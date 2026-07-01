"""Tests para AuthService: register, authenticate, refresh y logout.

Estructura AAA. Usa la fixture db_session (SQLite en memoria) definida en
conftest.py. Ningún test toca offbloom.db.
"""

from __future__ import annotations

import pytest

from coach.auth.security import hash_refresh_token
from coach.auth.service import (
    AuthService,
    EmailAlreadyExists,
    InvalidCredentials,
    InvalidRefreshToken,
)
from coach.db.repositories import RefreshTokenRepo


class TestRegister:
    def test_register_persists_hashed_password_not_plaintext(self, db_session):
        # Arrange
        service = AuthService(db_session)
        password = "super-secret-pw"

        # Act
        user = service.register("new@example.com", password)
        db_session.commit()

        # Assert
        assert user.password_hash is not None
        assert user.password_hash != password

    def test_register_duplicate_email_raises(self, db_session):
        # Arrange
        service = AuthService(db_session)
        service.register("dup@example.com", "password123")
        db_session.commit()

        # Act + Assert
        with pytest.raises(EmailAlreadyExists):
            service.register("dup@example.com", "otherpassword")


class TestAuthenticate:
    def test_authenticate_valid_credentials_returns_tokens(self, db_session):
        # Arrange
        service = AuthService(db_session)
        service.register("login@example.com", "password123")
        db_session.commit()

        # Act
        access_token, refresh_token = service.authenticate("login@example.com", "password123")
        db_session.commit()

        # Assert
        assert access_token != ""
        assert refresh_token != ""

    def test_authenticate_persists_refresh_token_as_hash_not_plaintext(self, db_session):
        # Arrange
        service = AuthService(db_session)
        service.register("hashcheck@example.com", "password123")
        db_session.commit()

        # Act
        _, refresh_token = service.authenticate("hashcheck@example.com", "password123")
        db_session.commit()

        # Assert — lo persistido en DB es el sha256, no el valor en claro
        stored = RefreshTokenRepo(db_session).get_by_hash(hash_refresh_token(refresh_token))
        assert stored is not None
        assert stored.token_hash != refresh_token
        assert stored.token_hash == hash_refresh_token(refresh_token)

    def test_authenticate_wrong_password_raises_invalid_credentials(self, db_session):
        # Arrange
        service = AuthService(db_session)
        service.register("wrongpw@example.com", "password123")
        db_session.commit()

        # Act + Assert
        with pytest.raises(InvalidCredentials):
            service.authenticate("wrongpw@example.com", "not-the-password")

    def test_authenticate_unknown_email_raises_invalid_credentials(self, db_session):
        # Arrange
        service = AuthService(db_session)

        # Act + Assert
        with pytest.raises(InvalidCredentials):
            service.authenticate("nobody@example.com", "whatever123")

    def test_authenticate_with_none_password_hash_raises_invalid_credentials(self, db_session):
        # Arrange — usuario sin password_hash (p.ej. pensado para OAuth futuro)
        service = AuthService(db_session)
        service.users.create("oauth@example.com")
        db_session.commit()

        # Act + Assert
        with pytest.raises(InvalidCredentials):
            service.authenticate("oauth@example.com", "whatever123")


class TestRefresh:
    def test_refresh_rotates_token_and_revokes_old_one(self, db_session):
        # Arrange
        service = AuthService(db_session)
        service.register("rotate@example.com", "password123")
        db_session.commit()
        _, old_refresh = service.authenticate("rotate@example.com", "password123")
        db_session.commit()

        # Act
        _, new_refresh = service.refresh(old_refresh)
        db_session.commit()

        # Assert — el token viejo queda revocado y ya no sirve
        old_stored = RefreshTokenRepo(db_session).get_by_hash(hash_refresh_token(old_refresh))
        assert old_stored is not None
        assert old_stored.revoked is True
        assert new_refresh != old_refresh

    def test_refresh_with_revoked_token_raises(self, db_session):
        # Arrange
        service = AuthService(db_session)
        service.register("reuse@example.com", "password123")
        db_session.commit()
        _, old_refresh = service.authenticate("reuse@example.com", "password123")
        db_session.commit()
        service.refresh(old_refresh)
        db_session.commit()

        # Act + Assert — reusar el token ya rotado debe fallar
        with pytest.raises(InvalidRefreshToken):
            service.refresh(old_refresh)

    def test_refresh_with_unknown_token_raises(self, db_session):
        # Arrange
        service = AuthService(db_session)

        # Act + Assert
        with pytest.raises(InvalidRefreshToken):
            service.refresh("this-token-does-not-exist")


class TestLogout:
    def test_logout_revokes_refresh_token(self, db_session):
        # Arrange
        service = AuthService(db_session)
        service.register("logout@example.com", "password123")
        db_session.commit()
        _, refresh_token = service.authenticate("logout@example.com", "password123")
        db_session.commit()

        # Act
        service.logout(refresh_token)
        db_session.commit()

        # Assert
        stored = RefreshTokenRepo(db_session).get_by_hash(hash_refresh_token(refresh_token))
        assert stored is not None
        assert stored.revoked is True

    def test_logout_is_idempotent_for_unknown_token(self, db_session):
        # Arrange
        service = AuthService(db_session)

        # Act + Assert — no debe lanzar excepción
        service.logout("token-that-was-never-issued")
