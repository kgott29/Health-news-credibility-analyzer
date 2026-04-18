"""
Health News Credibility Assessment System
Run: python app.py  ->  open http://127.0.0.1:5000
"""

import mysql.connector
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import re
from newspaper import Article

app = Flask(__name__, static_folder="static")

CORS(app)

# ========================= WORD LISTS =========================

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
]

EXAGGERATION_PATTERNS = [
    r"\b\d{3,}[%x]\b", r"\binstantly\b", r"\bovernight\b",
    r"\bmagically?\b", r"\bmiraculously?\b",
]

HEDGE_WORDS = ["may","might","could","suggests","indicates","appears"]

SCIENTIFIC_MARKERS = [
    r"\b(study|research|trial|analysis)\b",
    r"\b(pubmed|lancet|nejm|jama|bmj|nature|science)\b",
    r"\b(university|hospital|clinic)\b",
]

STATISTICAL_PATTERNS = [
    r"\b\d+\.?\d*\s?%\b",
    r"\b\d+ (out of|in) \d+\b",
]

INSTITUTIONS = ["who","cdc","nih","harvard","mayo clinic"]

TRUSTED_DOMAINS = [
    "ncbi.nlm.nih.gov",
    "pubmed.ncbi.nlm.nih.gov",
    "who.int",
    "cdc.gov",
    "nih.gov",
    "mayoclinic.org"
]

# ========================= DATABASE =========================

db = mysql.connector.connect(
    host="localhost",
    user="health_user",
    password="1234",
    database="health_news_detector"
)

cursor = db.cursor()

def save_to_database(url, emotional, scientific, credibility):
    try:
        query = """
        INSERT INTO article_analysis
        (article_url, emotional_score,
         scientific_score, credibility_score)
        VALUES (%s,%s,%s,%s)
        """
        values = (url, emotional, scientific, credibility)
        cursor.execute(query, values)
        db.commit()
    except Exception as e:
        print("DB Error:", e)

# ========================= CORE FUNCTIONS =========================

def extract_from_url(url):
    try:
        article = Article(url)
        article.download()
        article.parse()

        if len(article.text) < 50:
            return {"success": False, "error": "Article content too short"}

        return {
            "title": article.title,
            "text": article.text[:8000],
            "success": True
        }

    except Exception as e:
        return {"success": False, "error": str(e)}  
          
def generate_reader_report(signals):

    concerns = []
    positives = []

    if signals["emotional"]["sensational_words"]:
        concerns.append(
            "The article uses emotionally strong words like "
            + ", ".join(signals["emotional"]["sensational_words"][:3])
            + ", which may exaggerate claims."
        )

    if signals["emotional"]["exclamation_count"] > 2:
        concerns.append(
            "Frequent exclamation marks suggest a dramatic tone."
        )

    if signals["scientific"]["institutions_mentioned"]:
        positives.append(
            "Mentions trusted institutions such as "
            + ", ".join(signals["scientific"]["institutions_mentioned"])
        )

    if signals["scientific"]["statistical_claims"]:
        positives.append(
            "Includes numerical/statistical evidence supporting claims."
        )

    if signals["scientific"]["research_references"] > 0:
        positives.append(
            "Refers to scientific studies or research."
        )

    return concerns, positives

def analyse_text(text):

    lower = text.lower()

    s_hits = [w for w in SENSATIONAL_WORDS if w in lower]
    ab_hits = [w for w in ABSOLUTIST_WORDS if w in lower]
    ex_hits = re.findall("|".join(EXAGGERATION_PATTERNS), lower)
    hd_hits = [w for w in HEDGE_WORDS if w in lower]

    sci_hits = re.findall("|".join(SCIENTIFIC_MARKERS), lower)
    st_hits = re.findall("|".join(STATISTICAL_PATTERNS), lower)
    in_hits = [i for i in INSTITUTIONS if i in lower]

    exclamation_count = text.count("!")
    all_caps_words = re.findall(r"\b[A-Z]{3,}\b", text)

    emotional_score = min(
        (len(s_hits) + len(ab_hits) + len(ex_hits) + exclamation_count) / 12,
        1
    )

    scientific_score = min(
        (len(sci_hits) + len(st_hits) + len(in_hits) + len(hd_hits)) / 12,
        1
    )

    risk = (
        emotional_score * 45
        + exclamation_count * 2
        + len(all_caps_words) * 2
        - scientific_score * 35
        - len(st_hits) * 3
        - len(in_hits) * 4
        + 30
    )

    #risk_score = max(0, min(100, round(risk, 2)))
    credibility_score = round(100 - risk, 2)
    
    return {
        "emotional_score": emotional_score,
        "scientific_score": scientific_score,
        "credibility_score": credibility_score,

        "signals": {

            "emotional": {

                "sensational_words": s_hits,
                "absolutist_language": ab_hits,
                "exaggeration_patterns": ex_hits,
                "all_caps_words": all_caps_words,
                "exclamation_count": exclamation_count

            },

            "scientific": {

                "institutions_mentioned": in_hits,
                "statistical_claims": st_hits,
                "research_references": len(sci_hits),
                "hedge_words_used": hd_hits,
                "citation_count": len(re.findall(r"\[\d+\]", text)),
                "has_external_links": "http" in text

            }

        }

    }

def credibility_label(credibility_score):
    if credibility_score < 25:
        return "Low Reliability"
    elif credibility_score < 50:
        return "Moderate Reliability"
    elif credibility_score < 75:
        return "High Reliability"
    else:
        return "Very High Reliability"
# ========================= ROUTES =========================

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/report.html")
def report():
    return send_from_directory("static", "report.html")

@app.route("/api/analyse", methods=["POST"])
def analyse():
    data = request.get_json()

    url = (data.get("url") or "").strip()
    text = (data.get("text") or "").strip()
    title = ""

    if url:
        result = extract_from_url(url)
        if not result["success"]:
            return jsonify({"error": "URL fetch failed"}), 400
        text = result["text"]
        title = result["title"]

    if len(text) < 50:
        return jsonify({"error": "Text too short"}), 400

    analysis = analyse_text(text)

    if url and any(domain in url for domain in TRUSTED_DOMAINS):
        analysis["credibility_score"] = min(100, analysis["credibility_score"] + 15)
    
    print("📥 Calling save_to_database...")

    # ✅ SAVE TO DB
    save_to_database(
        url,
        analysis["emotional_score"],
        analysis["scientific_score"],
        analysis["credibility_score"]
        )
    
    concerns, positives = generate_reader_report(analysis["signals"])
        
    return jsonify({

    "title": title,

    "credibility_score": analysis["credibility_score"],

    "reliability_label": credibility_label(
        analysis["credibility_score"]
    ),

    "emotional": analysis["emotional_score"],

    "scientific": analysis["scientific_score"],

    "signals": analysis["signals"],

    "ai_assessment": {
        "summary": "Preliminary credibility estimation based on linguistic signals.",
        "reader_advice": "Verify claims using trusted medical sources.",
        "key_concerns": concerns,
        "positive_indicators": positives
    },

    "word_count": len(text.split())

})

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

# ========================= RUN =========================

if __name__ == "__main__":
    print("\nServer running at http://127.0.0.1:5000\n")
    app.run(debug=True)