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
