import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.agents.document_agent import DocumentAgent
from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Document, Opportunity, User
from app.schemas.common import AnalysisResult, DocumentOut, ResumeAnalyzeRequest, SOPAnalyzeRequest
from app.utils.ids import new_id

router = APIRouter()
ALLOWED_TYPES = {
    "resume",
    "transcript",
    "passport",
    "id",
    "aadhaar",
    "income_certificate",
    "caste_certificate",
    "community_certificate",
    "disability_certificate",
    "bank_passbook",
    "passport_photo",
    "gate_scorecard",
    "admission_letter",
    "recommendation_letter",
    "statement_of_purpose",
    "bonafide_certificate",
    "research_proposal",
    "other",
}
ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md"}


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Document).filter(Document.student_id == user.id).all()


@router.post("/documents", response_model=DocumentOut)
async def upload_document(
    document_type: str = Form(...),
    confirm_delete_existing: bool = Form(False),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dtype = document_type.lower().replace(" ", "_")
    if dtype not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Invalid document type")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    upload_root = Path(get_settings().upload_dir) / user.id
    upload_root.mkdir(parents=True, exist_ok=True)
    doc_id = new_id("doc_")
    dest = upload_root / f"{doc_id}{suffix}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    agent = DocumentAgent()
    text = agent.extract_text_from_file(str(dest))
    doc = Document(
        id=doc_id,
        student_id=user.id,
        document_type=dtype,
        file_name=file.filename or dest.name,
        file_url=str(dest),
        verified=False,
        metadata_json={"content_type": file.content_type},
        extracted_text=text[:20000] if text else None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    confirm: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "requires_confirmation": True,
                "confirmation_prompt": "Delete this document from your vault?",
            },
        )
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.student_id == user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    path = Path(doc.file_url)
    if path.exists() and path.is_file() and "demo://" not in doc.file_url:
        path.unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    return {"ok": True}


@router.post("/resume/analyze", response_model=AnalysisResult)
def analyze_resume(
    payload: ResumeAnalyzeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opp = db.query(Opportunity).filter(Opportunity.id == payload.opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    text = payload.resume_text or ""
    if payload.document_id:
        doc = (
            db.query(Document)
            .filter(Document.id == payload.document_id, Document.student_id == user.id)
            .first()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        text = doc.extracted_text or text
    if not text:
        resume_doc = (
            db.query(Document)
            .filter(Document.student_id == user.id, Document.document_type == "resume")
            .first()
        )
        text = resume_doc.extracted_text if resume_doc else ""
    result = DocumentAgent().analyze_resume(text or "", opp.title, opp.description)
    return AnalysisResult(**result)


@router.post("/sop/analyze", response_model=AnalysisResult)
def analyze_sop(
    payload: SOPAnalyzeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opp = db.query(Opportunity).filter(Opportunity.id == payload.opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    result = DocumentAgent().analyze_sop(
        payload.sop_text,
        opp.title,
        opp.description,
        generate_improved_draft=payload.generate_improved_draft,
    )
    return AnalysisResult(**result)
