"""Endpoints de perfil persistente: GET/PUT /me/profile.

Handlers finos: el mapper (db.mappers) traduce entre el UserProfile de
dominio y el Profile ORM; el commit de las mutaciones lo hace siempre el
handler, nunca el repo (Pattern B / Decisión D4).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from coach.api.deps import get_current_user, get_db
from coach.db.mappers import domain_to_profile_dict, profile_to_domain
from coach.db.models.user import User
from coach.db.repositories import ProfileRepo
from coach.graph.state import UserProfile

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("/profile", response_model=UserProfile)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfile:
    """Devuelve el perfil persistido del usuario autenticado.

    404 si el usuario todavía no ha completado el onboarding.
    """
    profile = ProfileRepo(db).get_by_user_id(current_user.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Perfil sin onboarding")

    return profile_to_domain(profile)


@router.put("/profile", response_model=UserProfile)
def put_profile(
    body: UserProfile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfile:
    """Crea o actualiza el perfil del usuario autenticado (idempotente)."""
    data = domain_to_profile_dict(body)
    profile = ProfileRepo(db).upsert(current_user.id, data)
    db.commit()
    return profile_to_domain(profile)
