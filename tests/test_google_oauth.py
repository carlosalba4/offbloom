"""Tests del login con Google (OIDC) — endpoints /auth/google/* y AuthService.

Ningún test toca la red: la fixture `google_client` sustituye el cliente OIDC
por un doble que devuelve la identidad que fija cada test, así que la suite es
determinista y no necesita credenciales reales de Google en CI.

Las redirecciones se inspeccionan con `follow_redirects=False`; el nombre de
las cookies sale siempre de `settings`, nunca literal.

Estructura AAA en todos los tests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from coach.api.deps import get_google_client
from coach.auth.google import GoogleIdentity, GoogleOAuthClient, GoogleOAuthError
from coach.config import settings
from coach.db.models.user import User
from tests.conftest import make_google_identity

_CODE = "fake-authorization-code"


def _start_google_login(client: TestClient) -> str:
    """Llama a /auth/google/login y devuelve el `state` emitido.

    Efecto de lado imprescindible: deja la cookie de `state` en el jar del
    TestClient, que es lo que el callback comprobará después.
    """
    resp = client.get("/auth/google/login", follow_redirects=False)
    assert resp.status_code == 302
    query = parse_qs(urlparse(resp.headers["location"]).query)
    return query["state"][0]


def _callback(client: TestClient, **params: str):
    """Ejecuta el callback con un `state` válido, salvo que el test lo sobreescriba."""
    state = _start_google_login(client)
    return client.get(
        "/auth/google/callback",
        params={"state": state, "code": _CODE, **params},
        follow_redirects=False,
    )


def _error_slug(resp) -> str | None:
    """Extrae el `?error=` de la redirección de vuelta al frontend."""
    query = parse_qs(urlparse(resp.headers["location"]).query)
    values = query.get("error")
    return values[0] if values else None


def _register(client: TestClient, email: str, password: str = "password123"):
    return client.post("/auth/register", json={"email": email, "password": password})


# ===========================================================================
# Inicio del flujo
# ===========================================================================


class TestGoogleLoginRedirect:
    def test_login_redirects_to_google_and_sets_state_cookie(self, client, google_client):
        # Arrange
        google_client(identity=make_google_identity())

        # Act
        resp = client.get("/auth/google/login", follow_redirects=False)

        # Assert
        assert resp.status_code == 302
        assert resp.headers["location"].startswith("https://accounts.google.com/")
        assert settings.cookie_oauth_state_name in resp.cookies

    def test_state_in_url_matches_state_in_cookie(self, client, google_client):
        # Arrange
        google_client(identity=make_google_identity())

        # Act
        resp = client.get("/auth/google/login", follow_redirects=False)

        # Assert — el double-submit exige que ambos valores coincidan
        state_in_url = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]
        assert state_in_url == resp.cookies[settings.cookie_oauth_state_name]

    def test_two_logins_produce_different_states(self, client, google_client):
        # Arrange
        google_client(identity=make_google_identity())

        # Act
        first = _start_google_login(client)
        second = _start_google_login(client)

        # Assert — el `state` es aleatorio por intento
        assert first != second


# ===========================================================================
# Resolución de usuario: crear, reutilizar, vincular
# ===========================================================================


class TestGoogleCallbackCreatesUser:
    def test_new_google_user_is_created_and_logged_in(
        self, client: TestClient, db_session: Session, google_client
    ):
        # Arrange
        identity = make_google_identity(sub="sub-new", email="nuevo@example.com")
        google_client(identity=identity)

        # Act
        resp = _callback(client)

        # Assert — redirige al frontend y deja la sesión puesta
        assert resp.status_code == 302
        assert resp.headers["location"] == settings.google_post_login_url
        assert settings.cookie_refresh_name in resp.cookies

        user = db_session.query(User).filter(User.email == "nuevo@example.com").one()
        assert user.google_sub == "sub-new"
        assert user.password_hash is None

    def test_callback_forwards_the_code_to_google(self, client, google_client):
        # Arrange
        fake = google_client(identity=make_google_identity())

        # Act
        _callback(client)

        # Assert
        assert fake.exchanged_code == _CODE

    def test_state_cookie_is_cleared_after_success(self, client, google_client):
        # Arrange
        google_client(identity=make_google_identity())

        # Act
        _callback(client)

        # Assert — la cookie de `state` es de un solo uso
        assert client.cookies.get(settings.cookie_oauth_state_name) is None


class TestGoogleCallbackReusesUser:
    def test_same_sub_logs_into_the_same_user_without_duplicating(
        self, client: TestClient, db_session: Session, google_client
    ):
        # Arrange — primer login por Google
        google_client(identity=make_google_identity(sub="sub-stable", email="repe@example.com"))
        _callback(client)
        user_id = db_session.query(User).filter(User.google_sub == "sub-stable").one().id

        # Act — segundo login con el MISMO sub
        resp = _callback(client)

        # Assert
        assert resp.status_code == 302
        assert db_session.query(User).count() == 1
        assert db_session.query(User).one().id == user_id

    def test_email_change_in_google_does_not_overwrite_the_stored_email(
        self, client: TestClient, db_session: Session, google_client
    ):
        # Arrange — la cuenta se crea con un email
        google_client(identity=make_google_identity(sub="sub-x", email="antiguo@example.com"))
        _callback(client)

        # Act — Google devuelve el mismo sub pero otro email
        google_client(identity=make_google_identity(sub="sub-x", email="nuevo@example.com"))
        _callback(client)

        # Assert — la identidad es el sub; el email guardado no se toca
        user = db_session.query(User).one()
        assert user.email == "antiguo@example.com"


class TestGoogleCallbackLinksExistingAccount:
    def test_verified_email_links_google_to_the_existing_password_account(
        self, client: TestClient, db_session: Session, google_client
    ):
        # Arrange — cuenta previa de email+contraseña
        _register(client, "mixta@example.com")
        db_session.commit()
        existing = db_session.query(User).filter(User.email == "mixta@example.com").one()
        existing_id = existing.id
        assert existing.google_sub is None

        google_client(
            identity=make_google_identity(
                sub="sub-link", email="mixta@example.com", email_verified=True
            )
        )

        # Act
        resp = _callback(client)

        # Assert — es LA MISMA cuenta, ahora vinculada
        assert resp.status_code == 302
        assert settings.cookie_refresh_name in resp.cookies
        assert db_session.query(User).count() == 1

        linked = db_session.query(User).one()
        assert linked.id == existing_id
        assert linked.google_sub == "sub-link"
        assert linked.password_hash is not None

    def test_linked_account_can_still_log_in_with_its_password(
        self, client: TestClient, db_session: Session, google_client
    ):
        # Arrange
        _register(client, "sigue@example.com", password="password123")
        db_session.commit()
        google_client(identity=make_google_identity(sub="sub-keep", email="sigue@example.com"))
        _callback(client)

        # Act — la vinculación no debe invalidar la contraseña
        resp = client.post(
            "/auth/login",
            json={"email": "sigue@example.com", "password": "password123"},
        )

        # Assert
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_different_sub_on_an_already_linked_account_is_rejected(
        self, client: TestClient, db_session: Session, google_client
    ):
        # Arrange — cuenta ya vinculada al sub A
        google_client(identity=make_google_identity(sub="sub-A", email="ocupada@example.com"))
        _callback(client)

        # Act — otra identidad de Google reclama el mismo email
        google_client(identity=make_google_identity(sub="sub-B", email="ocupada@example.com"))
        resp = _callback(client)

        # Assert — no se sobrescribe el vínculo existente ni se emite sesión
        assert resp.status_code == 302
        assert _error_slug(resp) == "account_already_linked"
        assert settings.cookie_refresh_name not in resp.cookies
        assert db_session.query(User).one().google_sub == "sub-A"


# ===========================================================================
# Guardarraíl: email no verificado por Google
# ===========================================================================


class TestUnverifiedEmailGuardrail:
    def test_unverified_email_does_not_link_to_the_existing_account(
        self, client: TestClient, db_session: Session, google_client
    ):
        # Arrange — cuenta previa de email+contraseña
        _register(client, "victima@example.com")
        db_session.commit()

        google_client(
            identity=make_google_identity(
                sub="sub-atacante", email="victima@example.com", email_verified=False
            )
        )

        # Act
        resp = _callback(client)

        # Assert — ni se vincula, ni se emite sesión
        assert resp.status_code == 302
        assert _error_slug(resp) == "email_not_verified"
        assert settings.cookie_refresh_name not in resp.cookies
        assert db_session.query(User).one().google_sub is None

    def test_unverified_email_does_not_create_a_new_account_either(
        self, client: TestClient, db_session: Session, google_client
    ):
        # Arrange — no existe ninguna cuenta con ese email
        google_client(
            identity=make_google_identity(
                sub="sub-nuevo", email="sinverificar@example.com", email_verified=False
            )
        )

        # Act
        resp = _callback(client)

        # Assert — la regla es única: sin email verificado no se entra
        assert _error_slug(resp) == "email_not_verified"
        assert db_session.query(User).count() == 0


# ===========================================================================
# Validación del `state` (anti-CSRF)
# ===========================================================================


class TestStateValidation:
    def test_callback_without_state_returns_400(self, client, google_client):
        # Arrange
        google_client(identity=make_google_identity())

        # Act — sin pasar por /auth/google/login: no hay cookie ni parámetro
        resp = client.get(
            "/auth/google/callback",
            params={"code": _CODE},
            follow_redirects=False,
        )

        # Assert
        assert resp.status_code == 400
        assert settings.cookie_refresh_name not in resp.cookies

    def test_callback_with_mismatched_state_returns_400(self, client, google_client):
        # Arrange — hay cookie de state, pero el parámetro no coincide
        google_client(identity=make_google_identity())
        _start_google_login(client)

        # Act
        resp = client.get(
            "/auth/google/callback",
            params={"state": "state-falsificado", "code": _CODE},
            follow_redirects=False,
        )

        # Assert
        assert resp.status_code == 400
        assert settings.cookie_refresh_name not in resp.cookies

    def test_callback_without_state_cookie_returns_400(self, client, google_client):
        # Arrange — se obtiene un state válido y luego se pierde la cookie
        google_client(identity=make_google_identity())
        state = _start_google_login(client)
        client.cookies.clear()

        # Act
        resp = client.get(
            "/auth/google/callback",
            params={"state": state, "code": _CODE},
            follow_redirects=False,
        )

        # Assert
        assert resp.status_code == 400

    def test_no_user_is_created_when_state_fails(
        self, client: TestClient, db_session: Session, google_client
    ):
        # Arrange
        google_client(identity=make_google_identity())

        # Act
        client.get("/auth/google/callback", params={"code": _CODE}, follow_redirects=False)

        # Assert — el fallo de state corta antes de tocar la base de datos
        assert db_session.query(User).count() == 0


# ===========================================================================
# Otros desenlaces del callback
# ===========================================================================


class TestCallbackFailures:
    def test_user_cancelling_at_google_redirects_with_the_error(self, client, google_client):
        # Arrange
        google_client(identity=make_google_identity())

        # Act — Google devuelve ?error= en vez de ?code=
        resp = _callback(client, error="access_denied")

        # Assert
        assert resp.status_code == 302
        assert _error_slug(resp) == "access_denied"
        assert settings.cookie_refresh_name not in resp.cookies

    def test_failed_code_exchange_redirects_with_error(self, client, google_client):
        # Arrange
        google_client(raises=GoogleOAuthError("Google no responde"))

        # Act
        resp = _callback(client)

        # Assert
        assert _error_slug(resp) == "exchange_failed"
        assert settings.cookie_refresh_name not in resp.cookies

    def test_callback_without_code_redirects_with_error(self, client, google_client):
        # Arrange
        google_client(identity=make_google_identity())
        state = _start_google_login(client)

        # Act
        resp = client.get(
            "/auth/google/callback",
            params={"state": state},
            follow_redirects=False,
        )

        # Assert
        assert _error_slug(resp) == "missing_code"


# ===========================================================================
# La sesión emitida es la MISMA que la del login por contraseña
# ===========================================================================


class TestSessionEquivalence:
    def test_refresh_cookie_from_google_login_works_like_a_normal_login(
        self, client: TestClient, google_client
    ):
        # Arrange
        google_client(identity=make_google_identity(email="sesion@example.com"))
        _callback(client)

        # Act — el frontend canjea la cookie por un access token
        refresh_resp = client.post("/auth/refresh")

        # Assert
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.json()
        assert refresh_resp.json()["token_type"] == "bearer"

    def test_access_token_obtained_after_google_login_authenticates_me(
        self, client: TestClient, google_client
    ):
        # Arrange
        google_client(identity=make_google_identity(email="perfil@example.com"))
        _callback(client)
        access_token = client.post("/auth/refresh").json()["access_token"]

        # Act
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})

        # Assert
        assert resp.status_code == 200
        assert resp.json()["email"] == "perfil@example.com"

    def test_google_login_never_puts_the_access_token_in_the_url(self, client, google_client):
        # Arrange
        google_client(identity=make_google_identity())

        # Act
        resp = _callback(client)

        # Assert — el access token solo viaja por /auth/refresh
        location = resp.headers["location"]
        assert "access_token" not in location
        assert "#" not in location


# ===========================================================================
# Cliente OIDC: construcción de la URL y validación del id_token (sin red)
# ===========================================================================


def _make_client() -> GoogleOAuthClient:
    """Cliente con credenciales ficticias: no se usa la red en ningún test."""
    return GoogleOAuthClient(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://localhost:8000/auth/google/callback",
    )


def _make_id_token(**overrides) -> str:
    """Firma un id_token de prueba (la firma no se valida, ver ADR-009)."""
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "test-client-id",
        "sub": "sub-from-token",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "email": "token@example.com",
        "email_verified": True,
        "name": "Token User",
    }
    claims.update(overrides)
    return jwt.encode(claims, "irrelevant-signing-key-for-tests", algorithm="HS256")


class TestAuthorizationUrl:
    def test_authorization_url_carries_every_required_parameter(self):
        # Arrange
        oauth_client = _make_client()

        # Act
        url = oauth_client.build_authorization_url("state-abc")

        # Assert
        query = parse_qs(urlparse(url).query)
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert query["client_id"] == ["test-client-id"]
        assert query["redirect_uri"] == ["http://localhost:8000/auth/google/callback"]
        assert query["response_type"] == ["code"]
        assert query["scope"] == ["openid email profile"]
        assert query["state"] == ["state-abc"]

    def test_authorization_url_does_not_leak_the_client_secret(self):
        # Arrange
        oauth_client = _make_client()

        # Act
        url = oauth_client.build_authorization_url("state-abc")

        # Assert — el secreto solo se usa server-to-server en el canje
        assert "test-client-secret" not in url


class TestGoogleClientDependency:
    """Cubre la dependencia real (el resto de tests la sustituye por un doble)."""

    def test_login_returns_503_when_google_is_not_configured(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange — se fuerza el entorno sin credenciales, sea cual sea el .env local
        monkeypatch.setattr(settings, "google_client_id", None)
        monkeypatch.setattr(settings, "google_client_secret", None)

        # Act
        resp = client.get("/auth/google/login", follow_redirects=False)

        # Assert — el login con Google es opcional: solo falla su endpoint
        assert resp.status_code == 503

    def test_dependency_builds_the_client_from_settings(self, monkeypatch: pytest.MonkeyPatch):
        # Arrange
        monkeypatch.setattr(settings, "google_client_id", "id-desde-settings")
        monkeypatch.setattr(settings, "google_client_secret", "secreto-desde-settings")
        monkeypatch.setattr(
            settings, "google_redirect_uri", "http://testserver/auth/google/callback"
        )

        # Act
        oauth_client = get_google_client()

        # Assert
        assert oauth_client.client_id == "id-desde-settings"
        assert oauth_client.redirect_uri == "http://testserver/auth/google/callback"


class TestIdTokenValidation:
    def test_valid_id_token_yields_the_identity(self):
        # Arrange
        oauth_client = _make_client()

        # Act
        identity = oauth_client.identity_from_id_token(_make_id_token())

        # Assert
        assert identity == GoogleIdentity(
            sub="sub-from-token",
            email="token@example.com",
            email_verified=True,
            name="Token User",
        )

    def test_token_issued_for_another_client_is_rejected(self):
        # Arrange
        oauth_client = _make_client()
        foreign = _make_id_token(aud="otra-aplicacion")

        # Act + Assert — sin comprobar `aud`, valdría el token de otra app
        with pytest.raises(GoogleOAuthError):
            oauth_client.identity_from_id_token(foreign)

    def test_token_from_another_issuer_is_rejected(self):
        # Arrange
        oauth_client = _make_client()
        foreign = _make_id_token(iss="https://evil.example.com")

        # Act + Assert
        with pytest.raises(GoogleOAuthError):
            oauth_client.identity_from_id_token(foreign)

    def test_expired_token_is_rejected(self):
        # Arrange
        oauth_client = _make_client()
        expired = _make_id_token(exp=datetime.now(UTC) - timedelta(hours=1))

        # Act + Assert
        with pytest.raises(GoogleOAuthError):
            oauth_client.identity_from_id_token(expired)

    def test_token_without_email_is_rejected(self):
        # Arrange
        oauth_client = _make_client()
        claims = {
            "iss": "https://accounts.google.com",
            "aud": "test-client-id",
            "sub": "sub-1",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        no_email = jwt.encode(claims, "irrelevant-signing-key-for-tests", algorithm="HS256")

        # Act + Assert
        with pytest.raises(GoogleOAuthError):
            oauth_client.identity_from_id_token(no_email)

    def test_malformed_token_is_rejected(self):
        # Arrange
        oauth_client = _make_client()

        # Act + Assert
        with pytest.raises(GoogleOAuthError):
            oauth_client.identity_from_id_token("esto-no-es-un-jwt")

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(True, True), ("true", True), ("false", False), (False, False), (None, False), (1, False)],
    )
    def test_email_verified_is_coerced_conservatively(self, raw, expected):
        # Arrange — Google puede enviar el claim como bool o como string
        oauth_client = _make_client()
        token = _make_id_token(email_verified=raw)

        # Act
        identity = oauth_client.identity_from_id_token(token)

        # Assert — cualquier valor inesperado cae del lado seguro (False)
        assert identity.email_verified is expected
