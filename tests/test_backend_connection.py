import pytest
from database.db import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# ------------------------------------------------------------------ #
# get_recent_transactions — Subagent 1                               #
# ------------------------------------------------------------------ #

def test_recent_transactions_returns_list(app):
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_recent_transactions(user["id"])
    assert isinstance(result, list)
    assert len(result) > 0


def test_recent_transactions_limit(app):
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_recent_transactions(user["id"], limit=3)
    assert len(result) <= 3


def test_recent_transactions_date_format(app):
    import re
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_recent_transactions(user["id"])
    for tx in result:
        assert re.match(r"[A-Z][a-z]+ \d{1,2}, \d{4}", tx["date"]), f"Bad date: {tx['date']}"


def test_recent_transactions_amount_format(app):
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_recent_transactions(user["id"])
    for tx in result:
        assert tx["amount"].startswith("₹"), f"Missing ₹ prefix: {tx['amount']}"


# ------------------------------------------------------------------ #
# get_user_by_id / get_summary_stats — Subagent 2                    #
# ------------------------------------------------------------------ #

def test_user_by_id_keys(app):
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user_row = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_user_by_id(user_row["id"])
    assert {"name", "email", "member_since", "initials"} == set(result.keys())


def test_user_member_since_format(app):
    import re
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user_row = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_user_by_id(user_row["id"])
    assert re.match(r"[A-Z][a-z]+ \d{4}", result["member_since"])


def test_user_initials_two_words(app):
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user_row = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_user_by_id(user_row["id"])
    assert result["initials"] == "DU"
    assert len(result["initials"]) <= 2
    assert result["initials"].isupper()


def test_summary_stats_keys(app):
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user_row = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_summary_stats(user_row["id"])
    assert {"total_spent", "transaction_count", "top_category"} == set(result.keys())


def test_summary_stats_total_spent_format(app):
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user_row = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_summary_stats(user_row["id"])
    assert result["total_spent"].startswith("₹")
    assert result["total_spent"] == "₹396.24"


def test_summary_stats_top_category(app):
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user_row = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_summary_stats(user_row["id"])
    assert result["top_category"] == "Bills"


def test_profile_route_200(auth_client):
    response = auth_client.get("/profile")
    assert response.status_code == 200
    assert b"Demo User" in response.data


def test_profile_route_redirects_when_logged_out(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ------------------------------------------------------------------ #
# get_category_breakdown — Subagent 3                                #
# ------------------------------------------------------------------ #

def test_category_breakdown_returns_list(app):
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user_row = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_category_breakdown(user_row["id"])
    assert isinstance(result, list)
    assert len(result) > 0
    for cat in result:
        assert {"name", "amount", "pct"} == set(cat.keys())


def test_category_breakdown_pct_sum(app):
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user_row = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_category_breakdown(user_row["id"])
    assert sum(cat["pct"] for cat in result) == 100


def test_category_breakdown_amount_format(app):
    with app.app_context():
        from database.db import seed_db, get_db
        seed_db()
        user_row = get_db().execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        result = get_category_breakdown(user_row["id"])
    for cat in result:
        assert cat["amount"].startswith("₹"), f"Missing ₹ prefix: {cat['amount']}"
        assert isinstance(cat["pct"], int)
