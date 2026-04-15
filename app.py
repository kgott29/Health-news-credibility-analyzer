"""
Health News Credibility Assessment System
Run: python app.py  ->  open http://127.0.0.1:5000
"""

import mysql.connector
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import re
import requests
from bs4 import BeautifulSoup

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
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script","style"]):
            tag.decompose()

        title = soup.title.string if soup.title else ""
        text = soup.get_text()

        return {"title": title, "text": text[:8000], "success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def analyse_text(text):
    lower = text.lower()

    s_hits = [w for w in SENSATIONAL_WORDS if w in lower]
    ab_hits = [w for w in ABSOLUTIST_WORDS if w in lower]
    ex_hits = re.findall("|".join(EXAGGERATION_PATTERNS), lower)
    hd_hits = [w for w in HEDGE_WORDS if w in lower]
    sci_hits = re.findall("|".join(SCIENTIFIC_MARKERS), lower)
    st_hits = re.findall("|".join(STATISTICAL_PATTERNS), lower)
    in_hits = [i for i in INSTITUTIONS if i in lower]

    emotional_score = min(len(s_hits + ab_hits + ex_hits) / 10, 1)
    scientific_score = min(len(sci_hits + st_hits + in_hits + hd_hits) / 10, 1)

    risk = round((emotional_score * 60) - (scientific_score * 40) + 40, 1)

    return {
        "emotional_score": emotional_score,
        "scientific_score": scientific_score,
        "risk_score": risk,
        "raw": {"st_hits": st_hits}
    }

def risk_label(score):
    if score < 25: return "Low Risk"
    if score < 50: return "Moderate Risk"
    if score < 75: return "High Risk"
    return "Very High Risk"

# ========================= ROUTES =========================

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

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
    
    print("📥 Calling save_to_database...")

    # ✅ SAVE TO DB
    save_to_database(
        url,
        analysis["emotional_score"],
        analysis["scientific_score"],
        analysis["risk_score"]
        )
        
    return jsonify({
    "title": title,
    "risk_score": analysis["risk_score"],
    "risk_label": risk_label(analysis["risk_score"]),
    "emotional": analysis["emotional_score"],
    "scientific": analysis["scientific_score"],

    "signals": {
        "emotional": {
            "sensational_words": [],
            "absolutist_language": [],
            "exaggeration_patterns": [],
            "all_caps_words": [],
            "emotional_triggers": [],
            "exclamation_count": 0,
            "sentiment_label": "Neutral"
        },
        "scientific": {
            "institutions_mentioned": [],
            "statistical_claims": [],
            "research_references": 0,
            "citation_count": 0,
            "hedge_words_used": [],
            "has_external_links": False
        }
    },

    "ai_assessment": {
        "summary": "Preliminary credibility estimation based on linguistic signals.",
        "reader_advice": "Verify claims using trusted medical sources.",
        "key_concerns": [],
        "positive_indicators": []
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