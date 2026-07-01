"""Capa de presentación HTTP (FastAPI): schemas, dependencias y routers.

Los handlers son finos: validan la entrada, delegan en la capa de dominio
(coach.auth, coach.graph) y traducen el resultado a HTTP.
"""

from __future__ import annotations
