"""Endpoint de baja de cuenta: DELETE /me.

Vive aparte del router de perfil porque borrar la cuenta no es una operación
sobre el perfil, sino sobre la identidad entera del usuario.

El sujeto sale SIEMPRE de `current_user` (el usuario del access token) y la
ruta no acepta ningún id: por construcción nadie puede dar de baja a otro.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from coach.api.cookies import clear_refresh_cookie
from coach.api.deps import get_current_user, get_db
from coach.api.schemas import DeleteAccountRequest
from coach.auth.service import AuthService, InvalidCredentials
from coach.db.models.user import User

router = APIRouter(prefix="/me", tags=["account"])


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    body: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Borra la cuenta del usuario autenticado y todos sus datos.

    Exige la contraseña actual como reautenticación. Todo el borrado (usuario,
    perfil, planes, progreso y refresh tokens) va en una sola transacción: si
    algo falla, `get_db` hace rollback y la cuenta queda intacta.
    """
    try:
        AuthService(db).delete_account(current_user, body.password)
    except InvalidCredentials as exc:
        # 403 y no 401: el access token ES válido, así que un 401 le diría al
        # cliente "token caducado" y le haría intentar un refresh (e incluso
        # cerrar la sesión) por una simple errata. Lo que falla aquí es el
        # step-up de reautenticación, que es autorización.
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    db.commit()

    # La sesión ya está muerta en servidor (los refresh tokens se fueron con la
    # cascada); esto borra además la cookie del navegador. Se emite sobre una
    # respuesta propia porque el 204 no lleva cuerpo.
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response
