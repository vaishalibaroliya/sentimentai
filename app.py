import sqlite3
import re
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

# ---------------- Extract Video ID from any YouTube URL ----------------
def extract_video_id(url):
    """
    Handles all YouTube URL formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://youtube.com/shorts/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    """
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:shorts\/)([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

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
    summary = get_summary()
    return render_template("dashboard.html", **summary)

# ---------------- MAIN: Analyze YouTube Video URL ----------------
@app.route("/analyze_video", methods=["POST"])
def analyze_video():
    data = request.get_json()
    video_url = data.get('video_url', '').strip()

    if not video_url:
        return jsonify({'error': 'Please paste a YouTube video link'}), 400

    # Extract video ID
    video_id = extract_video_id(video_url)
    if not video_id:
        return jsonify({'error': 'Invalid YouTube URL. Please paste a valid YouTube video link.'}), 400

    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

        # Get video title and info
        video_response = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        ).execute()

        if not video_response.get('items'):
            return jsonify({'error': 'Video not found. Please check the link.'}), 404

        video_info = video_response['items'][0]
        video_title = video_info['snippet']['title']
        channel_name = video_info['snippet']['channelTitle']
        view_count = video_info['statistics'].get('viewCount', 0)
        like_count = video_info['statistics'].get('likeCount', 0)
        comment_count = video_info['statistics'].get('commentCount', 0)
        thumbnail = video_info['snippet']['thumbnails']['medium']['url']

        # Fetch comments (up to 100)
        results = []
        next_page_token = None
        conn = sqlite3.connect(DB_PATH)

        for _ in range(20):  # max 20 pages x 10 comments = 200 comments
            try:
                comment_response = youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=10,
                    pageToken=next_page_token,
                    textFormat="plainText",
                    order="relevance"
                ).execute()
            except Exception:
                break

            for item in comment_response.get('items', []):
                snippet = item['snippet']['topLevelComment']['snippet']
                text    = snippet.get('textDisplay', '').strip()
                author  = snippet.get('authorDisplayName', 'Anonymous')
                likes   = snippet.get('likeCount', 0)

                if len(text) < 3:
                    continue

                sentiment, confidence = analyze_sentiment(text)

                conn.execute(
                    "INSERT INTO comments (text, sentiment, confidence, source, keyword) VALUES (?, ?, ?, ?, ?)",
                    (text, sentiment, confidence, 'youtube_video', video_id)
                )

                results.append({
                    'text': text[:300],
                    'author': author,
                    'likes': likes,
                    'sentiment': sentiment,
                    'confidence': confidence
                })

            next_page_token = comment_response.get('nextPageToken')
            if not next_page_token:
                break

        conn.commit()
        conn.close()

        pos = sum(1 for r in results if r['sentiment'] == 'Positive')
        neg = sum(1 for r in results if r['sentiment'] == 'Negative')
        neu = sum(1 for r in results if r['sentiment'] == 'Neutral')
        total = len(results)

        return jsonify({
            'video_title': video_title,
            'channel_name': channel_name,
            'video_url': f"https://youtube.com/watch?v={video_id}",
            'thumbnail': thumbnail,
            'view_count': int(view_count),
            'like_count': int(like_count),
            'total_comments_on_video': int(comment_count),
            'total': total,
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
