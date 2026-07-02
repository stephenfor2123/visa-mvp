"""Seed curated FAQ chunks for the 4 product-line RagSources (GB/FR/US/AU).

Idempotent — re-running skips existing chunks (matched by source_id+chunk_index).
Uses the existing embedder (hash backend, no API key needed).

Run:  cd backend && python scripts/seed_rag_chunks.py
"""
from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.rag import RagChunk, RagSource
from app.services.rag.embedder import embed

# Per-country curated FAQ chunks — each is a structured text covering
# materials / fees+timing / common rejection reasons for the target country.
CHUNKS = {
    "US": [
        {
            "chunk_index": 0,
            "content": (
                "美国 B1/B2 旅游/商务签证所需材料：\n"
                "1. 有效护照（有效期需超过预计离境日期6个月以上）\n"
                "2. DS-160 表格确认页（在线填写后打印，需有条形码）\n"
                "3. 签证申请费缴费收据（160美元 MRV 费）\n"
                "4. 白底彩色证件照 1 张（51mm×51mm，正面免冠，不戴眼镜）\n"
                "5. 在职证明或营业执照复印件（需加盖公章）\n"
                "6. 银行流水或存款证明（建议覆盖近3个月）\n"
                "7. 行程单或机票酒店预订\n"
                "8. 面试确认信（预约面谈后生成）"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "美国 B1/B2 签证费用与审理时间：\n"
                "签证费：160美元（MRV 费），需在线预约面谈后现场缴纳。\n"
                "审理时间：根据使馆当前负荷，通常5-15个工作日；高峰期（暑假、春节）可能延长至3-4周。\n"
                "签证有效期：通常为10年多次往返（B1/B2 类别）。\n"
                "单次最长停留：入境时由海关官员决定，通常不超过6个月。\n"
                "申请技巧：建议尽早预约面谈时间段，准备充分的面谈回答，提前整理好材料顺序。"
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "美国 B1/B2 签证常见拒签原因与加分材料：\n"
                "常见拒签：214(b) 条款（移民倾向推定），最常见原因。\n"
                "加分项：国内约束力证明（房产证、在职证明、户口本）、强大的出行记录、稳定的收入流水、详细的赴美行程说明。\n"
                "面试技巧：明确说明旅游目的，回答简洁真实，不要主动提及移民倾向相关话题。\n"
                "白本护照：首次申请无出行记录，建议提供更多国内约束力证明。"
            ),
        },
    ],
    "GB": [
        {
            "chunk_index": 0,
            "content": (
                "英国 Standard Visitor 签证所需材料：\n"
                "1. 有效护照（需有至少1页空白页）\n"
                "2. 在线申请表（在线填写后打印，有申请号）\n"
                "3. 肺结核检测证明（TB Test，有效期6个月）\n"
                "4. 在职证明或在学证明\n"
                "5. 银行流水（近3个月，需显示稳定资金来源）\n"
                "6. 酒店预订单与往返机票\n"
                "7. 护照尺寸白底证件照 2 张"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "英国 Standard Visitor 签证费用与审理时间：\n"
                "签证费：短期访问（6个月）申请费95英镑。\n"
                "审理时间：标准服务15个工作日；加急服务5个工作日；超级加急24小时。\n"
                "有效期：最长6个月多次往返，可申请2/5/10年长期访问签证（费用更高）。\n"
                "肺结核检测：必须在英国内政部指定的中国医疗机构进行，不接受其他机构证明。"
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "英国签证常见拒签原因：\n"
                "资金证明不足：银行流水余额过低或来源不明。\n"
                "国内约束力不足：无法证明会按期离境（无房产、无稳定工作）。\n"
                "TB 检测不合格：肺结核患者必须先完成治疗。\n"
                "申请表信息矛盾：行程与酒店机票预订不符。\n"
                "建议：材料真实完整，行程合理，提前购买不可取消的机票酒店（保存付款凭证）。"
            ),
        },
    ],
    "AU": [
        {
            "chunk_index": 0,
            "content": (
                "澳大利亚旅游签证（600类别）所需材料：\n"
                "1. 有效护照（彩色扫描件）\n"
                "2. 身份证翻译件（如适用）\n"
                "3. 户口本整本彩色复印件（需公证翻译）\n"
                "4. 在职证明或退休证明\n"
                "5. 银行流水（近6个月，显示稳定资金来源）\n"
                "6. 行程计划（机票、酒店预订单）\n"
                "7. 关系证明（如有随行家属）\n"
                "注：600 旅游类别无强制面试，材料审核制。"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "澳大利亚600旅游签证费用与审理时间：\n"
                "签证费：145澳元（线上申请，信用卡缴费）。\n"
                "审理时间：75%申请在28天内完成，高峰期可能更长。\n"
                "有效期：1-3年多次往返（审批时决定），单次最长停留3个月。\n"
                "健康要求：18岁以下需提供亲生父母同意书；部分申请需体检。\n"
                "在线申请：通过 ImmiAccount 提交，全部材料电子上传，无需邮寄。"
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "澳大利亚签证常见拒签原因：\n"
                "资金证明不足：余额过低或无法说明资金来源。\n"
                "出行历史薄弱：白本护照或出行记录不足。\n"
                "材料不完整：缺少关键文件（如无英文翻译的公证材料）。\n"
                "国内约束力：单身/无资产申请人的拒签率相对较高。\n"
                "建议：充分展示回国约束力（工作、房产、家庭），材料中英文准备完整。"
            ),
        },
    ],
    "FR": [
        {
            "chunk_index": 0,
            "content": (
                "申根短期签证（C 类）所需材料（以法国为例）：\n"
                "1. 申根签证申请表（在线填写 + 签名）\n"
                "2. 有效护照（有效期超过返程日期3个月以上，2页空白）\n"
                "3. 白底证件照 2 张（35mm×45mm，6个月内近照）\n"
                "4. 旅行保险（覆盖申根区，保额3万欧元以上，覆盖医疗遣返）\n"
                "5. 往返机票预订单\n"
                "6. 行程单（每日安排）\n"
                "7. 酒店预订确认\n"
                "8. 在职证明+营业执照复印件\n"
                "9. 近3个月银行流水\n"
                "10. 签证费缴费收据（约80欧元）"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "申根签证费用与审理时间（法国受理）：\n"
                "签证费：80欧元（6-12岁儿童35欧元，6岁以下免费）。\n"
                "服务费：VFS Global 收取约33美元服务费。\n"
                "审理时间：通常15个自然日内；高峰期可能需3-4周。\n"
                "有效期：最长90天内最多停留180天（灵活行程）。\n"
                "指纹采集：10指纹+照片，需本人前往签证中心。\n"
                "注意：如主要目的地非法国，应向该国领事馆申请。"
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "申根签证常见拒签原因：\n"
                "保险不合格：保额不足3万欧元，或不覆盖申根区。\n"
                "行程不合逻辑：机票与酒店在日期/地点上矛盾。\n"
                "资金证明不足：余额过低或流水不完整。\n"
                "无充分回国约束力：单身+无固定资产申请人风险高。\n"
                "申请表信息矛盾：出行目的与行程不符。\n"
                "建议：购买可取消的旅行保险、提前订好机票酒店（不可取消订单）、充分展示回国约束力。"
            ),
        },
    ],
}


async def main():
    async with AsyncSessionLocal() as db:
        # Load all enabled RagSource rows so we can map country_code → source_id
        rows = (
            await db.execute(select(RagSource).where(RagSource.enabled.is_(True)))
        ).scalars().all()

        source_by_country = {r.country_code: r for r in rows}

        total_added = 0
        total_skipped = 0

        for country_code, chunks_defs in CHUNKS.items():
            source = source_by_country.get(country_code)
            if source is None:
                print(f"  [WARN] no enabled RagSource for {country_code} — run seed_rag_sources.py first")
                continue

            for chunk_def in chunks_defs:
                chunk_index = chunk_def["chunk_index"]

                # Idempotency: skip if this (source_id, chunk_index) pair already exists
                existing = (
                    await db.execute(
                        select(RagChunk).where(
                            RagChunk.source_id == source.id,
                            RagChunk.chunk_index == chunk_index,
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    print(f"  skip  : {country_code} chunk #{chunk_index} (already exists)")
                    total_skipped += 1
                    continue

                content = chunk_def["content"]
                embedding_vec = embed(content)
                embedding_dim = len(embedding_vec)

                db.add(
                    RagChunk(
                        source_id=source.id,
                        chunk_index=chunk_index,
                        content=content,
                        embedding=json.dumps(embedding_vec),
                        embedding_dim=embedding_dim,
                    )
                )
                print(f"  add   : {country_code} chunk #{chunk_index} (dim={embedding_dim})")
                total_added += 1

        await db.commit()
        print(f"\nDone — added {total_added} chunks, skipped {total_skipped} existing.")


if __name__ == "__main__":
    asyncio.run(main())
