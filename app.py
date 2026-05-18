from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))
    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not name or not email or not password:
            return render_template("register.html", error="All fields are required")

        user_id = create_user(name, email, password)
        if user_id is None:
            return render_template("register.html", error="An account with that email already exists")

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            return render_template("login.html", error="All fields are required.")

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid email or password.")

        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name":         session["user_name"],
        "email":        "demo@spendly.com",
        "member_since": "January 2024",
        "initials":     session["user_name"][:2].upper(),
    }

    stats = {
        "total_spent":       "₹396.24",
        "transaction_count": 8,
        "top_category":      "Bills",
    }

    transactions = [
        {"date": "May 17, 2026", "description": "Lunch at cafe",          "category": "Food",          "amount": "₹15.75"},
        {"date": "May 14, 2026", "description": "New shoes",               "category": "Shopping",      "amount": "₹89.99"},
        {"date": "May 10, 2026", "description": "Streaming subscriptions", "category": "Entertainment", "amount": "₹30.00"},
        {"date": "May 8,  2026", "description": "Pharmacy",                "category": "Health",        "amount": "₹55.00"},
        {"date": "May 5,  2026", "description": "Electricity bill",        "category": "Bills",         "amount": "₹120.00"},
    ]

    categories = [
        {"name": "Bills",         "amount": "₹120.00", "pct": 30},
        {"name": "Shopping",      "amount": "₹89.99",  "pct": 23},
        {"name": "Food",          "amount": "₹58.25",  "pct": 15},
        {"name": "Health",        "amount": "₹55.00",  "pct": 14},
        {"name": "Entertainment", "amount": "₹30.00",  "pct": 8},
        {"name": "Other",         "amount": "₹25.00",  "pct": 6},
        {"name": "Transport",     "amount": "₹18.00",  "pct": 5},
    ]

    return render_template("profile.html",
                           user=user, stats=stats,
                           transactions=transactions, categories=categories)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=True, port=5001)
