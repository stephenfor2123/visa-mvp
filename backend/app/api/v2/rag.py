"""/api/v2/rag — retrieval-augmented Q&A over official visa info.

Endpoints:
  GET    /api/v2/rag/sources          — list configured sources
  POST   /api/v2/rag/refresh          — admin: re-fetch + re-embed all (or one country)
  POST   /api/v2/rag/query            — user: ask a question, get top-k + answer
"""
from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.middleware.admin_auth import verify_admin_token, AdminTokenData
from app.models.rag import RagSource
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.rag.refresh import refresh_all, refresh_source
from app.services.rag.retriever import generate_answer, retrieve

router = APIRouter(prefix="/rag", tags=["rag"])
_log = get_logger()


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #
class RagSourceOut(BaseModel):
    id: int
    name: str
    country_code: str
    url: Optional[str]
    content_type: str
    enabled: bool
    last_refresh_at: Optional[str]
    last_status: Optional[str]
    last_error: Optional[str]


class RagRefreshOut(BaseModel):
    refreshed: int
    errors: int
    items: List[dict]


class RagQueryRequest(BaseModel):
    query: str
    country_code: Optional[str] = None
    top_k: int = 3


class RagChunkOut(BaseModel):
    chunk_id: int
    source_name: str
    source_url: Optional[str]
    score: float
    snippet: str


class RagQueryOut(BaseModel):
    query: str
    answer: str
    chunks: List[RagChunkOut]


# --------------------------------------------------------------------------- #
# Sources list                                                                #
# --------------------------------------------------------------------------- #
@router.get(
    "/sources",
    response_model=ApiResponse[List[RagSourceOut]],
    summary="List configured RAG sources",
)
async def list_sources(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[List[RagSourceOut]]:
    rows = (await db.execute(select(RagSource).order_by(RagSource.country_code, RagSource.id))).scalars().all()
    items = [
        RagSourceOut(
            id=r.id,
            name=r.name,
            country_code=r.country_code,
            url=r.url,
            content_type=r.content_type,
            enabled=r.enabled,
            last_refresh_at=r.last_refresh_at.isoformat() if r.last_refresh_at else None,
            last_status=r.last_status,
            last_error=r.last_error,
        )
        for r in rows
    ]
    return ApiResponse[List[RagSourceOut]](code="1000", message="OK", data=items)


# --------------------------------------------------------------------------- #
# Refresh (admin)                                                             #
# --------------------------------------------------------------------------- #
@router.post(
    "/refresh",
    response_model=ApiResponse[RagRefreshOut],
    summary="Refresh RAG sources (admin)",
)
async def refresh(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminTokenData, Depends(verify_admin_token)],
    country_code: Optional[str] = Query(None, description="Filter by country"),
) -> ApiResponse[RagRefreshOut]:
    items = await refresh_all(db, country_code=country_code)
    errors = sum(1 for x in items if x.get("status") == "error")
    refreshed = sum(1 for x in items if x.get("status") == "ok")
    return ApiResponse[RagRefreshOut](
        code="1000",
        message="OK",
        data=RagRefreshOut(refreshed=refreshed, errors=errors, items=items),
    )


# --------------------------------------------------------------------------- #
# Query (user)                                                                #
# --------------------------------------------------------------------------- #
@router.post(
    "/query",
    response_model=ApiResponse[RagQueryOut],
    summary="Ask a question; retrieve top-k chunks + generated answer",
)
async def query(
    body: RagQueryRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[RagQueryOut]:
    retrieved = await retrieve(
        db,
        query=body.query,
        country_code=body.country_code,
        top_k=body.top_k,
    )
    answer = generate_answer(body.query, retrieved)
    chunks = [
        RagChunkOut(
            chunk_id=r.chunk_id,
            source_name=r.source_name,
            source_url=r.source_url,
            score=round(r.score, 4),
            snippet=r.text[:300] + ("..." if len(r.text) > 300 else ""),
        )
        for r in retrieved
    ]
    return ApiResponse[RagQueryOut](
        code="1000",
        message="OK",
        data=RagQueryOut(query=body.query, answer=answer, chunks=chunks),
    )
