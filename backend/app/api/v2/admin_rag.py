"""/api/v2/admin/rag/* — RAG content review (admin only).

W62+: 内容审核流程。把"定期查官网"+"管理员判断要不要更新"+"多语言翻译"
做成模块化的人工 review 流程,跟 user/RPA 解耦。

Endpoints:
  GET    /admin/rag/sources              列出所有 source + 审核状态
  GET    /admin/rag/sources/{id}         source 详情 + 最新 chunks + 翻译覆盖
  GET    /admin/rag/sources/{id}/diff    当前 chunks vs 待审 snapshot 的 diff
  POST   /admin/rag/refresh              触发刷新 (走审核流程,非 force)
  POST   /admin/rag/refresh/force        强制覆盖 (绕过审核,会二次确认)
  POST   /admin/rag/snapshots/{id}/approve   通过
  POST   /admin/rag/snapshots/{id}/reject    拒绝
  POST   /admin/rag/sources/{id}/retrans    强制重译 4 国翻译缓存
  GET    /admin/rag/translation-stats   4 国翻译覆盖率 (给 dashboard)
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.middleware.admin_auth import verify_admin_token, AdminTokenData
from app.models.rag import (
    RagChunk,
    RagReviewSnapshot,
    RagSource,
    RagTranslation,
)
from app.schemas.common import ApiResponse
from app.services.rag.refresh import (
    approve_snapshot,
    refresh_all,
    reject_snapshot,
)
from app.services.rag.translate import SUPPORTED_LANGS, to_display


router = APIRouter(prefix="/admin/rag", tags=["admin-rag"])
_log = get_logger()


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #
class AdminRagSourceOut(BaseModel):
    id: int
    name: str
    country_code: str
    language: str
    url: Optional[str]
    content_type: str
    enabled: bool
    last_refresh_at: Optional[str]
    last_status: Optional[str]
    last_error: Optional[str]
    # W62+ review fields
    last_content_hash: Optional[str]
    review_status: str
    reviewed_by: Optional[int]
    reviewed_at: Optional[str]
    review_note: Optional[str]
    # 计数 — pending snapshot 数
    pending_snapshots: int = 0
    # 翻译覆盖 — {target_lang: bool} 当前 chunk 是否有缓存翻译
    translation_coverage: dict[str, bool] = {}


class AdminRagChunkOut(BaseModel):
    chunk_id: int
    chunk_index: int
    content: str
    content_hash: str
    topic: str = "*"
    visa_type: str = "*"
    source_url: Optional[str] = None
    effective_date: Optional[str] = None


class AdminRagTranslationStat(BaseModel):
    target_lang: str
    translated_chunks: int
    total_chunks: int
    coverage_pct: float
    last_translated_at: Optional[str]


class AdminRagSourceDetailOut(BaseModel):
    source: AdminRagSourceOut
    chunks: List[AdminRagChunkOut]
    # 翻译缓存状态 (4 国 x 当前 chunk 数)
    translation_stats: List[AdminRagTranslationStat]
    # 当前 open snapshot (pending_review) — 详情页 diff 视图用
    pending_snapshot: Optional[dict] = None
    # 最近 N 次决定历史 (approved/rejected)
    recent_decisions: List[dict] = []


class AdminRagDiffOut(BaseModel):
    source_id: int
    snapshot_id: Optional[int]
    current_hash: Optional[str]
    pending_hash: Optional[str]
    diff: dict
    content_changed: bool


class AdminRagRefreshOut(BaseModel):
    refreshed: int
    errors: int
    content_changed: int
    snapshots_created: int
    items: List[dict]


class AdminRagDecisionIn(BaseModel):
    note: Optional[str] = None


class AdminRagDecisionOut(BaseModel):
    snapshot_id: int
    source_id: int
    status: str
    chunk_count: Optional[int] = None


class AdminRagTranslationStatsOut(BaseModel):
    by_lang: List[AdminRagTranslationStat]
    overall_coverage_pct: float
    generated_at: str


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _source_to_dict(
    r: RagSource,
    pending_snapshots: int = 0,
    translation_coverage: Optional[dict[str, bool]] = None,
) -> AdminRagSourceOut:
    return AdminRagSourceOut(
        id=r.id,
        name=r.name,
        country_code=r.country_code,
        language=r.language,
        url=r.url,
        content_type=r.content_type,
        enabled=r.enabled,
        last_refresh_at=r.last_refresh_at.isoformat() if r.last_refresh_at else None,
        last_status=r.last_status,
        last_error=r.last_error,
        last_content_hash=r.last_content_hash,
        review_status=r.review_status or "synced",
        reviewed_by=r.reviewed_by,
        reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
        review_note=r.review_note,
        pending_snapshots=pending_snapshots,
        translation_coverage=translation_coverage or {},
    )


async def _source_translation_coverage(
    db: AsyncSession, source: RagSource
) -> dict[str, bool]:
    """对当前 source 的每个 chunk,看 4 国翻译缓存是否存在。

    返回 {lang: all_translated}。True 表示所有 chunk 都翻译过了。
    """
    if source.language != "en":
        # 非 en source 没有翻译缓存需求 (en 是 source of truth)
        return {lang: True for lang in SUPPORTED_LANGS if lang != "en"}
    chunk_rows = (await db.execute(
        select(RagChunk).where(RagChunk.source_id == source.id)
    )).scalars().all()
    if not chunk_rows:
        return {lang: False for lang in SUPPORTED_LANGS if lang != "en"}
    result: dict[str, bool] = {}
    for lang in SUPPORTED_LANGS:
        if lang == "en":
            continue
        hashes = [c.content_hash for c in chunk_rows]
        if not hashes:
            result[lang] = False
            continue
        # 该 lang 翻译缓存是否覆盖了所有 chunk 的 hash
        cached = (await db.execute(
            select(RagTranslation.source_hash).where(
                RagTranslation.target_lang == lang,
                RagTranslation.kind == "chunk",
                RagTranslation.source_hash.in_(hashes),
            )
        )).scalars().all()
        result[lang] = len(set(cached)) >= len(hashes)
    return result


# --------------------------------------------------------------------------- #
# GET /admin/rag/sources                                                      #
# --------------------------------------------------------------------------- #
@router.get(
    "/sources",
    response_model=ApiResponse[List[AdminRagSourceOut]],
    summary="List all RAG sources (admin review view)",
)
async def list_sources(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminTokenData, Depends(verify_admin_token)],
    status_filter: Annotated[Optional[str], Query(alias="status")] = None,
) -> ApiResponse[List[AdminRagSourceOut]]:
    """status_filter: synced | pending_review | approved | rejected | force_applied"""
    stmt = select(RagSource).order_by(RagSource.country_code, RagSource.id)
    if status_filter:
        stmt = stmt.where(RagSource.review_status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    out: List[AdminRagSourceOut] = []
    for r in rows:
        # pending snapshot count
        pending_n = (await db.execute(
            select(RagReviewSnapshot).where(
                RagReviewSnapshot.source_id == r.id,
                RagReviewSnapshot.decision.is_(None),
            )
        )).scalars().all()
        coverage = await _source_translation_coverage(db, r)
        out.append(_source_to_dict(r, pending_snapshots=len(pending_n), translation_coverage=coverage))
    return ApiResponse[List[AdminRagSourceOut]](code="1000", message="OK", data=out)


# --------------------------------------------------------------------------- #
# GET /admin/rag/sources/{id}                                                 #
# --------------------------------------------------------------------------- #
@router.get(
    "/sources/{source_id}",
    response_model=ApiResponse[AdminRagSourceDetailOut],
    summary="RAG source detail (chunks + translation stats + pending snapshot)",
)
async def get_source_detail(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminTokenData, Depends(verify_admin_token)],
    source_id: Annotated[int, Path(ge=1)],
) -> ApiResponse[AdminRagSourceDetailOut]:
    source = (await db.execute(
        select(RagSource).where(RagSource.id == source_id)
    )).scalar_one_or_none()
    if not source:
        return ApiResponse[AdminRagSourceDetailOut](
            code="2404", message="Source not found", data=None
        )

    # Chunks
    chunk_rows = (await db.execute(
        select(RagChunk).where(RagChunk.source_id == source_id).order_by(RagChunk.chunk_index)
    )).scalars().all()
    chunks = [
        AdminRagChunkOut(
            chunk_id=c.id,
            chunk_index=c.chunk_index,
            content=c.content[:600] + ("..." if len(c.content) > 600 else ""),
            content_hash=c.content_hash,
            topic=c.topic or "*",
            visa_type=c.visa_type or "*",
            source_url=c.source_url,
            effective_date=c.effective_date.isoformat() if c.effective_date else None,
        )
        for c in chunk_rows
    ]

    # Translation stats
    translation_stats: List[AdminRagTranslationStat] = []
    for lang in SUPPORTED_LANGS:
        if lang == "en" or source.language != "en":
            # 非 en source: 自身就是显示语言,en 是 source of truth 不需要 cache
            translation_stats.append(AdminRagTranslationStat(
                target_lang=lang,
                translated_chunks=len(chunks) if lang == source.language else 0,
                total_chunks=len(chunks),
                coverage_pct=100.0 if lang == source.language else 0.0,
                last_translated_at=None,
            ))
            continue
        if not chunks:
            translation_stats.append(AdminRagTranslationStat(
                target_lang=lang, translated_chunks=0, total_chunks=0,
                coverage_pct=0.0, last_translated_at=None,
            ))
            continue
        hashes = [c.content_hash for c in chunk_rows]
        cached_rows = (await db.execute(
            select(RagTranslation).where(
                RagTranslation.target_lang == lang,
                RagTranslation.kind == "chunk",
                RagTranslation.source_hash.in_(hashes),
            )
        )).scalars().all()
        unique_hashes = len({r.source_hash for r in cached_rows})
        last_at = max((r.translated_at for r in cached_rows), default=None)
        translation_stats.append(AdminRagTranslationStat(
            target_lang=lang,
            translated_chunks=unique_hashes,
            total_chunks=len(hashes),
            coverage_pct=round(100 * unique_hashes / max(1, len(hashes)), 1),
            last_translated_at=last_at.isoformat() if last_at else None,
        ))

    # Pending snapshot
    snap = (await db.execute(
        select(RagReviewSnapshot).where(
            RagReviewSnapshot.source_id == source_id,
            RagReviewSnapshot.decision.is_(None),
        ).order_by(RagReviewSnapshot.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    pending_snapshot = None
    if snap:
        try:
            new_chunks = json.loads(snap.chunks_json)
        except Exception:
            new_chunks = []
        try:
            diff = json.loads(snap.diff_summary_json)
        except Exception:
            diff = {}
        try:
            fetch_meta = json.loads(snap.fetch_meta_json)
        except Exception:
            fetch_meta = {}
        pending_snapshot = {
            "id": snap.id,
            "content_hash": snap.content_hash,
            "created_at": snap.created_at.isoformat(),
            "expires_at": snap.expires_at.isoformat(),
            "raw_text_chars": len(snap.raw_text or ""),
            "new_chunk_count": len(new_chunks),
            "new_chunks": [
                {"chunk_index": c.get("chunk_index"), "content": (c.get("content") or "")[:400]}
                for c in new_chunks[:20]
            ],
            "diff": diff,
            "fetch_meta": fetch_meta,
        }

    # Recent decisions
    dec_rows = (await db.execute(
        select(RagReviewSnapshot).where(
            RagReviewSnapshot.source_id == source_id,
            RagReviewSnapshot.decision.is_not(None),
        ).order_by(RagReviewSnapshot.decided_at.desc()).limit(5)
    )).scalars().all()
    recent_decisions = [
        {
            "snapshot_id": s.id,
            "decision": s.decision,
            "decided_by": s.decided_by,
            "decided_at": s.decided_at.isoformat() if s.decided_at else None,
            "note": s.decision_note,
        }
        for s in dec_rows
    ]

    pending_n = len(pending_snapshot and [pending_snapshot] or [])
    coverage = await _source_translation_coverage(db, source)
    source_out = _source_to_dict(
        source, pending_snapshots=1 if pending_snapshot else 0,
        translation_coverage=coverage,
    )
    return ApiResponse[AdminRagSourceDetailOut](code="1000", message="OK", data=AdminRagSourceDetailOut(
        source=source_out,
        chunks=chunks,
        translation_stats=translation_stats,
        pending_snapshot=pending_snapshot,
        recent_decisions=recent_decisions,
    ))


# --------------------------------------------------------------------------- #
# GET /admin/rag/sources/{id}/diff                                            #
# --------------------------------------------------------------------------- #
@router.get(
    "/sources/{source_id}/diff",
    response_model=ApiResponse[AdminRagDiffOut],
    summary="Diff between current chunks and pending snapshot (if any)",
)
async def get_source_diff(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminTokenData, Depends(verify_admin_token)],
    source_id: Annotated[int, Path(ge=1)],
) -> ApiResponse[AdminRagDiffOut]:
    source = (await db.execute(
        select(RagSource).where(RagSource.id == source_id)
    )).scalar_one_or_none()
    if not source:
        return ApiResponse[AdminRagDiffOut](code="2404", message="Source not found", data=None)
    snap = (await db.execute(
        select(RagReviewSnapshot).where(
            RagReviewSnapshot.source_id == source_id,
            RagReviewSnapshot.decision.is_(None),
        ).order_by(RagReviewSnapshot.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not snap:
        return ApiResponse[AdminRagDiffOut](code="1000", message="OK", data=AdminRagDiffOut(
            source_id=source_id,
            snapshot_id=None,
            current_hash=source.last_content_hash,
            pending_hash=None,
            diff={"added": [], "removed": [], "changed": []},
            content_changed=False,
        ))
    try:
        diff = json.loads(snap.diff_summary_json or "{}")
    except Exception:
        diff = {}
    return ApiResponse[AdminRagDiffOut](code="1000", message="OK", data=AdminRagDiffOut(
        source_id=source_id,
        snapshot_id=snap.id,
        current_hash=source.last_content_hash,
        pending_hash=snap.content_hash,
        diff=diff,
        content_changed=(source.last_content_hash != snap.content_hash),
    ))


# --------------------------------------------------------------------------- #
# POST /admin/rag/refresh                                                     #
# --------------------------------------------------------------------------- #
@router.post(
    "/refresh",
    response_model=ApiResponse[AdminRagRefreshOut],
    summary="Trigger RAG refresh (走 review 流程,落到 snapshot)",
)
async def trigger_refresh(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminTokenData, Depends(verify_admin_token)],
    country_code: Optional[str] = Query(None),
) -> ApiResponse[AdminRagRefreshOut]:
    items = await refresh_all(db, country_code=country_code, mode="review")
    refreshed = sum(1 for x in items if x.get("status") == "ok")
    errors = sum(1 for x in items if x.get("status") == "error")
    content_changed = sum(1 for x in items if x.get("content_changed"))
    snapshots_created = sum(1 for x in items if x.get("snapshot_id"))
    return ApiResponse[AdminRagRefreshOut](code="1000", message="OK", data=AdminRagRefreshOut(
        refreshed=refreshed, errors=errors, content_changed=content_changed,
        snapshots_created=snapshots_created, items=items,
    ))


# --------------------------------------------------------------------------- #
# POST /admin/rag/refresh/force                                               #
# --------------------------------------------------------------------------- #
@router.post(
    "/refresh/force",
    response_model=ApiResponse[AdminRagRefreshOut],
    summary="强制覆盖 (绕过审核,仅供紧急使用)",
)
async def trigger_refresh_force(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminTokenData, Depends(verify_admin_token)],
    country_code: Optional[str] = Query(None),
) -> ApiResponse[AdminRagRefreshOut]:
    items = await refresh_all(db, country_code=country_code, mode="force")
    refreshed = sum(1 for x in items if x.get("status") == "ok")
    errors = sum(1 for x in items if x.get("status") == "error")
    content_changed = sum(1 for x in items if x.get("content_changed"))
    return ApiResponse[AdminRagRefreshOut](code="1000", message="OK", data=AdminRagRefreshOut(
        refreshed=refreshed, errors=errors, content_changed=content_changed,
        snapshots_created=0, items=items,
    ))


# --------------------------------------------------------------------------- #
# POST /admin/rag/snapshots/{id}/approve + /reject                            #
# --------------------------------------------------------------------------- #
@router.post(
    "/snapshots/{snapshot_id}/approve",
    response_model=ApiResponse[AdminRagDecisionOut],
    summary="Approve a pending snapshot (chunks 落库 + 翻译缓存按新 hash 失效)",
)
async def approve(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AdminTokenData, Depends(verify_admin_token)],
    snapshot_id: Annotated[int, Path(ge=1)],
    body: AdminRagDecisionIn = AdminRagDecisionIn(),
) -> ApiResponse[AdminRagDecisionOut]:
    try:
        result = await approve_snapshot(
            db, snapshot_id=snapshot_id, admin_id=admin.id, note=body.note,
        )
        _log.info("admin_rag approve snapshot={} admin={}", snapshot_id, admin.id)
        return ApiResponse[AdminRagDecisionOut](
            code="1000", message="OK",
            data=AdminRagDecisionOut(
                snapshot_id=result["snapshot_id"],
                source_id=result["source_id"],
                status=result["status"],
                chunk_count=result.get("chunk_count"),
            ),
        )
    except ValueError as e:
        return ApiResponse[AdminRagDecisionOut](code="2400", message=str(e), data=None)


@router.post(
    "/snapshots/{snapshot_id}/reject",
    response_model=ApiResponse[AdminRagDecisionOut],
    summary="Reject a pending snapshot (chunks 不变,source 状态置 rejected)",
)
async def reject(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AdminTokenData, Depends(verify_admin_token)],
    snapshot_id: Annotated[int, Path(ge=1)],
    body: AdminRagDecisionIn = AdminRagDecisionIn(),
) -> ApiResponse[AdminRagDecisionOut]:
    try:
        result = await reject_snapshot(
            db, snapshot_id=snapshot_id, admin_id=admin.id, note=body.note,
        )
        _log.info("admin_rag reject snapshot={} admin={}", snapshot_id, admin.id)
        return ApiResponse[AdminRagDecisionOut](
            code="1000", message="OK",
            data=AdminRagDecisionOut(
                snapshot_id=result["snapshot_id"],
                source_id=result["source_id"],
                status=result["status"],
            ),
        )
    except ValueError as e:
        return ApiResponse[AdminRagDecisionOut](code="2400", message=str(e), data=None)


# --------------------------------------------------------------------------- #
# POST /admin/rag/sources/{id}/retrans                                        #
# --------------------------------------------------------------------------- #
@router.post(
    "/sources/{source_id}/retrans",
    response_model=ApiResponse[dict],
    summary="强制重译:清空该 source 对应 hash 的所有翻译缓存",
)
async def retrans(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[AdminTokenData, Depends(verify_admin_token)],
    source_id: Annotated[int, Path(ge=1)],
) -> ApiResponse[dict]:
    source = (await db.execute(
        select(RagSource).where(RagSource.id == source_id)
    )).scalar_one_or_none()
    if not source:
        return ApiResponse[dict](code="2404", message="Source not found", data={})
    # 删该 source 所有 chunk 的所有翻译缓存 — 之后用户查询时按新 content_hash
    # 自动重翻译。
    chunk_rows = (await db.execute(
        select(RagChunk).where(RagChunk.source_id == source_id)
    )).scalars().all()
    hashes = [c.content_hash for c in chunk_rows]
    if not hashes:
        return ApiResponse[dict](code="1000", message="OK", data={
            "source_id": source_id, "cleared": 0,
        })
    from sqlalchemy import delete
    del_stmt = delete(RagTranslation).where(
        RagTranslation.kind == "chunk",
        RagTranslation.source_hash.in_(hashes),
    )
    result = await db.execute(del_stmt)
    await db.commit()
    _log.info("admin_rag retrans source={} admin={} cleared={}",
              source_id, admin.id, result.rowcount)
    return ApiResponse[dict](code="1000", message="OK", data={
        "source_id": source_id,
        "cleared": result.rowcount,
    })


# --------------------------------------------------------------------------- #
# GET /admin/rag/translation-stats                                            #
# --------------------------------------------------------------------------- #
@router.get(
    "/translation-stats",
    response_model=ApiResponse[AdminRagTranslationStatsOut],
    summary="4 国翻译覆盖率汇总 (dashboard 用)",
)
async def translation_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminTokenData, Depends(verify_admin_token)],
) -> ApiResponse[AdminRagTranslationStatsOut]:
    en_sources = (await db.execute(
        select(RagSource).where(RagSource.language == "en", RagSource.enabled.is_(True))
    )).scalars().all()
    en_source_ids = [s.id for s in en_sources]
    chunk_rows: List[RagChunk] = []
    if en_source_ids:
        chunk_rows = (await db.execute(
            select(RagChunk).where(RagChunk.source_id.in_(en_source_ids))
        )).scalars().all()
    total_hashes = len({c.content_hash for c in chunk_rows})
    by_lang: List[AdminRagTranslationStat] = []
    overall_covered = 0
    for lang in SUPPORTED_LANGS:
        if lang == "en":
            by_lang.append(AdminRagTranslationStat(
                target_lang="en", translated_chunks=total_hashes, total_chunks=total_hashes,
                coverage_pct=100.0, last_translated_at=None,
            ))
            continue
        if total_hashes == 0:
            by_lang.append(AdminRagTranslationStat(
                target_lang=lang, translated_chunks=0, total_chunks=0,
                coverage_pct=0.0, last_translated_at=None,
            ))
            continue
        cached = (await db.execute(
            select(RagTranslation).where(
                RagTranslation.target_lang == lang,
                RagTranslation.kind == "chunk",
            )
        )).scalars().all()
        cached_hashes = {r.source_hash for r in cached}
        translated = len(cached_hashes & {c.content_hash for c in chunk_rows})
        last_at = max((r.translated_at for r in cached), default=None)
        pct = round(100 * translated / total_hashes, 1)
        by_lang.append(AdminRagTranslationStat(
            target_lang=lang, translated_chunks=translated, total_chunks=total_hashes,
            coverage_pct=pct, last_translated_at=last_at.isoformat() if last_at else None,
        ))
        overall_covered += translated
    overall = round(100 * overall_covered / max(1, total_hashes * (len(SUPPORTED_LANGS) - 1)), 1)
    return ApiResponse[AdminRagTranslationStatsOut](
        code="1000", message="OK",
        data=AdminRagTranslationStatsOut(
            by_lang=by_lang, overall_coverage_pct=overall,
            generated_at=datetime.utcnow().isoformat(),
        ),
    )
