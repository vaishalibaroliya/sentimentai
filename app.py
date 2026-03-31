import sqlite3
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, jsonify
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from googleapiclient.discovery import build

app = Flask(__name__)
DB_PATH = "database.db"

# ==============================
# YOUR YOUTUBE API KEY
# ==============================
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

# ---------------- Summary ----------------
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
        "neutral":  len(df[df['sentiment'] == 'Neutral'])
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
        comment_text = request.form.get("comment", "").strip()
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

# ---------------- MAIN: YouTube Keyword Search (AJAX) ----------------
@app.route("/search", methods=["POST"])
def search():
    data = request.get_json()
    keyword = data.get('keyword', '').strip()

    if not keyword:
        return jsonify({'error': 'Please enter a keyword'}), 400

    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

        # Search top 5 videos for the keyword
        search_response = youtube.search().list(
            q=keyword,
            part="snippet",
            type="video",
            maxResults=5,
            order="relevance"
        ).execute()

        results = []
        conn = sqlite3.connect(DB_PATH)

        for video in search_response.get('items', []):
            video_id = video['id']['videoId']
            video_title = video['snippet']['title']
            channel = video['snippet']['channelTitle']

            try:
                # Fetch top 10 comments per video
                comment_response = youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=10,
                    textFormat="plainText"
                ).execute()

                for item in comment_response.get('items', []):
                    text = item['snippet']['topLevelComment']['snippet']['textDisplay']
                    author = item['snippet']['topLevelComment']['snippet']['authorDisplayName']
                    likes = item['snippet']['topLevelComment']['snippet']['likeCount']

                    if len(text.strip()) < 5:
                        continue

                    sentiment, confidence = analyze_sentiment(text)

                    conn.execute(
                        "INSERT INTO comments (text, sentiment, confidence, source, keyword) VALUES (?, ?, ?, ?, ?)",
                        (text, sentiment, confidence, 'youtube', keyword)
                    )

                    results.append({
                        'text': text[:300],
                        'author': author,
                        'likes': likes,
                        'video_title': video_title,
                        'channel': channel,
                        'video_url': f"https://youtube.com/watch?v={video_id}",
                        'sentiment': sentiment,
                        'confidence': confidence
                    })

            except Exception:
                # Skip videos with disabled comments
                continue

        conn.commit()
        conn.close()

        pos = sum(1 for r in results if r['sentiment'] == 'Positive')
        neg = sum(1 for r in results if r['sentiment'] == 'Negative')
        neu = sum(1 for r in results if r['sentiment'] == 'Neutral')

        return jsonify({
            'keyword': keyword,
            'total': len(results),
            'positive': pos,
            'negative': neg,
            'neutral': neu,
            'results': results
        })

    except Exception as e:
        return jsonify({'error': f'YouTube API error: {str(e)}'}), 500

# ---------------- Stats API ----------------
@app.route("/summary")
def summary_api():
    return jsonify(get_summary())

# ---------------- Auth ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        conn = sqlite3.connect(DB_PATH)
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?", (email, password)
        ).fetchone()
        conn.close()
        if user:
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid email or password"
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="Email already registered.")
        conn.close()
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        return redirect(url_for("login"))
    return render_template("forgot.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/admin")
def admin():
    conn = sqlite3.connect(DB_PATH)
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template("admin.html", users=users)

# ---------------- Run ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
