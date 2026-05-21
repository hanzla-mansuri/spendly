import pytest
from app import app as flask_app
from database.db import init_db


@pytest.fixture
def app():
    flask_app.config.update({"TESTING": True, "SECRET_KEY": "test-secret"})
    with flask_app.app_context():
        init_db()
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client, app):
    with app.app_context():
        from database.db import seed_db
        seed_db()
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    return client
