# Spec: Add Expense

## Overview
This feature implements the "Add Expense" form, allowing a logged-in user to record a new expense by submitting an amount, category, date, and optional description. It replaces the stub route at `GET /expenses/add` with a fully functional `GET/POST` route that validates input and inserts a row into the `expenses` table. This is the first write path for expense data in Spendly and is a prerequisite for edit and delete features in later steps.

## Depends on
- Step 01 — Database Setup (`expenses` table must exist)
- Step 03 — Login/Logout (session-based auth guard required)
- Step 04/05 — Profile Page (redirects user back to `/profile` on success)

## Routes
- `GET /expenses/add` — Render the add-expense form — logged-in only
- `POST /expenses/add` — Validate and insert the expense, redirect to `/profile` on success — logged-in only

## Database changes
No new tables or columns. The `expenses` table already exists in `database/db.py` with columns: `id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

A new DB helper `add_expense(user_id, amount, category, date, description)` must be added to `database/db.py`.

## Templates
- **Create:** `templates/add_expense.html` — form with fields: amount, category (dropdown), date, description (optional)
- **Modify:** None

## Files to change
- `app.py` — replace stub `add_expense` route with GET/POST implementation; import `add_expense` from `database.db`
- `database/db.py` — add `add_expense()` helper function

## Files to create
- `templates/add_expense.html` — the add-expense form page

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not applicable here, but no new auth logic)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Auth guard: redirect to `/login` if `session.get("user_id")` is falsy
- `amount` must be a positive number — reject zero or negative values
- `category` must be one of the fixed allowed values: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- `date` must be a valid `YYYY-MM-DD` string — reject malformed input
- On validation error, re-render the form with the error message and the previously entered values preserved
- On success, redirect to `url_for("profile")` with a flash message "Expense added."
- `add_expense()` in `db.py` must accept `(user_id, amount, category, date, description)` and insert one row

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders a form with fields: amount, category, date, description
- [ ] Submitting the form with all valid fields inserts a new row in `expenses` and redirects to `/profile`
- [ ] A flash message "Expense added." is visible on the profile page after a successful submission
- [ ] The new expense appears in the transactions list on `/profile`
- [ ] Submitting with a missing or blank `amount` re-renders the form with an error message
- [ ] Submitting with a non-numeric `amount` re-renders the form with an error message
- [ ] Submitting with a zero or negative `amount` re-renders the form with an error message
- [ ] Submitting with an invalid or missing `category` re-renders the form with an error message
- [ ] Submitting with a missing or malformed `date` re-renders the form with an error message
- [ ] Previously entered form values are preserved when the form re-renders after a validation error
