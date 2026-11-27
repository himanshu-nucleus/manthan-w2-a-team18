"""Approval chain: my pending queue, approve / reject / send back, steps and comments.

Rules live in ``app.services.approvals`` and ``app.services.chain``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models import ApprovalStep, Claim, ClaimComment, User
from app.schemas.approval import (
    ApprovalStepOut,
    ApproveRequest,
    CommentCreate,
    CommentOut,
    DecisionRequest,
    PendingItem,
    PendingPage,
)
from app.schemas.claim import ClaimOut, ClaimSummary
from app.schemas.errors import error_responses
from app.services import approvals

router = APIRouter(tags=["approvals"])


@router.get(
    "/approvals/pending",
    response_model=PendingPage,
    summary="My approval queue: current steps assigned to me, open to my role, or delegated "
    "to me today; oldest first",
    responses=error_responses(401, 422),
)
def list_pending_approvals(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PendingPage:
    rows, total = approvals.pending_for(db, user, limit=limit, offset=offset)
    return PendingPage(
        items=[
            PendingItem(
                step=ApprovalStepOut.model_validate(step),
                claim=ClaimSummary.model_validate(claim),
                on_behalf_of_id=via,
            )
            for step, claim, via in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/claims/{claim_id}/approve",
    response_model=ClaimOut,
    summary="Approve the current step (current approver or their delegate); the last step "
    "approves the claim",
    responses=error_responses(401, 403, 404, 409, 422),
)
def approve_claim(
    claim_id: int,
    body: ApproveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Claim:
    return approvals.approve(db, user, claim_id, step_id=body.step_id, comment=body.comment)


@router.post(
    "/claims/{claim_id}/reject",
    response_model=ClaimOut,
    summary="Reject the claim at the current step; comment required; final",
    responses=error_responses(401, 403, 404, 409, 422),
)
def reject_claim(
    claim_id: int,
    body: DecisionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Claim:
    return approvals.reject(db, user, claim_id, step_id=body.step_id, comment=body.comment)


@router.post(
    "/claims/{claim_id}/send-back",
    response_model=ClaimOut,
    summary="Send the claim back to the claimant for clarification; comment required",
    responses=error_responses(401, 403, 404, 409, 422),
)
def send_back_claim(
    claim_id: int,
    body: DecisionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Claim:
    return approvals.send_back(db, user, claim_id, step_id=body.step_id, comment=body.comment)


@router.get(
    "/claims/{claim_id}/approval-steps",
    response_model=list[ApprovalStepOut],
    summary="The claim's approval chain, latest round first, with each step's status",
    responses=error_responses(401, 404, 422),
)
def get_approval_steps(
    claim_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ApprovalStep]:
    return approvals.approval_steps(db, user, claim_id)


@router.post(
    "/claims/{claim_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a claim (anyone who can see the claim); status does not change",
    responses=error_responses(401, 404, 422),
)
def add_claim_comment(
    claim_id: int,
    body: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClaimComment:
    return approvals.add_comment(db, user, claim_id, body.body)


@router.get(
    "/claims/{claim_id}/comments",
    response_model=list[CommentOut],
    summary="A claim's comments, oldest first",
    responses=error_responses(401, 404, 422),
)
def list_claim_comments(
    claim_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ClaimComment]:
    return approvals.list_comments(db, user, claim_id)
