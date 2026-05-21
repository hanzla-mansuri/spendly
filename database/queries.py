"""Read-only query helpers for the profile page."""

from database.db import get_db


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


def get_summary_stats(user_id):
    conn = get_db()
    total_row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0.0) AS total, COUNT(*) AS cnt "
        "FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    top_row = conn.execute(
        "SELECT category FROM expenses WHERE user_id = ? "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return {
        "total_spent":       f"₹{total_row['total']:.2f}",
        "transaction_count": total_row["cnt"],
        "top_category":      top_row["category"] if top_row else "—",
    }


def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    rows = conn.execute(
        "SELECT date, description, category, amount FROM expenses "
        "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
        (user_id, limit),
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


def get_category_breakdown(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT category, SUM(amount) AS cat_total FROM expenses "
        "WHERE user_id = ? GROUP BY category ORDER BY cat_total DESC",
        (user_id,),
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
