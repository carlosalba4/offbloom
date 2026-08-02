"""Tests para la baja de cuenta: DELETE /me.

CI-safe: no llama al coach ni a Ollama. Los datos del usuario (perfil, plan,
progreso y refresh tokens) se siembran directamente en la sesión, no a través
de POST /plans.

Estructura AAA en todos los tests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from coach.auth.security import hash_refresh_token
from coach.config import settings
from coach.db.enums import ActivityProgressStatus, PlanStatus
from coach.db.mappers import domain_to_profile_dict
from coach.db.models.activity_progress import ActivityProgress
from coach.db.models.plan import Plan
from coach.db.models.profile import Profile
from coach.db.models.refresh_token import RefreshToken
from coach.db.models.user import User
from tests.conftest import auth_headers, make_profile, make_usage

PASSWORD = "password123"


def _get_user_id(db_session: Session, email: str) -> str:
    """Recupera el id del usuario ya autenticado a partir de su email."""
    user = db_session.query(User).filter(User.email == email.lower()).first()
    assert user is not None
    return user.id


def _seed_user_data(db_session: Session, user_id: str) -> None:
    """Siembra perfil, plan, progreso y un refresh token extra para un usuario.

    El login ya crea un refresh token; este segundo comprueba que la cascada
    se lleva TODOS, no solo el de la sesión en curso.
    """
    profile_data = domain_to_profile_dict(make_profile())
    db_session.add(
        Profile(
            user_id=user_id,
            goals=profile_data["goals"],
            interests=profile_data["interests"],
            constraints=profile_data["constraints"],
            lang=profile_data["lang"],
        )
    )

    plan = Plan(
        user_id=user_id,
        status=PlanStatus.GENERATED,
        input_profile_snapshot=make_profile().model_dump(mode="json"),
        input_usage_snapshot=make_usage().model_dump(mode="json"),
        plan={"weekly_focus": "foco", "days": []},
        activities=[],
        derivation=None,
        errors=[],
        created_at=datetime.now(UTC),
    )
    db_session.add(plan)
    db_session.flush()

    db_session.add(
        ActivityProgress(
            plan_id=plan.id,
            user_id=user_id,
            activity_index=0,
            status=ActivityProgressStatus.DONE,
        )
    )
    db_session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(f"extra-token-{user_id}"),
            expires_at=datetime.now(UTC) + timedelta(days=14),
        )
    )
    db_session.commit()


def _counts(db_session: Session, user_id: str) -> dict[str, int]:
    """Cuenta las filas de las cinco tablas que pertenecen a un usuario."""
    return {
        "users": db_session.query(User).filter(User.id == user_id).count(),
        "profiles": db_session.query(Profile).filter(Profile.user_id == user_id).count(),
        "plans": db_session.query(Plan).filter(Plan.user_id == user_id).count(),
        "activity_progresses": db_session.query(ActivityProgress)
        .filter(ActivityProgress.user_id == user_id)
        .count(),
        "refresh_tokens": db_session.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id)
        .count(),
    }


class TestDeleteAccountSuccess:
    def test_correct_password_deletes_user_and_all_owned_rows(
        self, client: TestClient, db_session: Session
    ) -> None:
        # Arrange — usuario autenticado con perfil, plan, progreso y dos refresh tokens
        email = "delete-me@example.com"
        headers = auth_headers(client, email=email, password=PASSWORD)
        user_id = _get_user_id(db_session, email)
        _seed_user_data(db_session, user_id)
        assert _counts(db_session, user_id) == {
            "users": 1,
            "profiles": 1,
            "plans": 1,
            "activity_progresses": 1,
            "refresh_tokens": 2,
        }

        # Act
        resp = client.request("DELETE", "/me", headers=headers, json={"password": PASSWORD})

        # Assert — 204 sin cuerpo y las cinco tablas a cero para ese usuario
        assert resp.status_code == 204
        assert resp.content == b""
        assert _counts(db_session, user_id) == {
            "users": 0,
            "profiles": 0,
            "plans": 0,
            "activity_progresses": 0,
            "refresh_tokens": 0,
        }

    def test_deletion_clears_the_refresh_cookie(
        self, client: TestClient, db_session: Session
    ) -> None:
        # Arrange
        email = "cookie-clear@example.com"
        headers = auth_headers(client, email=email, password=PASSWORD)
        assert client.cookies.get(settings.cookie_refresh_name) is not None

        # Act
        resp = client.request("DELETE", "/me", headers=headers, json={"password": PASSWORD})

        # Assert — el 204 trae el Set-Cookie que vacía la cookie del navegador
        assert resp.status_code == 204
        assert client.cookies.get(settings.cookie_refresh_name) is None


class TestDeleteAccountIsolation:
    def test_deleting_one_account_leaves_other_users_untouched(
        self, client: TestClient, db_session: Session
    ) -> None:
        # Arrange — dos usuarios, ambos con el juego completo de datos
        headers_a = auth_headers(client, email="isolation-a@example.com", password=PASSWORD)
        auth_headers(client, email="isolation-b@example.com", password=PASSWORD)
        user_a_id = _get_user_id(db_session, "isolation-a@example.com")
        user_b_id = _get_user_id(db_session, "isolation-b@example.com")
        _seed_user_data(db_session, user_a_id)
        _seed_user_data(db_session, user_b_id)
        counts_b_before = _counts(db_session, user_b_id)

        # Act — A se da de baja
        resp = client.request("DELETE", "/me", headers=headers_a, json={"password": PASSWORD})

        # Assert — A desaparece, B queda exactamente igual
        assert resp.status_code == 204
        assert _counts(db_session, user_a_id)["users"] == 0
        assert _counts(db_session, user_b_id) == counts_b_before


class TestDeleteAccountWrongPassword:
    def test_wrong_password_returns_403_and_deletes_nothing(
        self, client: TestClient, db_session: Session
    ) -> None:
        # Arrange
        email = "wrong-password@example.com"
        headers = auth_headers(client, email=email, password=PASSWORD)
        user_id = _get_user_id(db_session, email)
        _seed_user_data(db_session, user_id)
        counts_before = _counts(db_session, user_id)

        # Act
        resp = client.request(
            "DELETE", "/me", headers=headers, json={"password": "contraseña-incorrecta"}
        )

        # Assert — 403 (no 401: el Bearer es válido) y ni una fila borrada
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Credenciales inválidas"
        assert _counts(db_session, user_id) == counts_before


class TestDeleteAccountAuthRequired:
    def test_without_token_returns_401(self, client: TestClient) -> None:
        # Arrange / Act — sin cabecera Authorization
        resp = client.request("DELETE", "/me", json={"password": PASSWORD})

        # Assert
        assert resp.status_code == 401

    def test_without_token_does_not_delete_anything(
        self, client: TestClient, db_session: Session
    ) -> None:
        # Arrange — el usuario existe, pero la petición va sin token
        email = "no-token@example.com"
        auth_headers(client, email=email, password=PASSWORD)
        user_id = _get_user_id(db_session, email)
        _seed_user_data(db_session, user_id)
        counts_before = _counts(db_session, user_id)

        # Act
        resp = client.request("DELETE", "/me", json={"password": PASSWORD})

        # Assert
        assert resp.status_code == 401
        assert _counts(db_session, user_id) == counts_before


class TestDeleteAccountInvalidatesSession:
    def test_previous_refresh_token_no_longer_works(
        self, client: TestClient, db_session: Session
    ) -> None:
        # Arrange — captura el refresh en claro ANTES de la baja
        email = "session-gone@example.com"
        headers = auth_headers(client, email=email, password=PASSWORD)
        refresh_token = client.cookies.get(settings.cookie_refresh_name)
        assert refresh_token is not None

        # Act — baja y reenvío manual del refresh anterior
        delete_resp = client.request("DELETE", "/me", headers=headers, json={"password": PASSWORD})
        # Cabecera Cookie explícita: el Set-Cookie del 204 ya vació el jar de
        # httpx, así que sin esto el test comprobaría solo que la cookie no se
        # envía, no que la FILA del refresh token haya desaparecido.
        refresh_resp = client.post(
            "/auth/refresh",
            headers={"Cookie": f"{settings.cookie_refresh_name}={refresh_token}"},
        )

        # Assert
        assert delete_resp.status_code == 204
        assert refresh_resp.status_code == 401

    def test_access_token_no_longer_resolves_a_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        # Arrange
        email = "access-gone@example.com"
        headers = auth_headers(client, email=email, password=PASSWORD)

        # Act
        delete_resp = client.request("DELETE", "/me", headers=headers, json={"password": PASSWORD})
        me_resp = client.get("/auth/me", headers=headers)

        # Assert — el token sigue siendo criptográficamente válido, pero su
        # usuario ya no existe: get_current_user devuelve 401.
        assert delete_resp.status_code == 204
        assert me_resp.status_code == 401
