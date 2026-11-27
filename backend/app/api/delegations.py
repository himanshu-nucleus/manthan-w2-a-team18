"""Delegating approvals while on leave. Rules live in ``app.services.delegations``."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models import Delegation, User
from app.schemas.approval import DelegationCreate, DelegationOut
from app.schemas.errors import error_responses
from app.services import delegations

router = APIRouter(prefix="/delegations", tags=["delegations"])


@router.post(
    "",
    response_model=DelegationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Delegate my approvals to someone of the same or higher role for a date range "
    "(approver roles only)",
    responses=error_responses(401, 403, 422),
)
def create_delegation(
    body: DelegationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Delegation:
    return delegations.create(db, user, body)


@router.get(
    "/me",
    response_model=list[DelegationOut],
    summary="Delegations I gave or received, newest first",
    responses=error_responses(401),
)
def list_my_delegations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Delegation]:
    return delegations.mine(db, user)


@router.delete(
    "/{delegation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Cancel one of my delegations (delegator only)",
    responses=error_responses(401, 404, 422),
)
def cancel_delegation(
    delegation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    delegations.cancel(db, user, delegation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
