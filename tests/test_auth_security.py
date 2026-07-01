"""Tests para las primitivas puras de coach.auth.security.

Estructura AAA (Arrange – Act – Assert). No usa base de datos: solo hashing
de contraseñas y emisión/verificación de tokens.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from coach.auth.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from coach.config import settings


class TestHashPassword:
    def test_hash_is_different_from_plaintext_password(self):
        # Arrange
        password = "correct horse battery staple"

        # Act
        hashed = hash_password(password)

        # Assert — el hash nunca debe coincidir con la contraseña en claro
        assert hashed != password

    def test_verify_password_succeeds_with_correct_password(self):
        # Arrange
        password = "correct horse battery staple"
        hashed = hash_password(password)

        # Act
        result = verify_password(password, hashed)

        # Assert
        assert result is True

    def test_verify_password_fails_with_wrong_password(self):
        # Arrange
        hashed = hash_password("correct horse battery staple")

        # Act
        result = verify_password("wrong password", hashed)

        # Assert
        assert result is False

    def test_verify_password_fails_with_malformed_hash(self):
        # Arrange
        malformed_hash = "not-a-valid-argon2-hash"

        # Act
        result = verify_password("anything", malformed_hash)

        # Assert
        assert result is False


class TestAccessTokenRoundTrip:
    def test_create_and_decode_returns_same_subject(self):
        # Arrange
        user_id = "11111111-1111-1111-1111-111111111111"

        # Act
        token = create_access_token(user_id)
        subject = decode_access_token(token)

        # Assert
        assert subject == user_id

    def test_decode_raises_on_expired_token(self):
        # Arrange — token firmado con exp en el pasado
        now = datetime.now(UTC)
        payload = {
            "sub": "some-user-id",
            "iat": now - timedelta(minutes=60),
            "exp": now - timedelta(minutes=30),
            "type": "access",
        }
        expired_token = jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        # Act + Assert
        with pytest.raises(InvalidTokenError):
            decode_access_token(expired_token)

    def test_decode_raises_on_invalid_signature(self):
        # Arrange — token firmado con una clave distinta a la configurada
        now = datetime.now(UTC)
        payload = {
            "sub": "some-user-id",
            "iat": now,
            "exp": now + timedelta(minutes=30),
            "type": "access",
        }
        token_with_wrong_key = jwt.encode(payload, "otra-clave-distinta", algorithm="HS256")

        # Act + Assert
        with pytest.raises(InvalidTokenError):
            decode_access_token(token_with_wrong_key)

    def test_decode_raises_on_missing_exp_claim(self):
        # Arrange — token firmado con la clave real pero sin claim exp
        payload = {
            "sub": "some-user-id",
            "type": "access",
        }
        token_without_exp = jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        # Act + Assert
        with pytest.raises(InvalidTokenError):
            decode_access_token(token_without_exp)

    def test_decode_raises_on_wrong_token_type(self):
        # Arrange — token válido pero con type distinto a "access"
        now = datetime.now(UTC)
        payload = {
            "sub": "some-user-id",
            "iat": now,
            "exp": now + timedelta(minutes=30),
            "type": "refresh",
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        # Act + Assert
        with pytest.raises(InvalidTokenError):
            decode_access_token(token)


class TestHashRefreshToken:
    def test_hash_refresh_token_is_deterministic(self):
        # Arrange
        token = "some-opaque-refresh-token-value"

        # Act
        first_hash = hash_refresh_token(token)
        second_hash = hash_refresh_token(token)

        # Assert
        assert first_hash == second_hash

    def test_hash_refresh_token_differs_for_different_tokens(self):
        # Arrange + Act
        hash_a = hash_refresh_token("token-a")
        hash_b = hash_refresh_token("token-b")

        # Assert
        assert hash_a != hash_b
