"""Repository history and blame endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.database import get_session
from app.core.security import require_scope
from app.models import (
    RepositoryBlameRequest,
    RepositoryBlameResponse,
    RepositoryHistoryResponse,
)
from app.services.repository_insights import build_repository_history, resolve_repository_blame

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.get("/history", response_model=RepositoryHistoryResponse)
def get_repository_history(
    repo: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
) -> RepositoryHistoryResponse:
    """Return scan history for one repository in the current tenant."""

    history = build_repository_history(
        session, tenant_slug=principal.tenant_slug, repo=repo, limit=limit
    )
    if not history.points:
        raise HTTPException(status_code=404, detail="Repository history not found")
    return history


@router.post("/blame", response_model=RepositoryBlameResponse)
def get_repository_blame(
    payload: RepositoryBlameRequest,
    principal=Depends(require_scope("scan:read")),
) -> RepositoryBlameResponse:
    """Return git blame details for one repository file line."""

    del principal
    try:
        return resolve_repository_blame(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
