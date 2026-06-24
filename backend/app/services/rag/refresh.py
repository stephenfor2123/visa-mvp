"""RAG: refresh pipeline — fetch sources, chunk, embed, store.

Idempotent: refreshing a source replaces its chunks.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import RagChunk, RagSource
from app.services.rag.chunker import chunk_text
from app.services.rag.crawler import fetch_url
from app.services.rag.embedder import embed


async def _replace_chunks(db: AsyncSession, source_id: int, texts: List[str]) -> int:
    """Wipe old chunks for source_id and insert new ones with embeddings."""
    await db.execute(delete(RagChunk).where(RagChunk.source_id == source_id))
    count = 0
    for idx, text in enumerate(texts):
        vec = embed(text)
        db.add(
            RagChunk(
                source_id=source_id,
                chunk_index=idx,
                content=text,
                embedding=json.dumps(vec, ensure_ascii=False),
                embedding_dim=len(vec),
            )
        )
        count += 1
    await db.flush()
    return count


async def refresh_source(db: AsyncSession, source: RagSource) -> dict:
    """Refresh one source: fetch + chunk + embed + replace chunks."""
    if not source.enabled:
        return {"id": source.id, "status": "skipped", "reason": "disabled"}

    text = None
    title = None
    if source.content_type == "web":
        result = fetch_url(source.url)
        if result.error or not result.text:
            source.last_refresh_at = datetime.utcnow()
            source.last_status = "error"
            source.last_error = (result.error or "empty text")[:500]
            await db.flush()
            return {"id": source.id, "status": "error", "error": source.last_error}
        text = result.text
        title = result.title
    elif source.content_type == "curated":
        text = CURATED_CONTENT.get(source.name)
        if text is None:
            source.last_refresh_at = datetime.utcnow()
            source.last_status = "error"
            source.last_error = f"no curated content for: {source.name}"
            await db.flush()
            return {"id": source.id, "status": "error", "error": source.last_error}
    else:
        return {"id": source.id, "status": "error", "error": f"unknown content_type: {source.content_type}"}

    chunks = chunk_text(text)
    chunk_count = await _replace_chunks(db, source.id, [c.text for c in chunks])
    source.last_refresh_at = datetime.utcnow()
    source.last_status = "ok"
    source.last_error = None
    await db.commit()
    return {
        "id": source.id,
        "status": "ok",
        "url": source.url,
        "title": title,
        "text_chars": len(text),
        "chunk_count": chunk_count,
    }


# Curated FAQ content — small but real, paraphrased from public visa info.
# Replace with official copy once we get access.
CURATED_CONTENT = {
    "印尼签证申请要求 (curated FAQ)": (
        "印度尼西亚旅游签证 (B211A) 申请要求。申请人需持有有效期不少于6个月的因私普通护照。"
        "签证费用约为50美元 (单次入境) 或100美元 (多次入境),以最新官方公告为准。"
        "可停留30天,可通过当地移民局付费延期一次,再延30天,共最多60天。"
        "所需材料: 护照原件 + 复印件, 往返机票行程单, 印尼境内酒店预订确认或邀请函, "
        "近6个月白底彩色照片 (4x6cm), 完整填写的签证申请表。\n\n"
        "印度尼西亚电子签证 (e-VOA) 可在线申请,网址 https://evisa.imigrasi.go.id "
        "无需邮寄护照,审批通常1-3个工作日。e-VOA 费用略高于普通签证,但更便捷。\n\n"
        "中国公民可免签入境印尼 (30天),2024年起对中国游客实施。免签不可延期。"
        "如需超过30天停留,建议提前办理 B211A 或 e-VOA。\n\n"
        "印尼移民局工作时间: 周一至周五 08:00-16:00,节假日休息。"
        "联系方式: info@imigrasi.go.id。重大变更请关注官网公告。"
    ),
    "越南签证指南 (curated FAQ)": (
        "越南旅游签证申请要求。中国公民可申请电子签证 (e-visa) 或落地签证。"
        "电子签证有效期最长90天,单次或多次入境,费用约25美元。\n\n"
        "电子签证申请网址: https://evisa.xuatnhapcanh.gov.vn。"
        "所需材料: 护照首页扫描件 (有效期6个月以上), 白底彩色照片 (2x2英寸或3x4cm),"
        "完整填写的在线申请表,信用卡支付。审批通常3个工作日。\n\n"
        "落地签证需提前申请批文 (Approval Letter), 抵达机场后再贴签。"
        "批文可通过旅行社办理,费用约15-25美元。落地签费用另计25美元 (单次) 或50美元 (多次)。\n\n"
        "越南签证可停留天数由签证类型决定: 电子签最长90天, 落地签最长30天或90天。"
        "如需延期,需向越南出入境管理局申请,通常可延30天。\n\n"
        "越南出入境管理局联系方式: 越南公安部出入境管理局。"
        "建议出发前在官网核实最新政策,以避免政策变更造成的影响。"
    ),
}


async def refresh_all(db: AsyncSession, country_code: Optional[str] = None) -> List[dict]:
    """Refresh every enabled source (optionally filtered by country)."""
    from sqlalchemy import select

    stmt = select(RagSource).where(RagSource.enabled.is_(True))
    if country_code:
        stmt = stmt.where(RagSource.country_code == country_code)
    sources = (await db.execute(stmt)).scalars().all()
    results = []
    for s in sources:
        results.append(await refresh_source(db, s))
    return results
