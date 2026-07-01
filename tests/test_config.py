"""Tests para el validador de Settings.jwt_secret_key.

Estructura AAA. No usa base de datos.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from coach.config import Settings


class TestJwtSecretKeyValidation:
    def test_settings_rejects_jwt_secret_key_shorter_than_32_bytes(self):
        # Arrange — "corto" tiene menos de 32 bytes; se pasa como kwarg
        # explícito para que tenga prioridad sobre el JWT_SECRET_KEY fijado
        # en el entorno por conftest.py.
        secret_key_too_short = "corto"

        # Act + Assert
        with pytest.raises(ValidationError):
            Settings(jwt_secret_key=secret_key_too_short)
