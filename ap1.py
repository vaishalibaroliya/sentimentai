from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("index.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    result = None
    confidence = None

    if request.method == "POST":
        comment = request.form["comment"]

        # Simple Dummy Sentiment Logic
        if "good" in comment.lower():
            result = "Positive"
            confidence = "90%"
        elif "bad" in comment.lower():
            result = "Negative"
            confidence = "85%"
        else:
            result = "Neutral"
            confidence = "70%"

    return render_template("dashboard.html", result=result, confidence=confidence)

# ---------------- ADMIN ----------------
@app.route("/admin")
def admin():
    users = [
        {"id": 1, "name": "Student", "email": "student@email.com"}
    ]
    return render_template("admin.html", users=users)

# ---------------- ABOUT ----------------
@app.route("/about")
def about():
    return render_template("about.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return redirect(url_for("dashboard"))
    return render_template("login.html")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        return redirect(url_for("login"))
    return render_template("register.html")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)