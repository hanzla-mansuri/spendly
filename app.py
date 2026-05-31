from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from datetime import date, datetime
import calendar
from database.db import (
    get_db, init_db, seed_db, create_user, get_user_by_email,
    get_user_by_id, get_summary_stats, get_recent_transactions, get_category_breakdown,
)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"


def _months_back(today, n):
    m = today.month - n
    y = today.year + m // 12
    m = m % 12
    if m == 0:
        m = 12
        y -= 1
    return today.replace(year=y, month=m, day=min(today.day, calendar.monthrange(y, m)[1]))


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

    today     = date.today()
    today_str = today.isoformat()

    presets = {
        "this_month":    (today.replace(day=1).isoformat(), today_str),
        "last_3_months": (_months_back(today, 3).isoformat(), today_str),
        "last_6_months": (_months_back(today, 6).isoformat(), today_str),
    }

    def _parse_date(raw):
        try:
            datetime.strptime(raw.strip(), "%Y-%m-%d")
            return raw.strip()
        except (ValueError, AttributeError):
            return None

    date_from = _parse_date(request.args.get("date_from", ""))
    date_to   = _parse_date(request.args.get("date_to", ""))

    if date_from and date_to and date_from > date_to:
        flash("Start date must be before end date.")
        date_from = None
        date_to   = None

    active_preset = "all_time"
    for name, (pf, pt) in presets.items():
        if (date_from, date_to) == (pf, pt):
            active_preset = name
            break
    else:
        if date_from is not None or date_to is not None:
            active_preset = "custom"

    user         = get_user_by_id(session["user_id"])
    stats        = get_summary_stats(session["user_id"], date_from=date_from, date_to=date_to)
    transactions = get_recent_transactions(session["user_id"], date_from=date_from, date_to=date_to)
    categories   = get_category_breakdown(session["user_id"], date_from=date_from, date_to=date_to)

    return render_template("profile.html",
                           user=user, stats=stats,
                           transactions=transactions, categories=categories,
                           date_from=date_from, date_to=date_to,
                           presets=presets, active_preset=active_preset)


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


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
