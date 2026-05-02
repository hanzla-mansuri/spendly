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
