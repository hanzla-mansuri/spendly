Spec: Registration
Overview
Implement the POST /register handler so users can create accounts. The form already exists in register.html and the users table is ready from Step 01. This step wires them together: a create_user() helper in database/db.py, a POST route in app.py that validates input, hashes the password, inserts the user, and redirects to /login on success. Errors (duplicate email, missing fields) re-render the form with an inline message.

Depends on
Step 01 — Database Setup (users table, get_db(), and init_db() must be implemented).

Routes
POST /register — process registration form — public

The existing GET /register stays as-is; its route decorator gains methods=["GET", "POST"].

Database changes
No database changes. The users table already exists with the correct schema.

Templates
Modify: templates/register.html — change action="/register" to action="{{ url_for('register') }}". No other template changes; {{ error }} display is already in place.

Files to change
app.py — add request, redirect, url_for to Flask imports; add create_user to the database.db import; expand /register route to handle POST. Added logic: Perform server-side validation to ensure no fields are empty or whitespace-only before calling the database.

database/db.py — add create_user(name, email, password) helper. Added logic: Import sqlite3.IntegrityError and werkzeug.security.generate_password_hash. The function should return the new row ID on success and None on IntegrityError.

templates/register.html — fix hardcoded action URL.

Files to create
None.

New dependencies
No new dependencies.

Rules for implementation
No SQLAlchemy or ORMs

Parameterized queries only (? placeholders) — never f-strings in SQL

Passwords hashed with werkzeug.security.generate_password_hash before storing — never store plaintext

Use CSS variables — never hardcode hex values

All templates extend base.html

Route must declare methods=["GET", "POST"]

On GET: render form (existing behaviour, no change)

On POST: validate (check for empty strings) → hash → insert → redirect on success, re-render with error string on failure

create_user() must catch sqlite3.IntegrityError to detect duplicate email and return None to the route — do not let the exception bubble up to the browser

Do not use flash() or session — those are introduced in Step 03

Definition of done
[ ] Submitting the form with a new name/email/password creates a row in users with a hashed password_hash

[ ] Submitting with a duplicate email re-renders the form with a user-visible error message and does not crash

[ ] Submitting empty fields or whitespace triggers a "All fields are required" error

[ ] On success, the browser is redirected to /login

[ ] password_hash never contains a plaintext password (verify directly in spendly.db)

[ ] create_user() lives in database/db.py, not inline in the route, and returns a consistent value (ID or None)

[ ] Form action uses url_for('register'), not a hardcoded URL

[ ] App starts and runs without errors after the change