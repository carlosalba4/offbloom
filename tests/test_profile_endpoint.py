"""Tests para los endpoints de perfil persistente: GET/PUT /me/profile.

Usa la fixture `client` (TestClient con get_db sobreescrito hacia la sesión
en memoria) y el helper `auth_headers` para autenticar. El lifespan del grafo
del coach nunca se dispara porque TestClient se instancia sin entrar en el
context manager async.

Estructura AAA en todos los tests.
"""

from __future__ import annotations

from coach.db.models.profile import Profile
from tests.conftest import auth_headers


def _profile_payload() -> dict:
    return {
        "goals": ["reducir tiempo de pantalla"],
        "interests": ["lectura", "senderismo"],
        "constraints": {
            "available_minutes": 45,
            "energy": "MEDIUM",
            "place": "HOME",
            "social": "SOLO",
        },
        "lang": "ES",
    }


class TestPutThenGetProfile:
    def test_put_creates_profile_and_get_retrieves_it_identically(self, client):
        # Arrange
        headers = auth_headers(client, email="onboard@example.com")
        payload = _profile_payload()

        # Act
        put_resp = client.put("/me/profile", json=payload, headers=headers)
        get_resp = client.get("/me/profile", headers=headers)

        # Assert
        assert put_resp.status_code == 200
        assert get_resp.status_code == 200
        assert get_resp.json() == put_resp.json()
        assert get_resp.json()["goals"] == payload["goals"]
        assert get_resp.json()["interests"] == payload["interests"]
        assert get_resp.json()["constraints"] == payload["constraints"]

    def test_get_profile_without_onboarding_returns_404(self, client):
        # Arrange
        headers = auth_headers(client, email="no-onboarding@example.com")

        # Act
        resp = client.get("/me/profile", headers=headers)

        # Assert
        assert resp.status_code == 404


class TestUpsertIdempotency:
    def test_put_twice_updates_without_duplicating(self, client, db_session):
        # Arrange
        headers = auth_headers(client, email="upsert@example.com")
        first_payload = _profile_payload()
        second_payload = _profile_payload()
        second_payload["goals"] = ["dormir mejor"]
        second_payload["interests"] = ["yoga"]

        # Act
        client.put("/me/profile", json=first_payload, headers=headers)
        second_resp = client.put("/me/profile", json=second_payload, headers=headers)

        # Assert — respuesta refleja los valores nuevos
        assert second_resp.status_code == 200
        assert second_resp.json()["goals"] == ["dormir mejor"]
        assert second_resp.json()["interests"] == ["yoga"]

        # Assert — un único Profile en DB, con los valores actualizados
        profiles = db_session.query(Profile).all()
        assert len(profiles) == 1
        assert profiles[0].goals == ["dormir mejor"]
        assert profiles[0].interests == ["yoga"]


class TestAuthRequired:
    def test_get_profile_without_token_returns_401(self, client):
        # Arrange + Act
        resp = client.get("/me/profile")

        # Assert
        assert resp.status_code == 401

    def test_put_profile_without_token_returns_401(self, client):
        # Arrange + Act
        resp = client.put("/me/profile", json=_profile_payload())

        # Assert
        assert resp.status_code == 401
