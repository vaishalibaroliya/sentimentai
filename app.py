import sqlite3
import requests
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, jsonify
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from googleapiclient.discovery import build

app = Flask(__name__)
DB_PATH = "database.db"

# ⚠️ Make sure your API Key is unrestricted for YouTube Data API v3
YOUTUBE_API_KEY = "AIzaSyCgcCrMS1uivhs-a2YLNZEXF1s0wfzsfRU"

analyzer = SentimentIntensityAnalyzer()

# ---------------- Database Init ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            sentiment TEXT NOT NULL,
            confidence REAL DEFAULT 0,
            keyword TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# ---------------- Sentiment Logic ----------------
def analyze_sentiment(text):
    if not text:
        return 'Neutral', 0
    scores = analyzer.polarity_scores(text)
    compound = scores['compound']

    if compound >= 0.05:
        return 'Positive', round(50 + (compound * 50), 1)
    elif compound <= -0.05:
        return 'Negative', round(50 + (abs(compound) * 50), 1)
    else:
        return 'Neutral', round((1 - abs(compound)) * 100, 1)

# ---------------- Dashboard Summary ----------------
def get_summary():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT sentiment FROM comments", conn)
    conn.close()
    total = len(df)
    if total == 0:
        return {"total": 0, "positive": 0, "negative": 0, "neutral": 0}
    return {
        "total": total,
        "positive": len(df[df['sentiment'] == 'Positive']),
        "negative": len(df[df['sentiment'] == 'Negative']),
        "neutral": len(df[df['sentiment'] == 'Neutral'])
    }

# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    result = None
    confidence = None
    
    if request.method == "POST":
        comment_text = request.form.get("comment")
        if comment_text:
            sentiment, conf = analyze_sentiment(comment_text)
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO comments (text, sentiment, confidence, source) VALUES (?, ?, ?, ?)",
                (comment_text, sentiment, conf, 'manual')
            )
            conn.commit()
            conn.close()
            result = sentiment
            confidence = f"{conf}%"

    summary = get_summary()
    return render_template("dashboard.html", result=result, confidence=confidence, **summary)

# ---------------- UPDATED: KEYWORD FETCH ROUTE ----------------
@app.route("/fetch_by_keyword", methods=["POST"])
def fetch_by_keyword():
    keyword = request.form.get("keyword")
    if not keyword:
        return redirect(url_for('dashboard'))

    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

        # 1. Search for the top 5 videos based on the keyword
        search_response = youtube.search().list(
            q=keyword,
            part="snippet",
            type="video",
            maxResults=5,
            order="relevance"
        ).execute()

        conn = sqlite3.connect(DB_PATH)

        # 2. Loop through each video found and get comments
        for video in search_response.get('items', []):
            video_id = video['id']['videoId']
            
            try:
                # Fetch top 10 comments for THIS video
                comment_response = youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=10,
                    textFormat="plainText"
                ).execute()

                for item in comment_response.get('items', []):
                    text = item['snippet']['topLevelComment']['snippet']['textDisplay']
                    sentiment, conf = analyze_sentiment(text)
                    
                    conn.execute(
                        "INSERT INTO comments (text, sentiment, confidence, source, keyword) VALUES (?, ?, ?, ?, ?)",
                        (text, sentiment, conf, 'youtube_search', keyword)
                    )
            except Exception:
                # Skip videos that have comments disabled
                continue
        
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    except Exception as e:
        return f"Error connecting to YouTube: {str(e)}", 500

# ---------------- ADMIN & AUTH ----------------
@app.route("/admin")
def admin():
    conn = sqlite3.connect(DB_PATH)
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template("admin.html", users=users)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cur.fetchone()
        conn.close()
        if user: return redirect(url_for("dashboard"))
        else: error = "Invalid email or password"
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        name = request
