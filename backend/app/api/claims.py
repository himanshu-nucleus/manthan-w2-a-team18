"""Expense claims: create, update, read, receipts and the audit trail.

Every endpoint needs a logged-in user. Rules live in ``app.services.claims``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models import AuditEvent, Claim, ClaimAttachment, ClaimStatus, User
from app.schemas.claim import AttachmentOut, AuditEventOut, ClaimOut, ClaimPage, ClaimWrite
from app.schemas.errors import error_responses
from app.services import attachments, claims

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post(
    "",
    response_model=ClaimOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a claim as a draft, or create and submit it (any logged-in user)",
    responses=error_responses(401, 422),
)
def create_claim(
    body: ClaimWrite,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Claim:
    return claims.create_claim(db, user, body)


@router.put(
    "/{claim_id}",
    response_model=ClaimOut,
    summary="Replace a draft claim's content; save it again as a draft or submit it (owner only)",
    responses=error_responses(401, 403, 404, 409, 422),
)
def update_claim(
    claim_id: int,
    body: ClaimWrite,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Claim:
    return claims.update_claim(db, user, claim_id, body)


@router.get("", response_model=ClaimPage, summary="List claims (employees see only their own)")
def list_claims(
    status_filter: ClaimStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClaimPage:
    items, total = claims.list_claims(
        db, user, status_filter=status_filter, limit=limit, offset=offset
    )
    return ClaimPage.model_validate(
        {"items": items, "total": total, "limit": limit, "offset": offset},
        from_attributes=True,
    )


@router.get("/{claim_id}", response_model=ClaimOut, summary="One claim with its lines")
def get_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Claim:
    return claims.get_visible_claim(db, user, claim_id)


@router.get(
    "/{claim_id}/audit",
    response_model=list[AuditEventOut],
    summary="The claim's change history, newest first",
)
def get_claim_audit(
    claim_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AuditEvent]:
    return claims.claim_history(db, user, claim_id)


@router.post(
    "/{claim_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a receipt (PDF, PNG or JPEG) to a draft claim",
)
def upload_attachment(
    claim_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClaimAttachment:
    return attachments.save_receipt(
        db,
        user,
        claim_id,
        filename=file.filename,
        content_type=file.content_type,
        stream=file.file,
    )


@router.get(
    "/{claim_id}/attachments/{attachment_id}",
    response_class=FileResponse,
    summary="Download a receipt file",
)
def download_attachment(
    claim_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    attachment, path = attachments.get_receipt(db, user, claim_id, attachment_id)
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.original_name)
