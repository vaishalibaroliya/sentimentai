import sqlite3
import requests
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, jsonify
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

app = Flask(__name__)
DB_PATH = "database.db"

NEWS_API_KEY = "YOUR_API_KEY_HERE"  # ⚠️ apni key yaha daal

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


# ---------------- Sentiment ----------------
def analyze_sentiment(text):
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
        "neutral": len(df[df['sentiment'] == 'Neutral'])
    }


# ---------------- Routes ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    result = None
    confidence = None

    if request.method == "POST":
        comment = request.form.get("comment")

        if comment:
            sentiment, conf = analyze_sentiment(comment)

            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO comments (text, sentiment, confidence) VALUES (?, ?, ?)",
                (comment, sentiment, conf)
            )
            conn.commit()
            conn.close()

            result = sentiment
            confidence = f"{conf}%"

    summary = get_summary()

    return render_template(
        "dashboard.html",
        result=result,
        confidence=confidence,
        **summary
    )


# ---------------- SUMMARY API ----------------
@app.route("/summary")
def summary_api():
    return jsonify(get_summary())


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        )
        user = cur.fetchone()
        conn.close()

        if user:
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid email or password"

    return render_template("login.html", error=error)


# ---------------- REGISTER ----------------
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
            error = "Email already exists"

        conn.close()

        if not error:
            return redirect(url_for("login"))

    return render_template("register.html", error=error)


# ---------------- ADMIN ----------------
@app.route("/admin")
def admin():
    conn = sqlite3.connect(DB_PATH)
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template("admin.html", users=users)


# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)