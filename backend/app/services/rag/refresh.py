"""RAG: refresh pipeline — fetch sources, chunk, embed, store.

W62: Two modes — "审核" (default) and "force" (legacy/admin override).
- 审核: refresh_source 抓完 + 切块后,**先存到 RagReviewSnapshot**,
  把 RagSource.review_status 置为 pending_review,不动 RagChunk。
  admin 在 /admin/rag-review approve 后才落库。
- force: 直接覆盖 RagChunk(回退到 W46 之前的行为),并把 review_status
  标 force_applied。给紧急用,会绕开审核。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import RagChunk, RagReviewSnapshot, RagSource
from app.services.rag.chunker import chunk_text
from app.services.rag.crawler import fetch_url
from app.services.rag.embedder import embed


# W46: per-destination recommended minimum bank-statement balance, in the
# destination country's local currency. The RAG curated content used to
# hardcode "余额建议 ≥ 5万元" for every country, which made no sense for
# applicants targeting the US / GB / VN / ID etc. We rewrite the canonical
# phrase in `localize_curated_text` below before chunking.
_BANK_BALANCE_BY_COUNTRY = {
    "US": "US$7,000",
    "GB": "£5,500",
    "FR": "€6,500", "DE": "€6,500", "IT": "€6,500", "ES": "€6,500",
    "NL": "€6,500", "CH": "€6,500", "AT": "€6,500", "BE": "€6,500",
    "JP": "¥1,000,000",
    "AU": "AU$10,000",
    "CA": "CA$10,000",
    "KR": "₩10,000,000",
    "SG": "S$10,000",
    "TH": "฿200,000",
    "VN": "₫150,000,000",
    "ID": "Rp 100.000.000",
    "IN": "₹500,000",
}

# 申根法定保险下限 3 万欧元，US/GB 等没有法定下限但业内常见 5 万美元
_INSURANCE_MIN_BY_COUNTRY = {
    "US": "US$50,000",
    "GB": "£30,000",
    # Schengen 法定下限
    "FR": "€30,000", "DE": "€30,000", "IT": "€30,000", "ES": "€30,000",
    "NL": "€30,000", "CH": "€30,000", "AT": "€30,000", "BE": "€30,000",
    "JP": "¥5,000,000",
    "AU": "AU$50,000",
    "CA": "CA$50,000",
    "KR": "₩30,000,000",
    "SG": "S$30,000",
    "TH": "฿1,000,000",
    "VN": "₫500,000,000",
    "ID": "Rp 500.000.000",
    "IN": "₹3,000,000",
}


def localize_curated_text(text: str, country_code: str) -> str:
    """Replace canonical zh-CN money phrases with the destination-country
    equivalent. The original phrases are still kept in chunks for fallback
    matching when the destination isn't in our table.

    Currently handles two patterns:
      - "余额建议 ≥ 5 万元" / "余额建议 ≥ 5万元" / "余额建议 ≥ 5 万"
      - "保额 ≥ 30 万元" / "保额 ≥ 3万欧元" (Schengen only — already correct)
    """
    if not country_code:
        return text
    cc = country_code.upper()

    balance = _BANK_BALANCE_BY_COUNTRY.get(cc)
    if balance:
        # match both with/without space, with/without 元
        text = re.sub(
            r"余额建议\s*≥\s*5\s*万(?:元)?",
            f"余额建议 ≥ {balance}",
            text,
        )

    insurance = _INSURANCE_MIN_BY_COUNTRY.get(cc)
    if insurance:
        # only rewrite the "30 万元" generic insurance phrase; leave the
        # existing Schengen-specific "3万欧元" alone (it's already correct)
        text = re.sub(
            r"保额\s*≥\s*30\s*万(?:元)?",
            f"保额 ≥ {insurance}",
            text,
        )

    return text


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


def _compute_chunks_hash(chunks: List[dict]) -> str:
    """SHA-1 of concatenated chunk contents, used as content fingerprint.

    任何 chunk 文本变化都会让 hash 变化 — 用作"内容是否真的变了"的判断。
    """
    joined = "\n".join(c["content"] for c in chunks)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


async def _compute_diff_for_source(db: AsyncSession, source_id: int, new_chunks: List[dict]) -> dict:
    """Build {added, removed, changed} diff vs current RagChunk rows.

    Used both when creating a snapshot (to show admins) and when deciding
    whether a content-hash change actually means the content changed (vs.
    just re-chunked into the same text).
    """
    rows = (await db.execute(
        select(RagChunk).where(RagChunk.source_id == source_id).order_by(RagChunk.chunk_index)
    )).scalars().all()
    old_chunks = [{"chunk_index": r.chunk_index, "content": r.content} for r in rows]
    old_map = {c["chunk_index"]: c["content"] for c in old_chunks}
    new_map = {c["chunk_index"]: c["content"] for c in new_chunks}

    added = [c for i, c in enumerate(new_chunks) if i not in old_map]
    removed = [c for c in old_chunks if c["chunk_index"] not in new_map]
    changed = [
        {"chunk_index": i, "old": old_map[i], "new": new_map[i]}
        for i in old_map.keys() & new_map.keys()
        if old_map[i] != new_map[i]
    ]
    return {"added": added, "removed": removed, "changed": changed}


async def _expire_existing_pending_snapshots(
    db: AsyncSession, source_id: int
) -> None:
    """If a source already has an open snapshot (还没 approve/reject 的),
    mark it as auto-rejected with note "superseded by newer refresh".

    避免同一 source 堆 5 个 pending snapshot 让审核员眼花。
    """
    now = datetime.utcnow()
    rows = (await db.execute(
        select(RagReviewSnapshot).where(
            RagReviewSnapshot.source_id == source_id,
            RagReviewSnapshot.decision.is_(None),
        )
    )).scalars().all()
    for snap in rows:
        snap.decision = "rejected"
        snap.decided_at = now
        snap.decision_note = "superseded by newer refresh"


async def _create_snapshot(
    db: AsyncSession,
    source: RagSource,
    raw_text: str,
    new_chunks: List[dict],
    diff: dict,
    fetch_meta: dict,
) -> RagReviewSnapshot:
    """Save a pending review snapshot for the source. Caller commits."""
    content_hash = _compute_chunks_hash(new_chunks)
    expires_at = datetime.utcnow() + timedelta(days=7)
    snap = RagReviewSnapshot(
        source_id=source.id,
        content_hash=content_hash,
        raw_text=raw_text,
        chunks_json=json.dumps(new_chunks, ensure_ascii=False),
        diff_summary_json=json.dumps(diff, ensure_ascii=False),
        fetch_meta_json=json.dumps(fetch_meta, ensure_ascii=False),
        expires_at=expires_at,
    )
    db.add(snap)
    source.review_status = "pending_review"
    await db.flush()
    return snap


async def refresh_source(
    db: AsyncSession, source: RagSource, *, mode: str = "review"
) -> dict:
    """Refresh one source: fetch + chunk + embed + (review snapshot | force replace).

    Args:
        mode: "review" (default) — 写入 RagReviewSnapshot 等审核;不会改 RagChunk。
              "force"            — 直接替换 RagChunk (绕过审核),把 review_status
                                    标 force_applied。一般运维紧急用,前端 UI
                                    会有二次确认。

    Returns:
        dict with {id, status, content_changed, snapshot_id?, ...}
    """
    if not source.enabled:
        return {"id": source.id, "status": "skipped", "reason": "disabled"}

    text = None
    title = None
    fetch_meta: dict = {"extractor": None, "status_code": None, "fetched_chars": 0}

    if source.content_type == "web":
        result = fetch_url(source.url)
        fetch_meta["extractor"] = result.extractor
        fetch_meta["status_code"] = result.status
        if result.error or not result.text:
            source.last_refresh_at = datetime.utcnow()
            source.last_status = "error"
            source.last_error = (result.error or "empty text")[:500]
            await db.flush()
            return {"id": source.id, "status": "error", "error": source.last_error}
        text = result.text
        title = result.title
        fetch_meta["fetched_chars"] = len(text)
    elif source.content_type == "curated":
        text = CURATED_CONTENT.get(source.name)
        if text is None:
            source.last_refresh_at = datetime.utcnow()
            source.last_status = "error"
            source.last_error = f"no curated content for: {source.name}"
            await db.flush()
            return {"id": source.id, "status": "error", "error": source.last_error}
        # W46: rewrite canonical zh-CN money phrases to the destination's
        # local currency before chunking (so RAG retrievals match users
        # querying in their own currency, e.g. "Rp" for ID applicants).
        text = localize_curated_text(text, source.country_code)
        fetch_meta["fetched_chars"] = len(text)
    else:
        return {"id": source.id, "status": "error", "error": f"unknown content_type: {source.content_type}"}

    chunks = chunk_text(text)
    new_chunks = [{"chunk_index": idx, "content": c.text} for idx, c in enumerate(chunks)]
    new_hash = _compute_chunks_hash(new_chunks)
    diff = await _compute_diff_for_source(db, source.id, new_chunks)
    content_changed = source.last_content_hash != new_hash

    source.last_refresh_at = datetime.utcnow()
    source.last_status = "ok"
    source.last_error = None

    if mode == "force":
        # 紧急:直接覆盖 RagChunk
        await _replace_chunks(db, source.id, [c["content"] for c in new_chunks])
        source.last_content_hash = new_hash
        source.review_status = "force_applied"
        # force 模式:作废现有 pending snapshot
        await _expire_existing_pending_snapshots(db, source.id)
        await db.commit()
        return {
            "id": source.id,
            "status": "ok",
            "mode": "force",
            "url": source.url,
            "title": title,
            "text_chars": len(text),
            "chunk_count": len(new_chunks),
            "content_changed": content_changed,
            "diff": diff,
        }

    # 默认 mode == "review" — 写入 snapshot,等 admin approve
    await _expire_existing_pending_snapshots(db, source.id)
    snap = await _create_snapshot(db, source, text, new_chunks, diff, fetch_meta)
    snapshot_id = snap.id
    await db.commit()
    return {
        "id": source.id,
        "status": "ok",
        "mode": "review",
        "url": source.url,
        "title": title,
        "text_chars": len(text),
        "chunk_count": len(new_chunks),
        "content_changed": content_changed,
        "snapshot_id": snapshot_id,
        "diff": diff,
    }


# Curated FAQ content — small but real, paraphrased from public visa info.
# W31: focus on 4 product lines: 欧洲(GB) / 申根(FR) / 美国(US) / 澳洲(AU).
CURATED_CONTENT = {
    "英国 Standard Visitor 签证 (curated FAQ)": (
        "英国 Standard Visitor 签证申请要求 (欧洲签证产品线)。"
        "中国公民可在线申请, 6个月内有效, "
        "单次或多次入境, 每次停留最多6个月。\n\n"
        "在线申请: GOV.UK 官网填写, 预约 UKVCAS 签证中心递交材料和采集指纹。\n\n"
        "所需材料: 护照原件 (有效期6个月以上, 至少1页空白), "
        "近6个月白底彩色照片 (35x45mm), 在线申请表, "
        "往返机票预订单, 酒店预订确认或英国邀请函, "
        "近6个月银行流水 (余额建议 ≥ 5万元, 流水显示稳定收入), "
        "在职证明 + 公司营业执照副本, 户口本复印件, 个人所得税完税证明。\n\n"
        "签证费: 127英镑 (约 1200 元人民币), 加急服务另收费。\n\n"
        "审理时间: 标准 3 周, 加急 5个工作日, 优先 (24小时) 需提前预约。\n\n"
        "UKVCAS 签证中心: 北京/上海/广州/重庆/沈阳/武汉/成都/济南/杭州/南京。\n\n"
        "英国签证官网: https://www.gov.uk/standard-visitor, UKVCAS: https://www.ukvcas.co.uk"
    ),
    "申根 (Schengen) 短期签证 (curated FAQ)": (
        "申根签证 (C 类短期签证, 申根产品线) 可入境所有 26 个申根国家 "
        "(法国/德国/意大利/西班牙/荷兰/瑞士/希腊/奥地利/比利时/捷克/丹麦/匈牙利/波兰/瑞典/挪威/芬兰等)。"
        "中国公民可通过法国/德国/意大利/西班牙等任意申根国驻华使领馆申请。\n\n"
        "所需材料: 护照原件 (有效期6个月以上, 至少2页空白签证页), "
        "近3个月白底彩色照片 (35x45mm), 完整填写的申根签证申请表, "
        "往返机票预订单 (不要出票), 申根区全程酒店预订确认, "
        "旅行医疗保险 (覆盖申根区, 保额 ≥ 3万欧元, 涵盖整个行程), "
        "近6个月银行流水 (余额建议 ≥ 5万元), 在职证明 + 公司营业执照副本, "
        "户口本复印件, 个人户口簿所有页。\n\n"
        "签证费: 80欧元 (约 600 元人民币), 6-15岁 40欧元, 6岁以下免费。\n\n"
        "审理时间: 通常 15 个工作日, 高峰期 (暑假/春节) 可能延长至 30 个工作日。\n\n"
        "首次申请申根签证必须采集指纹, 5年内再次申请可免。"
        "VFS Global 北京/上海/广州/武汉/沈阳/成都/重庆/济南均有受理中心。\n\n"
        "申根签证可在任一申根国家申请, 但行程主要目的地必须是申请国, 否则可能被退回。\n\n"
        "法国签证官网: https://france-visas.gouv.fr, 德国签证: https://videx.diplo.de, "
        "VFS Global 中国: https://visa.vfsglobal.com/chn"
    ),
    "美国 B1/B2 旅游商务签证 (curated FAQ)": (
        "美国 B1/B2 签证申请要求 (美国签证产品线)。"
        "申请人需持有有效期不少于6个月的因私普通护照。"
        "DS-160 在线申请表必须真实完整填写,所有信息与面试时回答一致。\n\n"
        "所需材料: 护照原件 (有效期6个月以上), DS-160 确认页, 51x51mm 白底彩色照片 (近6个月), "
        "面试预约信, 财力证明 (近6个月银行流水, 余额建议 ≥ 5 万元), 在职/在读证明, 行程单, "
        "美国境内联系人/酒店预订确认。\n\n"
        "面试常见问题: 旅行目的、停留时长、在美联系人、是否有亲属在美、工作/收入情况。"
        "回答要简洁真实,与 DS-160 内容一致。\n\n"
        "签证费: 185美元 (MRV 费), 不退款。即使签证被拒, 费用也不退。\n\n"
        "常见拒签原因 (214b): 无法证明非移民意图, 即签证官认为你有移民倾向。"
        "提高通过率: 充分证明国内约束力 (工作/家庭/财产), 行程合理, 财务清晰。\n\n"
        "审理时间因使领馆而异, 通常 3-15 个工作日出签。\n\n"
        "美国国务院官网: https://travel.state.gov, 面签预约: https://ustraveldocs.com"
    ),
    "澳大利亚旅游签证 (curated FAQ)": (
        "澳大利亚旅游签证 (subclass 600) 申请要求 (澳洲签证产品线)。"
        "中国公民可申请电子签证, 6个月内有效。\n\n"
        "所需材料: 护照原件 (有效期6个月以上), 身份证复印件, "
        "近6个月白底彩色照片 (35x45mm), 完整填写的签证申请表 (1419 表), "
        "近6个月银行流水 (余额建议 ≥ 5万元, 流水显示稳定收入), "
        "在职证明 + 公司营业执照副本, 户口本复印件, "
        "往返机票预订单, 澳大利亚酒店预订确认或邀请函。\n\n"
        "签证费: 190澳元 (约 900 元人民币), 在线信用卡支付。\n\n"
        "审理时间: 标准 15-25 个工作日, 高峰期 (暑假/春节/国庆) 可能延长至 30-40 个工作日。\n\n"
        "指定旅行社代送: 携程, 凯撒, 中青旅, 众信等, 也可个人通过 ImmiAccount 在线递交。\n\n"
        "常见拒签原因: 资金不足, 在职证明无法证明稳定收入, 单身女性无固定工作, 行程单不明确。\n\n"
        "澳大利亚移民局: https://immi.homeaffairs.gov.au, ImmiAccount: https://online.immi.gov.au"
    ),
}


async def refresh_all(
    db: AsyncSession,
    country_code: Optional[str] = None,
    *,
    mode: str = "review",
) -> List[dict]:
    """Refresh every enabled source (optionally filtered by country).

    mode: "review" | "force" — 透传给 refresh_source。
    """
    stmt = select(RagSource).where(RagSource.enabled.is_(True))
    if country_code:
        stmt = stmt.where(RagSource.country_code == country_code)
    sources = (await db.execute(stmt)).scalars().all()
    results = []
    for s in sources:
        results.append(await refresh_source(db, s, mode=mode))
    return results


# --------------------------------------------------------------------------- #
# W62+: 审核流程 service                                                       #
# --------------------------------------------------------------------------- #
async def approve_snapshot(
    db: AsyncSession,
    *,
    snapshot_id: int,
    admin_id: int,
    note: Optional[str] = None,
) -> dict:
    """把 snapshot 的 chunks 写回 RagChunk,更新 RagSource.last_content_hash。

    旧 hash 的 RagTranslation 缓存自动失效 (因为新 chunk 的 content_hash 跟
    旧的不同,retriever 会按新 hash 查缓存,miss 就走 LLM 重新翻译)。

    Idempotency: 如果 snapshot 已经 decided,直接报 "already_decided"。
    """
    snap = (await db.execute(
        select(RagReviewSnapshot).where(RagReviewSnapshot.id == snapshot_id)
    )).scalar_one_or_none()
    if not snap:
        raise ValueError(f"snapshot {snapshot_id} not found")
    if snap.decision is not None:
        raise ValueError(f"snapshot {snapshot_id} already decided: {snap.decision}")

    source = (await db.execute(
        select(RagSource).where(RagSource.id == snap.source_id)
    )).scalar_one_or_none()
    if not source:
        raise ValueError(f"source {snap.source_id} not found")

    new_chunks = json.loads(snap.chunks_json)
    # Replace chunks
    await _replace_chunks(db, source.id, [c["content"] for c in new_chunks])
    # 重要:刷新每个 chunk 的 content_hash,translation cache 才能正确失效
    rows = (await db.execute(
        select(RagChunk).where(RagChunk.source_id == source.id).order_by(RagChunk.chunk_index)
    )).scalars().all()
    for chunk in rows:
        chunk.content_hash = chunk.compute_content_hash()
    # Update source
    source.last_content_hash = snap.content_hash
    source.review_status = "approved"
    source.reviewed_by = admin_id
    source.reviewed_at = datetime.utcnow()
    source.review_note = note
    # Mark snapshot decided
    snap.decision = "approved"
    snap.decided_by = admin_id
    snap.decided_at = datetime.utcnow()
    snap.decision_note = note
    await db.commit()
    return {
        "snapshot_id": snapshot_id,
        "source_id": source.id,
        "status": "approved",
        "chunk_count": len(new_chunks),
    }


async def reject_snapshot(
    db: AsyncSession,
    *,
    snapshot_id: int,
    admin_id: int,
    note: Optional[str] = None,
) -> dict:
    """拒绝 snapshot。RagChunk 不变,source 状态变 rejected。

    跟 approve 一样会标 decision,只是 chunks 不落库。
    """
    snap = (await db.execute(
        select(RagReviewSnapshot).where(RagReviewSnapshot.id == snapshot_id)
    )).scalar_one_or_none()
    if not snap:
        raise ValueError(f"snapshot {snapshot_id} not found")
    if snap.decision is not None:
        raise ValueError(f"snapshot {snapshot_id} already decided: {snap.decision}")

    source = (await db.execute(
        select(RagSource).where(RagSource.id == snap.source_id)
    )).scalar_one_or_none()
    if not source:
        raise ValueError(f"source {snap.source_id} not found")

    source.review_status = "rejected"
    source.reviewed_by = admin_id
    source.reviewed_at = datetime.utcnow()
    source.review_note = note
    snap.decision = "rejected"
    snap.decided_by = admin_id
    snap.decided_at = datetime.utcnow()
    snap.decision_note = note
    await db.commit()
    return {
        "snapshot_id": snapshot_id,
        "source_id": source.id,
        "status": "rejected",
    }


async def cleanup_expired_snapshots(db: AsyncSession) -> int:
    """7 天前的未决 snapshot 直接 reject (decision=expired)。

    跟 reject 不同:不走 admin 流程,decision='expired' 表示系统自动清理。
    """
    now = datetime.utcnow()
    rows = (await db.execute(
        select(RagReviewSnapshot).where(
            RagReviewSnapshot.expires_at < now,
            RagReviewSnapshot.decision.is_(None),
        )
    )).scalars().all()
    for snap in rows:
        snap.decision = "expired"
        snap.decided_at = now
        snap.decision_note = "auto-expired after 7 days"
        # 同步 source 状态回 synced (没有 pending 了)
        source = (await db.execute(
            select(RagSource).where(RagSource.id == snap.source_id)
        )).scalar_one_or_none()
        if source and source.review_status == "pending_review":
            source.review_status = "synced"
    if rows:
        await db.commit()
    return len(rows)
