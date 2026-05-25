"""
tests/test_date_filter.py

Behaviour tests for the Step 6 date-filter feature on GET /profile.

Spec under test
---------------
- No params          → all-time unfiltered view
- Valid range        → only expenses within that inclusive range are included
- Empty range        → ₹0.00 total, 0 transactions, empty breakdown, no crash
- date_from > date_to → flash "Start date must be before end date.", fall back to all-time
- Malformed date     → silently ignored, fall back to all-time
- Only date_from     → lower-bound filter only, no crash
- Only date_to       → upper-bound filter only, no crash
- Unauthenticated    → 302 redirect to /login
- ₹ symbol           → always present in response regardless of filter

Seed data summary (all May 2026, total = ₹396.24, 8 transactions):
    2026-05-01  Food          ₹42.50
    2026-05-03  Transport     ₹18.00
    2026-05-05  Bills         ₹120.00
    2026-05-08  Health        ₹55.00
    2026-05-10  Entertainment ₹30.00
    2026-05-14  Shopping      ₹89.99
    2026-05-17  Food          ₹15.75
    2026-05-20  Other         ₹25.00
"""

import pytest
from app import app as flask_app
from database.db import init_db, seed_db


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def app():
    """
    Provide a TESTING-mode Flask app backed by the shared file DB.
    init_db() is idempotent — safe to call every test run.
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
def auth_client(client, app):
    """
    Authenticated test client.
    seed_db() is idempotent — skips insertion if demo user already exists.
    Logs in as demo@spendly.com / demo123.
    """
    with app.app_context():
        seed_db()
    client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
    )
    return client


# ------------------------------------------------------------------ #
# Helper                                                              #
# ------------------------------------------------------------------ #

def _get_profile(client, params=None):
    """GET /profile with optional query-string dict. Returns the response."""
    url = "/profile"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    return client.get(url)


# ------------------------------------------------------------------ #
# Test 1 — No params → all-time unfiltered view                       #
# ------------------------------------------------------------------ #

def test_no_params_returns_200_with_all_time_data(auth_client):
    """
    GET /profile with no query params must return HTTP 200 and include
    the all-time total (₹396.24) and all 8 seed transactions.
    """
    # Act
    response = _get_profile(auth_client)

    # Assert
    assert response.status_code == 200
    assert b"\xe2\x82\xb9396.24" in response.data  # ₹396.24 (UTF-8 bytes for ₹)


def test_no_params_shows_all_eight_transactions(auth_client):
    """
    The all-time view must surface all 8 seed transactions.
    Verified by checking each unique seed description appears in the page.
    """
    seed_descriptions = [
        b"Grocery run",
        b"Weekly bus pass",
        b"Electricity bill",
        b"Pharmacy",
        b"Streaming subscriptions",
        b"New shoes",
        b"Lunch at cafe",
        b"Miscellaneous",
    ]

    response = _get_profile(auth_client)

    assert response.status_code == 200
    for desc in seed_descriptions:
        assert desc in response.data, f"Expected description not found: {desc!r}"


# ------------------------------------------------------------------ #
# Test 2 — Valid date range covering all seed data (May 2026)         #
# ------------------------------------------------------------------ #

def test_valid_may_range_returns_all_seed_expenses(auth_client):
    """
    A range of 2026-05-01 to 2026-05-31 is inclusive of every seed
    expense, so the total must still be ₹396.24 with 8 transactions.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "2026-05-01", "date_to": "2026-05-31"},
    )

    assert response.status_code == 200
    assert b"\xe2\x82\xb9396.24" in response.data


def test_valid_narrow_range_returns_only_matching_expenses(auth_client):
    """
    A range of 2026-05-01 to 2026-05-05 must include only the first
    three seed expenses (Food ₹42.50, Transport ₹18.00, Bills ₹120.00)
    and exclude later ones (e.g. Health ₹55.00 on 2026-05-08).
    Total in this window = ₹180.50.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "2026-05-01", "date_to": "2026-05-05"},
    )

    assert response.status_code == 200
    assert b"\xe2\x82\xb9180.50" in response.data
    # Expense outside the range must not appear
    assert b"Pharmacy" not in response.data


# ------------------------------------------------------------------ #
# Test 3 — Range covering no expenses → zero state, no crash          #
# ------------------------------------------------------------------ #

def test_empty_range_returns_zero_total(auth_client):
    """
    A date range with no matching seed expenses must show ₹0.00 total
    and must not crash (HTTP 200 expected).
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "2025-01-01", "date_to": "2025-01-31"},
    )

    assert response.status_code == 200
    assert b"\xe2\x82\xb90.00" in response.data  # ₹0.00


def test_empty_range_shows_no_transactions(auth_client):
    """
    When no expenses match the date range, none of the seed descriptions
    should appear in the rendered page.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "2025-01-01", "date_to": "2025-01-31"},
    )

    assert response.status_code == 200
    # Spot-check a couple of seed descriptions that must be absent
    assert b"Grocery run" not in response.data
    assert b"Electricity bill" not in response.data


# ------------------------------------------------------------------ #
# Test 4 — date_from > date_to → flash error, fall back to all-time   #
# ------------------------------------------------------------------ #

def test_inverted_range_returns_200(auth_client):
    """
    Submitting date_from > date_to must not crash; the route returns 200.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "2026-05-31", "date_to": "2026-05-01"},
    )

    assert response.status_code == 200


def test_inverted_range_flashes_error_message(auth_client):
    """
    When date_from > date_to, the response must contain the exact flash
    message: "Start date must be before end date."
    Flask flashes are rendered into the page on the next request when
    using the test client with follow_redirects; since the profile route
    renders the same page (not a redirect), the flash appears immediately.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "2026-05-31", "date_to": "2026-05-01"},
    )

    assert b"Start date must be before end date." in response.data


def test_inverted_range_falls_back_to_all_time_data(auth_client):
    """
    After an inverted range, the route must display all-time data
    (both dates are treated as absent), so the full ₹396.24 total appears.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "2026-05-31", "date_to": "2026-05-01"},
    )

    assert response.status_code == 200
    assert b"\xe2\x82\xb9396.24" in response.data


# ------------------------------------------------------------------ #
# Test 5 — Malformed date → silently ignored, all-time data shown     #
# ------------------------------------------------------------------ #

def test_malformed_date_from_returns_200(auth_client):
    """
    A non-ISO value for date_from (e.g. "not-a-date") must not crash
    the route; HTTP 200 is expected.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "not-a-date"},
    )

    assert response.status_code == 200


def test_malformed_date_from_falls_back_to_all_time(auth_client):
    """
    A malformed date_from must be silently ignored, so the all-time
    total (₹396.24) must be visible — no partial or zero result.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "not-a-date"},
    )

    assert b"\xe2\x82\xb9396.24" in response.data


def test_malformed_date_to_returns_200(auth_client):
    """
    A non-ISO value for date_to must not crash the route.
    """
    response = _get_profile(
        auth_client,
        params={"date_to": "99/99/9999"},
    )

    assert response.status_code == 200


def test_both_dates_malformed_falls_back_to_all_time(auth_client):
    """
    When both date params are malformed, the all-time view must be shown.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "yesterday", "date_to": "tomorrow"},
    )

    assert response.status_code == 200
    assert b"\xe2\x82\xb9396.24" in response.data


# ------------------------------------------------------------------ #
# Test 6 — Only date_from supplied → lower-bound filter, no crash     #
# ------------------------------------------------------------------ #

def test_only_date_from_returns_200(auth_client):
    """
    Supplying only date_from must not crash the route.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "2026-05-10"},
    )

    assert response.status_code == 200


def test_only_date_from_excludes_earlier_expenses(auth_client):
    """
    With only date_from=2026-05-10, expenses before 2026-05-10 must be
    excluded.  The "Grocery run" expense (2026-05-01) must not appear.
    Expenses on or after 2026-05-10 must still appear
    (e.g. "Streaming subscriptions" on 2026-05-10).
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "2026-05-10"},
    )

    assert b"Grocery run" not in response.data
    assert b"Streaming subscriptions" in response.data


# ------------------------------------------------------------------ #
# Test 7 — Only date_to supplied → upper-bound filter, no crash       #
# ------------------------------------------------------------------ #

def test_only_date_to_returns_200(auth_client):
    """
    Supplying only date_to must not crash the route.
    """
    response = _get_profile(
        auth_client,
        params={"date_to": "2026-05-05"},
    )

    assert response.status_code == 200


def test_only_date_to_excludes_later_expenses(auth_client):
    """
    With only date_to=2026-05-05, expenses after 2026-05-05 must be
    excluded.  "Pharmacy" (2026-05-08) must not appear.
    Expenses on or before 2026-05-05 must still appear
    (e.g. "Electricity bill" on 2026-05-05).
    """
    response = _get_profile(
        auth_client,
        params={"date_to": "2026-05-05"},
    )

    assert b"Pharmacy" not in response.data
    assert b"Electricity bill" in response.data


# ------------------------------------------------------------------ #
# Test 8 — Unauthenticated request → 302 redirect to /login           #
# ------------------------------------------------------------------ #

def test_unauthenticated_request_redirects_to_login(client):
    """
    A GET /profile request without an active session must return HTTP 302
    and redirect to /login.  The client fixture is NOT authenticated.
    """
    response = _get_profile(client)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_unauthenticated_request_with_date_params_still_redirects(client):
    """
    Date params must not bypass the authentication check; an unauthenticated
    request with valid date params must still redirect to /login.
    """
    response = _get_profile(
        client,
        params={"date_from": "2026-05-01", "date_to": "2026-05-31"},
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ------------------------------------------------------------------ #
# Test 9 — ₹ symbol present regardless of filter                      #
# ------------------------------------------------------------------ #

def test_rupee_symbol_present_with_no_filter(auth_client):
    """
    The ₹ symbol must appear in the response for an all-time (no-filter) view.
    """
    response = _get_profile(auth_client)

    assert response.status_code == 200
    # ₹ is U+20B9, encoded as 0xE2 0x82 0xB9 in UTF-8
    assert "₹".encode("utf-8") in response.data


def test_rupee_symbol_present_with_valid_filter(auth_client):
    """
    The ₹ symbol must appear in the response when a valid date range is applied.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "2026-05-01", "date_to": "2026-05-31"},
    )

    assert response.status_code == 200
    assert "₹".encode("utf-8") in response.data


def test_rupee_symbol_present_on_empty_range(auth_client):
    """
    Even when a date range matches zero expenses (showing ₹0.00), the ₹
    symbol must still be present in the rendered page.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "2025-01-01", "date_to": "2025-01-31"},
    )

    assert response.status_code == 200
    assert "₹".encode("utf-8") in response.data


def test_rupee_symbol_present_on_malformed_date(auth_client):
    """
    A malformed date param triggers the all-time fallback; the ₹ symbol
    must still appear in the response.
    """
    response = _get_profile(
        auth_client,
        params={"date_from": "bad-input"},
    )

    assert response.status_code == 200
    assert "₹".encode("utf-8") in response.data
