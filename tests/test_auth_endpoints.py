"""Tests end-to-end para los endpoints /auth/*.

Usa la fixture `client` (TestClient con get_db sobreescrito hacia la sesión
en memoria). El lifespan del grafo del coach nunca se dispara porque
TestClient se instancia sin entrar en el context manager async.

Estructura AAA en todos los tests.
"""

from __future__ import annotations


def _register(client, email: str = "user@example.com", password: str = "password123"):
    return client.post("/auth/register", json={"email": email, "password": password})


def _login(client, email: str = "user@example.com", password: str = "password123"):
    return client.post("/auth/login", json={"email": email, "password": password})


class TestRegisterAndLogin:
    def test_register_then_login_succeeds(self, client):
        # Arrange
        _register(client)

        # Act
        resp = _login(client)

        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_register_returns_201_with_user_body(self, client):
        # Arrange + Act
        resp = _register(client, email="fresh@example.com")

        # Assert
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "fresh@example.com"
        assert body["has_profile"] is False
        assert "password" not in body
        assert "password_hash" not in body

    def test_register_duplicate_email_returns_409(self, client):
        # Arrange
        _register(client, email="dup@example.com")

        # Act
        resp = _register(client, email="dup@example.com")

        # Assert
        assert resp.status_code == 409

    def test_login_wrong_password_returns_401(self, client):
        # Arrange
        _register(client, email="wrongpw@example.com", password="correctpassword")

        # Act
        resp = _login(client, email="wrongpw@example.com", password="incorrectpassword")

        # Assert
        assert resp.status_code == 401

    def test_register_password_too_long_returns_422(self, client):
        # Arrange
        too_long_password = "a" * 129

        # Act
        resp = _register(client, email="toolong@example.com", password=too_long_password)

        # Assert
        assert resp.status_code == 422

    def test_login_password_too_long_returns_422(self, client):
        # Arrange
        too_long_password = "a" * 129

        # Act
        resp = _login(client, email="whoever@example.com", password=too_long_password)

        # Assert
        assert resp.status_code == 422

    def test_login_unknown_email_and_wrong_password_return_same_status_and_body(self, client):
        # Arrange — un email registrado (para probar password incorrecta) y otro que no existe
        _register(client, email="known@example.com", password="correctpassword")

        # Act
        resp_unknown_email = _login(client, email="nobody@example.com", password="whatever123")
        resp_wrong_password = _login(
            client, email="known@example.com", password="incorrectpassword"
        )

        # Assert — mismo status y mismo cuerpo: no se revela si el email existe
        assert resp_unknown_email.status_code == resp_wrong_password.status_code == 401
        assert resp_unknown_email.json() == resp_wrong_password.json()


class TestRefreshRotation:
    def test_refresh_rotates_and_reusing_old_token_returns_401(self, client):
        # Arrange
        _register(client, email="rotate@example.com")
        tokens = _login(client, email="rotate@example.com").json()
        old_refresh = tokens["refresh_token"]

        # Act
        first_refresh_resp = client.post("/auth/refresh", json={"refresh_token": old_refresh})
        reuse_resp = client.post("/auth/refresh", json={"refresh_token": old_refresh})

        # Assert
        assert first_refresh_resp.status_code == 200
        assert reuse_resp.status_code == 401

    def test_refresh_with_unknown_token_returns_401(self, client):
        # Arrange + Act
        resp = client.post("/auth/refresh", json={"refresh_token": "no-such-token"})

        # Assert
        assert resp.status_code == 401


class TestLogout:
    def test_logout_revokes_refresh_token(self, client):
        # Arrange
        _register(client, email="logout@example.com")
        tokens = _login(client, email="logout@example.com").json()
        refresh_token = tokens["refresh_token"]

        # Act
        logout_resp = client.post("/auth/logout", json={"refresh_token": refresh_token})
        reuse_resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        # Assert
        assert logout_resp.status_code == 200
        assert reuse_resp.status_code == 401

    def test_logout_with_unknown_token_still_returns_200(self, client):
        # Arrange + Act
        resp = client.post("/auth/logout", json={"refresh_token": "never-issued"})

        # Assert — logout es idempotente
        assert resp.status_code == 200


class TestMe:
    def test_me_without_token_returns_401(self, client):
        # Arrange + Act
        resp = client.get("/auth/me")

        # Assert
        assert resp.status_code == 401

    def test_me_with_valid_token_returns_user_data(self, client):
        # Arrange
        _register(client, email="me@example.com")
        tokens = _login(client, email="me@example.com").json()
        access_token = tokens["access_token"]

        # Act
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})

        # Assert
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "me@example.com"
        assert body["has_profile"] is False
        assert "id" in body

    def test_me_with_invalid_token_returns_401(self, client):
        # Arrange + Act
        resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})

        # Assert
        assert resp.status_code == 401
