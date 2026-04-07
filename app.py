"""
Health News Credibility Assessment System
100% local - no API key required.
Run: python app.py  ->  open http://127.0.0.1:5000
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import re
import requests
from bs4 import BeautifulSoup

app = Flask(__name__, static_folder="static")
CORS(app)

SENSATIONAL_WORDS = [
    "shocking","explosive","bombshell","outrage","unbelievable","incredible",
    "insane","mind-blowing","jaw-dropping","terrifying","devastating","miracle",
    "breakthrough","revolutionary","secret","urgent","crisis","emergency",
    "alarming","scandalous","exposed","revealed","conspiracy","cover-up",
    "banned","suppressed","censored","danger","deadly","toxic","poisonous",
    "fatal","life-threatening","catastrophic","horrifying","stunning","eye-opening",
]
ABSOLUTIST_WORDS = [
    "always","never","everyone","nobody","all","none","every",
    "definitely","certainly","guaranteed","proven","100%","without doubt",
    "undeniably","absolutely","completely","totally","entirely","perfectly",
    "impossible","must","will always","will never","no exceptions",
    "without question","unquestionably","conclusively",
]
EXAGGERATION_PATTERNS = [
    r"\b\d{3,}[%x]\b", r"\binstantly\b", r"\bovernig?ht\b",
    r"\bmagically?\b", r"\bmiraculously?\b",
    r"\bin just \d+ (days?|hours?|minutes?|weeks?)\b",
    r"\bnumber one\b", r"\b#1\b",
    r"\bworld['\u2019]?s? (best|only|first|leading)\b",
    r"\bchange.?your.?life\b", r"\btransform.?your\b",
]
HEDGE_WORDS = [
    "may","might","could","suggests","indicates","appears","seems",
    "preliminary","initial","early","limited","small study","some evidence",
    "researchers say","scientists believe","experts suggest","according to",
    "reportedly","allegedly","claims","possible","potential","likely",
    "tentative","inconclusive","further research","early findings","pilot study",
]
SCIENTIFIC_MARKERS = [
    r"\b(study|studies|research|trial|experiment|analysis|meta-analysis)\b",
    r"\b(peer.?reviewed?|published|journal|pubmed|lancet|nejm|jama|bmj|nature|science)\b",
    r"\b(university|institute|hospital|clinic|center|centre|department)\b",
    r"\b(dr\.?|doctor|professor|phd|m\.?d\.?|researcher|scientist|epidemiologist)\b",
    r"\b(fda|cdc|who|nih|nhs|ema|nice|mayo clinic)\b",
    r"\b(p[\s-]?value|confidence interval|odds ratio|relative risk|hazard ratio|sample size)\b",
    r"\b(randomized|double.?blind|placebo|controlled|cohort|longitudinal)\b",
    r"\bhttps?://[^\s]+\b", r"\(\d{4}\)",
    r"\b(evidence.?based|systematic review|clinical trial|observational study)\b",
]
EMOTIONAL_TRIGGER_PATTERNS = [
    r"\byou (need|must|should|have to)\b",
    r"\bdon'?t (miss|ignore|skip)\b",
    r"\bbefore it'?s? too late\b",
    r"\bact now\b", r"\bwake up\b", r"\bshare (this|now|before)\b",
    r"\bwhat (they|doctors|big pharma) (don'?t want|won'?t tell)\b",
    r"\bthe truth (about|behind|they)\b",
    r"\bhidden (cure|treatment|remedy|secret)\b",
]
FEAR_PATTERNS = [
    r"\byou (could|might|may) (be|have|get|develop)\b",
    r"\bat risk\b", r"\bwarning (signs?|symptoms?)\b",
    r"\bkilling (you|us|people)\b", r"\bsilent (killer|epidemic|threat)\b",
    r"\bdeadly (secret|truth|risk|side effect)\b",
    r"\byour (doctor|government|hospital) (won'?t|doesn'?t|isn'?t)\b",
]
CREDIBILITY_BOOSTERS = [
    r"\baccording to (the )?(study|research|data|findings|report|journal)\b",
    r"\b(published|appeared) in\b",
    r"\bthe (study|research|trial|analysis) (found|showed|demonstrated|concluded)\b",
    r"\bpeer.?reviewed\b", r"\bstatistically significant\b",
    r"\breplication\b", r"\bconsensus\b",
]
INSTITUTIONS = [
    "harvard","stanford","mit","oxford","cambridge","johns hopkins",
    "mayo clinic","cleveland clinic","lancet","new england journal",
    "world health organization","cdc","nih","fda","who","pubmed",
    "nature","science","jama","bmj","annals","yale","columbia",
    "imperial college","wellcome","cochrane",
]
STATISTICAL_PATTERNS = [
    r"\b\d+\.?\d*\s?%\b", r"\b\d+ (out of|in) \d+\b", r"\bone in \d+\b",
    r"\b\d+\s?(times|fold)\b", r"\bincreased?\s+by\s+\d+",
    r"\bdecreased?\s+by\s+\d+", r"\breduced?\s+by\s+\d+",
    r"\bn\s?=\s?\d+\b", r"\b\d+\s?(patients?|participants?|subjects?)\b",
]


def extract_from_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script","style","nav","footer","header","aside"]):
            tag.decompose()
        title = ""
        h1 = soup.find("h1")
        if h1: title = h1.get_text(strip=True)
        elif soup.title: title = soup.title.get_text(strip=True)
        ct = soup.find_all(["article","main","section"])
        text = " ".join(t.get_text(separator=" ", strip=True) for t in ct) if ct else soup.get_text(separator=" ", strip=True)
        return {"title": title, "text": re.sub(r"\s+", " ", text).strip()[:8000], "success": True}
    except Exception as e:
        return {"title": "", "text": "", "success": False, "error": str(e)}


def count_matches(text, patterns, flags=re.IGNORECASE):
    out = []
    for p in patterns:
        found = re.findall(p, text, flags)
        out.extend(found if found else [])
    return out


def analyse_text(text):
    lower = text.lower()
    word_count = max(len(re.findall(r"\b\w+\b", lower)), 1)
    s_hits  = [w for w in SENSATIONAL_WORDS if w in lower]
    ab_hits = [w for w in ABSOLUTIST_WORDS if f" {w} " in f" {lower} "]
    ex_hits = count_matches(text, EXAGGERATION_PATTERNS)
    tr_hits = count_matches(text, EMOTIONAL_TRIGGER_PATTERNS)
    fr_hits = count_matches(text, FEAR_PATTERNS)
    hd_hits = [w for w in HEDGE_WORDS if w in lower]
    cb_hits = count_matches(text, CREDIBILITY_BOOSTERS)
    caps    = re.findall(r"\b[A-Z]{3,}\b", text)
    excl    = text.count("!")
    qbait   = len(re.findall(r"\?{2,}|!\?|[?!]{3,}", text))
    sci_hits= count_matches(text, SCIENTIFIC_MARKERS)
    st_hits = count_matches(text, STATISTICAL_PATTERNS)
    in_hits = [i for i in INSTITUTIONS if i in lower]
    links   = bool(re.search(r"https?://", text))
    cites   = len(re.findall(r"\(\d{4}\)|\[\d+\]", text))
    pos = sum(lower.count(w) for w in ["effective","safe","proven","beneficial","healthy","improve","cure","treat","heal","protect","prevent","boost","positive","success","recovery"])
    neg = sum(lower.count(w) for w in ["dangerous","toxic","harmful","risk","deadly","kill","destroy","damage","serious","severe","warning","threat","poison","death"])
    polarity = (pos - neg) / max(pos + neg, 1)
    em_score = min((len(s_hits)*2 + len(ab_hits)*1.5 + len(ex_hits)*2 + len(tr_hits)*2.5 + len(fr_hits)*1.5 + len(caps)*0.5 + excl*0.3 + qbait*1.5 + abs(polarity)*5) / 22, 1.0)
    sc_score = min((len(sci_hits)*1.5 + len(st_hits) + len(in_hits)*2 + len(hd_hits)*0.5 + len(cb_hits)*1.5 + (5 if links else 0) + cites) / 22, 1.0)
    risk = round(max(0, min(100, (em_score*60) - (sc_score*40) + 40)), 1)
    return {
        "word_count": word_count,
        "emotional_score": round(em_score, 3),
        "scientific_score": round(sc_score, 3),
        "risk_score": risk,
        "raw": {"s_hits":s_hits,"ab_hits":ab_hits,"ex_hits":ex_hits,"tr_hits":tr_hits,"fr_hits":fr_hits,"hd_hits":hd_hits,"cb_hits":cb_hits,"caps":caps,"excl":excl,"qbait":qbait,"sci_hits":sci_hits,"st_hits":st_hits,"in_hits":in_hits,"links":links,"cites":cites,"polarity":polarity},
        "signals": {
            "emotional": {
                "sensational_words": s_hits[:10], "absolutist_language": ab_hits[:10],
                "exaggeration_patterns": [str(e) for e in ex_hits[:5]],
                "emotional_triggers": [str(e) for e in tr_hits[:5]],
                "all_caps_words": list(set(caps))[:8], "exclamation_count": excl,
                "sentiment_polarity": round(polarity,3),
                "sentiment_label": ("strongly positive" if polarity>0.5 else "positive" if polarity>0.1 else "strongly negative" if polarity<-0.5 else "negative" if polarity<-0.1 else "neutral"),
            },
            "scientific": {
                "research_references": len(sci_hits), "statistical_claims": [str(s) for s in st_hits[:8]],
                "institutions_mentioned": in_hits, "hedge_words_used": hd_hits[:8],
                "has_external_links": links, "citation_count": cites,
            }
        }
    }


def risk_label(score):
    if score < 25: return "Low Risk"
    if score < 50: return "Moderate Risk"
    if score < 75: return "High Risk"
    return "Very High Risk"


def build_assessment(analysis):
    r      = analysis["raw"]
    risk   = analysis["risk_score"]
    em_pct = round(analysis["emotional_score"] * 100)
    sc_pct = round(analysis["scientific_score"] * 100)

    # ── Plain-language summary ──
    parts = []

    if risk < 25:
        parts.append(
            "Based on our analysis, this article appears to be written in a responsible and measured way. "
            "It does not rely on scare tactics or exaggerated language to make its point, and there are signs "
            "that it draws on credible sources. This does not mean every claim is correct, but the overall "
            "style and structure are consistent with trustworthy health journalism."
        )
    elif risk < 40:
        parts.append(
            "This article is broadly reasonable but has a few patterns worth noting. "
            "While it does not raise major red flags, some of its language or sourcing could be stronger. "
            "Readers should feel reasonably confident but may want to quickly verify any specific statistics or treatment claims."
        )
    elif risk < 55:
        parts.append(
            "This article has a mixed profile — it contains both legitimate information and concerning patterns. "
            "On one hand, there may be some scientific references or measured language. On the other, "
            "certain phrases or claims appear designed to trigger an emotional reaction rather than inform. "
            "We recommend reading this critically and checking the key claims independently before acting or sharing."
        )
    elif risk < 70:
        parts.append(
            "This article shows several warning signs that it may be exaggerating or distorting health information. "
            "The way it is written — the words chosen, the claims made, and how sources are used — is more "
            "consistent with content designed to alarm or persuade than to inform. "
            "You should be cautious about trusting this article at face value."
        )
    else:
        parts.append(
            "This article has the hallmarks of misleading or sensationalist health content. "
            "It relies heavily on emotional language, makes sweeping claims without solid evidence, "
            "and shows little sign of genuine scientific grounding. "
            "Content like this can cause real harm by spreading health misinformation. "
            "We strongly advise against acting on or sharing this article without first checking trusted medical sources."
        )

    if em_pct >= 65:
        if r["s_hits"]:
            parts.append(
                f"In terms of emotional tone, the article scores very high ({em_pct}%). "
                f"Words like '{r['s_hits'][0]}'" + (f" and '{r['s_hits'][1]}'" if len(r['s_hits']) > 1 else "") +
                " are typical of writing that is trying to provoke fear or outrage rather than report facts. "
                "When health articles use this kind of language, it often signals that the content is more "
                "interested in getting clicks or shares than in accurately representing medical evidence."
            )
        if r["ab_hits"]:
            parts.append(
                f"The article also uses absolute statements like '{r['ab_hits'][0]}'. "
                "In medicine and science, very few things are ever 'always' or 'never' true — "
                "so when an article uses these words confidently, it is usually oversimplifying "
                "or ignoring important nuance."
            )
    elif em_pct >= 35:
        parts.append(
            f"The emotional tone of this article is moderate ({em_pct}%). "
            "It uses some charged language but does not rely on it throughout. "
            "This is worth noting but is not necessarily a sign of misinformation on its own."
        )
    else:
        parts.append(
            f"The emotional tone is low ({em_pct}%), meaning the article avoids exaggerated or fear-based "
            "language. This is generally a positive sign — good health journalism tends to be calm and factual."
        )

    if sc_pct >= 60:
        sci_note = f"On the scientific credibility side, this article scores well ({sc_pct}%). "
        if r["in_hits"]:
            sci_note += f"It mentions institutions like {', '.join(i.upper() for i in r['in_hits'][:2])}, which are recognised authorities in health. "
        if r["hd_hits"]:
            sci_note += ("It also uses careful, qualified language — phrases like 'may', 'suggests', or 'according to' — "
                        "which is how real scientists and doctors talk, because they acknowledge uncertainty. ")
        if r["st_hits"]:
            sci_note += "The presence of specific statistics or data figures also suggests the article is grounded in actual research. "
        parts.append(sci_note)
    elif sc_pct >= 25:
        parts.append(
            f"The scientific credibility score is moderate ({sc_pct}%). "
            "The article shows some awareness of evidence, but not enough to fully verify its claims. "
            + ("It does not cite any well-known health institutions, which makes it harder to trust. " if not r["in_hits"] else "")
            + ("No specific statistics are provided to back up its claims. " if not r["st_hits"] else "")
        )
    else:
        parts.append(
            f"The scientific credibility score is very low ({sc_pct}%). "
            "The article makes claims about health without pointing to any studies, experts, or data. "
            "In health journalism, this is a serious concern — any significant health claim should be backed "
            "by evidence, and a reader has no way to verify anything written here."
        )

    summary = " ".join(parts)

    # ── Key concerns ──
    concerns = []
    if r["s_hits"]:
        sample = "', '".join(r["s_hits"][:3])
        concerns.append(
            f"The article uses alarming words like '{sample}'. These are emotional triggers — "
            "they are designed to make you feel scared or outraged, which can cloud your judgement "
            "about whether the information is actually accurate."
        )
    if r["ab_hits"]:
        sample = "', '".join(r["ab_hits"][:2])
        concerns.append(
            f"Phrases like '{sample}' are used as if they are definitive facts. "
            "Real health research almost never speaks in absolutes — the body is complex, "
            "and what is true for one person may not be true for another. Absolute claims are a red flag."
        )
    if r["ex_hits"]:
        concerns.append(
            f"The article contains {len(r['ex_hits'])} instance(s) of exaggerated claims — "
            "such as things working 'instantly', 'overnight', or being dramatically more effective. "
            "Legitimate medical research does not make these kinds of dramatic promises."
        )
    if r["tr_hits"]:
        concerns.append(
            "The article tries to create a sense of urgency — telling you to act now, share immediately, "
            "or warning that 'it's too late' if you don't. This is a manipulation technique "
            "commonly used in health misinformation to stop you from pausing and thinking critically."
        )
    if r["fr_hits"]:
        concerns.append(
            "Fear-based framing is present — the article uses language designed to make you feel personally "
            "at risk or threatened. This is a well-documented technique in misleading health content to "
            "bypass rational thinking and push emotional decision-making."
        )
    if r["excl"] > 3:
        concerns.append(
            f"There are {r['excl']} exclamation marks in this article. "
            "Credible health journalism rarely uses exclamation marks — they signal excitement or alarm "
            "rather than factual reporting."
        )
    if len(r["sci_hits"]) == 0:
        concerns.append(
            "No scientific studies, research papers, or academic sources are mentioned anywhere. "
            "Any significant health claim should be backed by research. An article that makes health "
            "claims without citing any evidence should be treated with serious scepticism."
        )
    if not r["in_hits"]:
        concerns.append(
            "No credible health organisations (such as the WHO, CDC, NHS, or NIH) are referenced. "
            "Trustworthy health articles typically point to recognised experts or institutions. "
            "When none are cited, there is no way to know whether the information reflects mainstream medical understanding."
        )
    if not r["links"] and not r["cites"]:
        concerns.append(
            "There are no links or citations anywhere in the article. "
            "This means you cannot follow up on any of the claims made. "
            "Credible health content always gives you a path to verify what you are reading."
        )
    if not concerns:
        concerns.append(
            "No significant manipulation or misinformation signals were detected. "
            "The article appears to follow responsible health communication standards."
        )

    # ── Positive indicators ──
    positives = []
    if r["in_hits"]:
        positives.append(
            f"The article references {', '.join(i.upper() for i in r['in_hits'][:2])} — "
            "these are widely recognised and trusted health authorities. "
            "When an article cites institutions like these, it suggests the claims are at least "
            "partially grounded in mainstream medical knowledge."
        )
    if len(r["sci_hits"]) > 3:
        positives.append(
            f"There is a good amount of scientific language in this article ({len(r['sci_hits'])} research-related terms). "
            "This suggests the author is engaging with actual evidence rather than just making things up."
        )
    elif len(r["sci_hits"]) > 0:
        positives.append(
            "Some scientific terminology is used, which suggests at least partial engagement with evidence-based sources."
        )
    if r["st_hits"]:
        positives.append(
            "The article includes specific numbers and statistics, which is a positive sign. "
            "Vague health claims are much easier to fabricate than specific ones backed by data. "
            "Statistics suggest the author is drawing on actual research."
        )
    if r["hd_hits"]:
        positives.append(
            "The article uses cautious, qualified language — words like 'may', 'could', 'suggests', or "
            "'according to'. This is how scientists and doctors communicate, because they acknowledge "
            "that evidence has limits. Articles that speak in certainties are often less trustworthy."
        )
    if r["links"]:
        positives.append(
            "The article includes external links, meaning you can click through and check the original "
            "sources yourself. This transparency is a hallmark of honest, accountable journalism."
        )
    if r["cites"] > 0:
        positives.append(
            f"There are {r['cites']} citation(s) or dated references in the article. "
            "This suggests the author is pointing to specific, traceable sources rather than making claims without basis."
        )
    if analysis["word_count"] > 600:
        positives.append(
            f"At {analysis['word_count']} words, this is a substantial article. "
            "Longer articles generally allow for more nuance, context, and evidence — "
            "short, punchy health articles are more likely to oversimplify."
        )
    if not positives:
        positives.append(
            "No strong positive credibility indicators were found. "
            "This does not necessarily mean the article is wrong, but there is little "
            "in its structure or language to inspire confidence."
        )

    # ── Reader advice ──
    if risk < 25:
        advice = (
            "This article appears credible. If a health claim is relevant to you personally, "
            "still confirm it with your doctor — no article, however well-written, replaces professional medical advice."
        )
    elif risk < 40:
        advice = (
            "This article is broadly reasonable. For any specific claim that would influence a health decision, "
            "quickly check it against a trusted source like NHS.uk, CDC.gov, or PubMed."
        )
    elif risk < 55:
        advice = (
            "Be a careful reader. Before sharing this article or acting on anything it says, "
            "look up the main claim on a trusted health site. If you cannot find the same information "
            "on CDC, WHO, or NHS, treat the article with significant caution."
        )
    elif risk < 70:
        advice = (
            "We would advise against sharing this article without first verifying its claims. "
            "Search the core topic on PubMed, NIH, or your national health authority. "
            "If the article's claims do not appear there, that is a strong signal the content may be misleading."
        )
    else:
        advice = (
            "Please do not share or act on this article. The analysis suggests it has the characteristics "
            "of misleading health content. If you are concerned about the health topic it covers, "
            "go directly to WHO.int, CDC.gov, or NHS.uk for accurate information. "
            "Sharing articles like this — even with good intentions — can spread harmful misinformation."
        )

    confidence = (
        "High" if analysis["word_count"] > 500 else
        "Medium" if analysis["word_count"] > 150 else
        "Low — article is very short, analysis may be incomplete"
    )

    return {
        "overall_verdict":    risk_label(risk),
        "summary":            summary,
        "key_concerns":       concerns[:5],
        "positive_indicators":positives[:5],
        "reader_advice":      advice,
        "confidence":         confidence,
    }


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/analyse", methods=["POST"])
def analyse():
    data  = request.get_json(force=True)
    url   = (data.get("url") or "").strip()
    text  = (data.get("text") or "").strip()
    title = ""
    if url:
        result = extract_from_url(url)
        if not result["success"]:
            return jsonify({"error": "Could not fetch URL: " + result.get("error","unknown")}), 400
        text, title = result["text"], result["title"]
    if not text or len(text) < 50:
        return jsonify({"error": "Article text is too short. Please provide at least 50 characters."}), 400
    analysis   = analyse_text(text)
    assessment = build_assessment(analysis)
    return jsonify({
        "title":            title,
        "risk_score":       analysis["risk_score"],
        "risk_label":       risk_label(analysis["risk_score"]),
        "emotional_score":  analysis["emotional_score"],
        "scientific_score": analysis["scientific_score"],
        "word_count":       analysis["word_count"],
        "signals":          analysis["signals"],
        "ai_assessment":    assessment,
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  HealthCheck — 100% local, no API needed")
    print("  Open: http://127.0.0.1:5000")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)