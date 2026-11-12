"""IDE-oriented analysis endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.database import get_session
from app.core.security import require_scope
from app.models import IdeAnalyzeRequest, IdeAnalyzeResponse
from app.services.ide_scanner import run_ide_analysis
from app.services.policy_engine import write_audit_event

router = APIRouter(prefix="/ide", tags=["ide"])


@router.post("/analyze", response_model=IdeAnalyzeResponse)
def analyze_from_ide(
    payload: IdeAnalyzeRequest,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:write")),
) -> IdeAnalyzeResponse:
    """Analyze a workspace or file snapshot sent by an IDE extension."""

    try:
        response = run_ide_analysis(
            session, payload, tenant_slug=principal.tenant_slug, actor=principal.actor
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="ide.analyze",
        entity_type="scan" if response.scan else "analysis",
        entity_id=str(response.scan.id) if response.scan else None,
        details={"persisted": response.scan is not None, "files": len(payload.files)},
    )
    session.commit()
    return response
