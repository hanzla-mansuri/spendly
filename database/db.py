import sqlite3
import os
from werkzeug.security import generate_password_hash


def get_db():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "spendly.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()

    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    if existing[0] > 0:
        conn.close()
        return

    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123"))
    )

    user = conn.execute("SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)).fetchone()
    user_id = user["id"]

    expenses = [
        (user_id, 42.50,  "Food",          "2026-05-01", "Grocery run"),
        (user_id, 18.00,  "Transport",     "2026-05-03", "Weekly bus pass"),
        (user_id, 120.00, "Bills",         "2026-05-05", "Electricity bill"),
        (user_id, 55.00,  "Health",        "2026-05-08", "Pharmacy"),
        (user_id, 30.00,  "Entertainment", "2026-05-10", "Streaming subscriptions"),
        (user_id, 89.99,  "Shopping",      "2026-05-14", "New shoes"),
        (user_id, 15.75,  "Food",          "2026-05-17", "Lunch at cafe"),
        (user_id, 25.00,  "Other",         "2026-05-20", "Miscellaneous"),
    ]

    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses
    )

    conn.commit()
    conn.close()


def _date_where(date_from, date_to):
    clauses, params = [], []
    if date_from:
        clauses.append("date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("date <= ?")
        params.append(date_to)
    sql = (" AND " + " AND ".join(clauses)) if clauses else ""
    return sql, params


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    from datetime import datetime
    created_dt = datetime.strptime(row["created_at"][:10], "%Y-%m-%d")
    words = row["name"].split()
    return {
        "name":         row["name"],
        "email":        row["email"],
        "member_since": created_dt.strftime("%B %Y"),
        "initials":     "".join(w[0] for w in words if w)[:2].upper(),
    }


def get_summary_stats(user_id, date_from=None, date_to=None):
    conn = get_db()
    ds, dp = _date_where(date_from, date_to)
    total_row = conn.execute(
        f"SELECT COALESCE(SUM(amount), 0.0) AS total, COUNT(*) AS cnt "
        f"FROM expenses WHERE user_id = ?{ds}",
        (user_id, *dp),
    ).fetchone()
    top_row = conn.execute(
        f"SELECT category FROM expenses WHERE user_id = ?{ds} "
        f"GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (user_id, *dp),
    ).fetchone()
    conn.close()
    return {
        "total_spent":       f"₹{total_row['total']:.2f}",
        "transaction_count": total_row["cnt"],
        "top_category":      top_row["category"] if top_row else "—",
    }


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    conn = get_db()
    ds, dp = _date_where(date_from, date_to)
    rows = conn.execute(
        f"SELECT date, description, category, amount FROM expenses "
        f"WHERE user_id = ?{ds} ORDER BY date DESC, id DESC LIMIT ?",
        (user_id, *dp, limit),
    ).fetchall()
    conn.close()
    from datetime import datetime
    result = []
    for row in rows:
        dt = datetime.strptime(row["date"], "%Y-%m-%d")
        formatted_date = dt.strftime("%B") + f" {dt.day}, " + str(dt.year)
        result.append({
            "date":        formatted_date,
            "description": row["description"] or "",
            "category":    row["category"],
            "amount":      f"₹{row['amount']:.2f}",
        })
    return result


def get_category_breakdown(user_id, date_from=None, date_to=None):
    conn = get_db()
    ds, dp = _date_where(date_from, date_to)
    rows = conn.execute(
        f"SELECT category, SUM(amount) AS cat_total FROM expenses "
        f"WHERE user_id = ?{ds} GROUP BY category ORDER BY cat_total DESC",
        (user_id, *dp),
    ).fetchall()
    conn.close()
    if not rows:
        return []
    grand_total = sum(row["cat_total"] for row in rows)
    result = [
        {
            "name":   row["category"],
            "amount": f"₹{row['cat_total']:.2f}",
            "pct":    int((row["cat_total"] / grand_total) * 100),
        }
        for row in rows
    ]
    result[0]["pct"] += 100 - sum(item["pct"] for item in result)
    return result


def get_user_by_email(email):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return user


def create_user(name, email, password):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password))
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()
