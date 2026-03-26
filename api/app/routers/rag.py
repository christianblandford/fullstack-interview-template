from fastapi import APIRouter
from app.services.rag import rag_service

router = APIRouter(prefix="/rag",tags=["ingest"])


@router.get("/ingest")
async def ingest():
    total = rag_service.ingest()
    return {"status": "ok", "total": total}
