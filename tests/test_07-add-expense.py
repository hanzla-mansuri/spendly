"""
tests/test_07-add-expense.py

Behaviour tests for the Step 07 "Add Expense" feature.

Spec under test
---------------
Route:  GET  /expenses/add  — render add-expense form (auth-guarded)
        POST /expenses/add  — validate and insert expense (auth-guarded)

Auth guard
----------
- Unauthenticated GET  → 302 redirect to /login
- Unauthenticated POST → 302 redirect to /login

GET (logged in)
---------------
- Returns 200
- Response contains the form fields: amount, category, date, description

POST — happy path
-----------------
- Valid full submission → 302 redirect to /profile
- Flash message "Expense added." visible on redirect target
- New expense row present in the DB with correct values

POST — optional description
----------------------------
- Submission without description field → success, no error

POST — validation errors (each re-renders the form with an error message)
---------------------------------------------------------------------------
- Blank amount
- Missing amount (field absent from POST body)
- Non-numeric amount (e.g. "abc")
- Zero amount ("0")
- Negative amount ("-10")
- Invalid category (not in allowed list)
- Missing category (field absent)
- Missing date (field absent)
- Malformed date ("31-12-2026", "not-a-date")

POST — form value preservation on validation error
---------------------------------------------------
- Previously entered values survive re-render so the user does not
  have to re-type every field after fixing one error.

Isolation strategy
------------------
get_db() in database/db.py reads a hardcoded file path ("spendly.db").
To keep tests fully isolated from the real database, each test that
exercises a write path patches get_db() via monkeypatch to return a
connection to a fresh temporary SQLite file.  Tests that only exercise
the auth guard or GET rendering do not need DB isolation because they
perform no writes and the auth check runs before any DB call.

A dedicated test user (not the seed demo user) is inserted into the
temp DB so that session["user_id"] resolves to a real user row.
"""

import sqlite3
import tempfile
import os
import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from database.db import init_db


# ------------------------------------------------------------------ #
# Constants                                                           #
# ------------------------------------------------------------------ #

ADD_EXPENSE_URL = "/expenses/add"

VALID_FORM = {
    "amount":      "42.50",
    "category":    "Food",
    "date":        "2026-06-01",
    "description": "Test lunch",
}

VALID_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def app():
    """
    Flask app in TESTING mode.  init_db() is called so the schema exists
    in whatever DB get_db() points to at the time (tests that need
    isolation will patch get_db() before any DB call).
    """
    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
    })
    with flask_app.app_context():
        init_db()
    yield flask_app


@pytest.fixture
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


@pytest.fixture
def isolated_db(tmp_path):
    """
    Return a factory that, when called, gives a fresh sqlite3 connection
    to a temp file DB with the Spendly schema initialised and a single
    test user inserted.

    Returns a dict with:
        conn_factory  — callable () -> sqlite3.Connection (used by monkeypatch)
        db_path       — str path to the temp SQLite file
        user_id       — int id of the inserted test user
    """
    db_file = str(tmp_path / "test_spendly.db")

    # Build schema and insert a test user using a direct connection
    setup_conn = sqlite3.connect(db_file)
    setup_conn.row_factory = sqlite3.Row
    setup_conn.execute("PRAGMA foreign_keys = ON")
    setup_conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        )
    """)
    setup_conn.execute("""
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
    cursor = setup_conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Test User", "test@spendly.com", generate_password_hash("testpass"))
    )
    setup_conn.commit()
    user_id = cursor.lastrowid
    setup_conn.close()

    def conn_factory():
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    return {"conn_factory": conn_factory, "db_path": db_file, "user_id": user_id}


@pytest.fixture
def auth_client(app, isolated_db, monkeypatch):
    """
    Test client with an active session for the isolated test user.
    get_db() is patched so all DB calls during the request go to the
    temp file instead of the real spendly.db.
    """
    import database.db as db_module
    monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

    user_id = isolated_db["user_id"]
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"]   = user_id
        sess["user_name"] = "Test User"

    return test_client


# ------------------------------------------------------------------ #
# Helper                                                              #
# ------------------------------------------------------------------ #

def _count_expenses(isolated_db, user_id):
    """Return how many expense rows exist for user_id in the temp DB."""
    conn = isolated_db["conn_factory"]()
    row  = conn.execute(
        "SELECT COUNT(*) AS cnt FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row["cnt"]


def _fetch_expenses(isolated_db, user_id):
    """Return all expense rows for user_id from the temp DB as a list of dicts."""
    conn  = isolated_db["conn_factory"]()
    rows  = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ================================================================== #
# AUTH GUARD TESTS                                                    #
# ================================================================== #

class TestAuthGuard:
    """Unauthenticated requests must be blocked regardless of HTTP method."""

    def test_unauthenticated_get_redirects_to_login(self, client):
        """
        GET /expenses/add without a session must return 302 and redirect
        the user to /login.
        """
        # Act
        response = client.get(ADD_EXPENSE_URL)

        # Assert
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_unauthenticated_post_redirects_to_login(self, client):
        """
        POST /expenses/add without a session must return 302 and redirect
        to /login even when a complete valid form body is submitted.
        """
        # Act
        response = client.post(ADD_EXPENSE_URL, data=VALID_FORM)

        # Assert
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_unauthenticated_get_does_not_return_200(self, client):
        """
        The route must never hand out a 200 to an unauthenticated caller.
        """
        response = client.get(ADD_EXPENSE_URL)

        assert response.status_code != 200


# ================================================================== #
# GET — FORM RENDERING                                                #
# ================================================================== #

class TestGetFormRendering:
    """Logged-in users must receive a correctly structured form page."""

    def test_get_returns_200_for_authenticated_user(self, auth_client):
        """
        GET /expenses/add with a valid session must return HTTP 200.
        """
        # Act
        response = auth_client.get(ADD_EXPENSE_URL)

        # Assert
        assert response.status_code == 200

    def test_get_response_contains_amount_field(self, auth_client):
        """
        The rendered form must contain an input for the expense amount.
        """
        response = auth_client.get(ADD_EXPENSE_URL)

        assert b'name="amount"' in response.data

    def test_get_response_contains_category_field(self, auth_client):
        """
        The rendered form must contain a category selector.
        """
        response = auth_client.get(ADD_EXPENSE_URL)

        assert b'name="category"' in response.data

    def test_get_response_contains_date_field(self, auth_client):
        """
        The rendered form must contain an input for the expense date.
        """
        response = auth_client.get(ADD_EXPENSE_URL)

        assert b'name="date"' in response.data

    def test_get_response_contains_description_field(self, auth_client):
        """
        The rendered form must contain an input or textarea for the
        optional description.
        """
        response = auth_client.get(ADD_EXPENSE_URL)

        assert b'name="description"' in response.data

    def test_get_response_lists_all_valid_categories(self, auth_client):
        """
        Every allowed category must appear as an option in the form so
        the user can choose any of them.
        """
        response = auth_client.get(ADD_EXPENSE_URL)

        for category in VALID_CATEGORIES:
            assert category.encode() in response.data, (
                f"Category '{category}' missing from GET form"
            )


# ================================================================== #
# POST — HAPPY PATH                                                   #
# ================================================================== #

class TestPostHappyPath:
    """Valid submissions must insert the expense and redirect correctly."""

    def test_valid_full_submission_redirects_to_profile(
        self, app, isolated_db, monkeypatch
    ):
        """
        A POST with all valid fields must return 302 and redirect to /profile.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = isolated_db["user_id"]
            sess["user_name"] = "Test User"

        # Act
        response = test_client.post(ADD_EXPENSE_URL, data=VALID_FORM)

        # Assert
        assert response.status_code == 302
        assert "/profile" in response.headers["Location"]

    def test_valid_full_submission_inserts_row_in_db(
        self, app, isolated_db, monkeypatch
    ):
        """
        After a successful POST, exactly one expense row must exist in the
        DB belonging to the authenticated user with the submitted values.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        user_id = isolated_db["user_id"]
        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = user_id
            sess["user_name"] = "Test User"

        # Arrange — confirm no expenses exist yet
        assert _count_expenses(isolated_db, user_id) == 0

        # Act
        test_client.post(ADD_EXPENSE_URL, data=VALID_FORM)

        # Assert — one row was inserted with the correct values
        expenses = _fetch_expenses(isolated_db, user_id)
        assert len(expenses) == 1
        row = expenses[0]
        assert row["user_id"]  == user_id
        assert row["amount"]   == pytest.approx(42.50)
        assert row["category"] == "Food"
        assert row["date"]     == "2026-06-01"
        assert row["description"] == "Test lunch"

    def test_flash_message_expense_added_appears_after_redirect(
        self, app, isolated_db, monkeypatch
    ):
        """
        After a successful POST, the flash message "Expense added." must
        be visible on the /profile page the user is redirected to.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = isolated_db["user_id"]
            sess["user_name"] = "Test User"

        # Act — follow the redirect so the flash renders on /profile
        response = test_client.post(
            ADD_EXPENSE_URL, data=VALID_FORM, follow_redirects=True
        )

        # Assert
        assert b"Expense added." in response.data

    def test_valid_submission_without_description_succeeds(
        self, app, isolated_db, monkeypatch
    ):
        """
        Description is optional. A POST without the description field must
        still succeed: 302 redirect and one DB row inserted.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        user_id = isolated_db["user_id"]
        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = user_id
            sess["user_name"] = "Test User"

        form_without_description = {
            "amount":   "15.00",
            "category": "Transport",
            "date":     "2026-06-02",
        }

        # Act
        response = test_client.post(ADD_EXPENSE_URL, data=form_without_description)

        # Assert redirect
        assert response.status_code == 302
        assert "/profile" in response.headers["Location"]

        # Assert DB row exists
        expenses = _fetch_expenses(isolated_db, user_id)
        assert len(expenses) == 1
        assert expenses[0]["description"] is None

    def test_valid_submission_with_empty_description_succeeds(
        self, app, isolated_db, monkeypatch
    ):
        """
        An explicitly empty description string must be treated the same as
        absent — the submission must succeed and the DB row must be inserted.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        user_id = isolated_db["user_id"]
        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = user_id
            sess["user_name"] = "Test User"

        form_empty_description = {
            "amount":      "10.00",
            "category":    "Other",
            "date":        "2026-06-03",
            "description": "",
        }

        # Act
        response = test_client.post(ADD_EXPENSE_URL, data=form_empty_description)

        # Assert
        assert response.status_code == 302
        assert _count_expenses(isolated_db, user_id) == 1


# ================================================================== #
# POST — VALIDATION ERRORS                                            #
# ================================================================== #

class TestPostValidationErrors:
    """
    Each invalid submission must re-render the form (200) with an error
    message and must NOT write any row to the database.
    """

    def test_blank_amount_returns_200_with_error(self, auth_client):
        """
        Submitting an empty string for amount must re-render the form
        with an error — not redirect.
        """
        form = {**VALID_FORM, "amount": ""}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200
        assert b"amount" in response.data.lower() or b"error" in response.data.lower()

    def test_blank_amount_does_not_write_to_db(
        self, app, isolated_db, monkeypatch
    ):
        """
        A blank amount must leave the expenses table untouched.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        user_id = isolated_db["user_id"]
        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = user_id
            sess["user_name"] = "Test User"

        test_client.post(ADD_EXPENSE_URL, data={**VALID_FORM, "amount": ""})

        assert _count_expenses(isolated_db, user_id) == 0

    def test_missing_amount_returns_200_with_error(self, auth_client):
        """
        A POST body with no 'amount' key at all must re-render the form.
        """
        form = {k: v for k, v in VALID_FORM.items() if k != "amount"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200

    def test_non_numeric_amount_returns_200_with_error(self, auth_client):
        """
        A non-numeric amount (e.g. "abc") must re-render the form with
        a validation error.
        """
        form = {**VALID_FORM, "amount": "abc"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200

    def test_non_numeric_amount_does_not_write_to_db(
        self, app, isolated_db, monkeypatch
    ):
        """
        A non-numeric amount must leave the expenses table untouched.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        user_id = isolated_db["user_id"]
        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = user_id
            sess["user_name"] = "Test User"

        test_client.post(ADD_EXPENSE_URL, data={**VALID_FORM, "amount": "abc"})

        assert _count_expenses(isolated_db, user_id) == 0

    def test_zero_amount_returns_200_with_error(self, auth_client):
        """
        An amount of exactly zero must be rejected — the spec requires a
        strictly positive number.
        """
        form = {**VALID_FORM, "amount": "0"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200

    def test_zero_amount_does_not_write_to_db(
        self, app, isolated_db, monkeypatch
    ):
        """
        Zero amount must leave the expenses table untouched.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        user_id = isolated_db["user_id"]
        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = user_id
            sess["user_name"] = "Test User"

        test_client.post(ADD_EXPENSE_URL, data={**VALID_FORM, "amount": "0"})

        assert _count_expenses(isolated_db, user_id) == 0

    def test_negative_amount_returns_200_with_error(self, auth_client):
        """
        A negative amount must be rejected — expenses cannot have negative
        values.
        """
        form = {**VALID_FORM, "amount": "-10"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200

    def test_negative_amount_does_not_write_to_db(
        self, app, isolated_db, monkeypatch
    ):
        """
        A negative amount must leave the expenses table untouched.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        user_id = isolated_db["user_id"]
        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = user_id
            sess["user_name"] = "Test User"

        test_client.post(ADD_EXPENSE_URL, data={**VALID_FORM, "amount": "-10"})

        assert _count_expenses(isolated_db, user_id) == 0

    def test_invalid_category_returns_200_with_error(self, auth_client):
        """
        A category value not in the allowed list (e.g. "Gambling") must
        be rejected and the form re-rendered.
        """
        form = {**VALID_FORM, "category": "Gambling"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200

    def test_invalid_category_does_not_write_to_db(
        self, app, isolated_db, monkeypatch
    ):
        """
        An invalid category must leave the expenses table untouched.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        user_id = isolated_db["user_id"]
        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = user_id
            sess["user_name"] = "Test User"

        test_client.post(ADD_EXPENSE_URL, data={**VALID_FORM, "category": "Gambling"})

        assert _count_expenses(isolated_db, user_id) == 0

    def test_missing_category_returns_200_with_error(self, auth_client):
        """
        A POST body with no 'category' key must be rejected — category is
        a required field.
        """
        form = {k: v for k, v in VALID_FORM.items() if k != "category"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200

    def test_missing_date_returns_200_with_error(self, auth_client):
        """
        A POST body with no 'date' key must be rejected — date is required.
        """
        form = {k: v for k, v in VALID_FORM.items() if k != "date"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200

    def test_missing_date_does_not_write_to_db(
        self, app, isolated_db, monkeypatch
    ):
        """
        A missing date must leave the expenses table untouched.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        user_id = isolated_db["user_id"]
        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = user_id
            sess["user_name"] = "Test User"

        form = {k: v for k, v in VALID_FORM.items() if k != "date"}
        test_client.post(ADD_EXPENSE_URL, data=form)

        assert _count_expenses(isolated_db, user_id) == 0

    def test_malformed_date_dd_mm_yyyy_returns_200_with_error(self, auth_client):
        """
        A date in DD-MM-YYYY format is not the accepted YYYY-MM-DD format
        and must be rejected with a validation error.
        """
        form = {**VALID_FORM, "date": "31-12-2026"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200

    def test_malformed_date_freetext_returns_200_with_error(self, auth_client):
        """
        A date supplied as free text (e.g. "not-a-date") must be rejected.
        """
        form = {**VALID_FORM, "date": "not-a-date"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200

    def test_malformed_date_does_not_write_to_db(
        self, app, isolated_db, monkeypatch
    ):
        """
        A malformed date must leave the expenses table untouched.
        """
        import database.db as db_module
        monkeypatch.setattr(db_module, "get_db", isolated_db["conn_factory"])

        user_id = isolated_db["user_id"]
        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess["user_id"]   = user_id
            sess["user_name"] = "Test User"

        test_client.post(ADD_EXPENSE_URL, data={**VALID_FORM, "date": "not-a-date"})

        assert _count_expenses(isolated_db, user_id) == 0

    def test_error_response_contains_error_text(self, auth_client):
        """
        When a validation error occurs the response body must contain
        some error indication — the spec requires re-rendering with an
        error message (not a silent failure).
        We use a zero amount to trigger a predictable error.
        """
        form = {**VALID_FORM, "amount": "0"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        # The word "error" or the specific message should appear in the page
        body_lower = response.data.lower()
        assert b"error" in body_lower or b"must be" in body_lower or b"positive" in body_lower


# ================================================================== #
# POST — FORM VALUE PRESERVATION ON VALIDATION ERROR                 #
# ================================================================== #

class TestFormValuePreservation:
    """
    When a validation error occurs the form must be re-rendered with the
    previously entered values still populated so the user does not lose
    their input.
    """

    def test_entered_amount_preserved_when_category_is_invalid(self, auth_client):
        """
        After an invalid-category error, the amount the user typed must
        still appear in the re-rendered form.
        """
        form = {**VALID_FORM, "category": "Gambling"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200
        assert b"42.50" in response.data

    def test_entered_date_preserved_when_amount_is_invalid(self, auth_client):
        """
        After a non-numeric amount error, the date the user typed must
        still appear in the re-rendered form.
        """
        form = {**VALID_FORM, "amount": "abc"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200
        assert b"2026-06-01" in response.data

    def test_entered_description_preserved_when_date_is_invalid(self, auth_client):
        """
        After a malformed-date error, the description the user typed must
        still appear in the re-rendered form.
        """
        form = {**VALID_FORM, "date": "not-a-date"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200
        assert b"Test lunch" in response.data

    def test_entered_category_preserved_when_amount_is_zero(self, auth_client):
        """
        After a zero-amount error, the selected category must still appear
        in the re-rendered form.
        """
        form = {**VALID_FORM, "amount": "0"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200
        assert b"Food" in response.data

    def test_entered_amount_preserved_when_date_is_malformed(self, auth_client):
        """
        After a malformed-date error, the amount the user typed must
        still appear in the re-rendered form.
        """
        form = {**VALID_FORM, "date": "31-12-2026"}

        response = auth_client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200
        assert b"42.50" in response.data
