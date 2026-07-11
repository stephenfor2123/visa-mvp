"""Seed curated FAQ chunks for the 4 product-line RagSources (GB/FR/US/AU).

Idempotent — re-running skips existing chunks (matched by source_id+chunk_index).
Uses the existing embedder (hash backend, no API key needed).

Run:  cd backend && python scripts/seed_rag_chunks.py

W47c: each chunk now carries topic / visa_type / effective_date / source_url
metadata, and content_hash (SHA-1 of content) for the translation-cache
invalidation scheme. Re-running keeps the source of truth in sync.
"""
from __future__ import annotations

import asyncio
import json

import hashlib
from datetime import date

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.rag import RagChunk, RagSource
from app.services.rag.embedder import embed

# Per-country curated FAQ chunks — each is a structured text covering
# materials / fees+timing / common rejection reasons for the target country.

# W47c: chunk metadata — maps chunk_index → (topic, source_url fragment).
# All three sources for a country share `visa_type` and `effective_date`.
_TOPIC_BY_INDEX = {0: "materials", 1: "fees", 2: "refusal"}

CHUNKS = {
    "US": {
        "visa_type": "b1_b2",
        "effective_date": "2025-09-30",
        "source_url": "https://travel.state.gov/content/travel/en/us-visas.html",
        "items": [
            {
                "chunk_index": 0,
                "content": (
                    "美国 B1/B2 旅游/商务签证所需材料（依据 travel.state.gov 整理）：\n"
                    "B-1 用于商务活动（会议、谈判、短期培训），B-2 用于旅游、探亲、就医。两者通常合并签发为 B-1/B-2 多次往返签证。\n"
                    "1. 有效护照（有效期需超过在美停留期 6 个月以上，除非中美协议另有规定；每名需要签证的家庭成员须单独申请）。\n"
                    "2. DS-160 表格确认页（在线填写后打印，赴面谈时携带）。\n"
                    "3. 签证申请费缴费收据（MRV 费 185 美元，面谈前缴纳）。\n"
                    "4. 白底彩色证件照 1 张（51mm×51mm，6 个月内近照；DS-160 上传失败时备用）。\n"
                    "面谈时领事官员可能要求补充：赴美目的、回国意愿、支付能力证明（在职证明、营业执照、银行流水、资产证明等）。\n"
                    "重要：美国 B1/B2 签证申请**不需要**邀请函或 Affidavit of Support。提供与否都不影响是否签发，请勿把邀请函当决定性材料。"
                ),
            },
            {
                "chunk_index": 1,
                "content": (
                    "美国 B1/B2 签证费用、有效期与停留时间（依据 travel.state.gov）：\n"
                    "MRV 申请费：185 美元（不可退还，绝大部分国籍面谈前缴纳）。\n"
                    "签证签发费：根据申请人国籍，可能有额外签发费（依双边协议）。\n"
                    "有效期：通常对中国公民签发 10 年多次往返 B-1/B-2 签证；具体有效期由领事官员决定，依申请人国籍而不同。\n"
                    "单次最长停留：入境时由美国海关与边境保护局（CBP）官员在口岸决定，最长一般不超过 6 个月。具体天数标注在入境章或 I-94 表上。\n"
                    "审理时间：根据使领馆负荷，通常 5-15 个工作日；旺季（暑假、春节）可能延长至 3-4 周。\n"
                    "费用与面谈等待时间因使领馆而异，请查询具体使领馆官网。"
                ),
            },
            {
                "chunk_index": 2,
                "content": (
                    "美国 B1/B2 拒签、EVUS 与逾期后果（依据 travel.state.gov）：\n"
                    "Section 214(b) 拒签：依《移民与国籍法》，B-1/B-2 申请人默认有移民倾向，除非能证明与中国有强约束力（工作、家庭、财产等）。214(b) 是最常见的拒签条款。若情况有变化，可重新申请。\n"
                    "EVUS（签证更新电子系统）：持 10 年 B-1/B-2 签证的中国公民每次赴美前必须更新 EVUS。更新网址 www.EVUS.gov，每次更新费 30 美元（自 2025-09-30 起）。每两年更新一次；或取得新护照时更新；或新获 10 年 B-1/B-2 签证时更新——以先到者为准。\n"
                    "逾期停留：未按期离开美国即构成逾期（out of status）。根据 INA 222(g) 条款，逾期者的签证将自动作废，且任何因逾期而作废的多次往返签证不可再用于未来入境。\n"
                    "弄虚作假：故意虚假陈述或欺诈可能导致永久拒签。\n"
                    "B-1/B-2 签证**不允许在美国工作**。拿到签证前不要买机票或做不可退的行程安排。"
                ),
            },
        ],
    },
    "GB": {
        "visa_type": "standard_visitor",
        "effective_date": "2025-04-09",
        "source_url": "https://www.gov.uk/standard-visitor",
        "items": [
            {
                "chunk_index": 0,
                "content": (
                    "英国 Standard Visitor 签证所需材料（依据 GOV.UK）：\n"
                    "1. 护照（需在英国停留期间全部有效）。\n"
                    "2. 在线申请确认页（出发前通过 GOV.UK 在线提交，英国不提供落地签）。\n"
                    "3. 肺结核检测证明（在中国居住超过 6 个月的申请人必须使用英国内政部指定的医疗机构）。\n"
                    "4. 资金与旅行计划证明（银行对账单、住宿预订、回程或续程机票）。\n"
                    "5. 访问目的的支持材料（在职证明、商务会议邀请函或旅游行程单）。\n"
                    "6. 签证费缴费确认（在线支付申请费后保留确认页）。\n"
                    "注：签证不保证入境。UK Border Force 官员在边境做最终决定。"
                ),
            },
            {
                "chunk_index": 1,
                "content": (
                    "英国 Standard Visitor 签证费用、有效期与申请方式（依据 GOV.UK）：\n"
                    "签证费：135 英镑（6 个月以内的 Standard Visitor 标准短期签证）。最早可在出发前 3 个月申请。\n"
                    "若过境是来英的唯一目的，可申请 Visitor in Transit 签证，费用 74.50 英镑。\n"
                    "长期 Standard Visitor：可选 2 年、5 年、10 年长期签证，费用更高；10 年长期签证允许每次入境停留不超过 6 个月。\n"
                    "有效期：Standard Visitor 签证通常允许最长停留 6 个月（标准短期）。签证不保证入境，最终决定由 UK Border Force 在边境做出。\n"
                    "申请方式：必须通过 GOV.UK 在线申请。\n"
                    "允许的活动：旅游、探亲访友、过境转机、参加会议或面试（商务）、作为专家进行 permitted paid engagement、短期学习（不超过 6 个月）等。\n"
                    "禁止的活动：在英国公司工作或自雇（除非属 permitted paid engagement）、申领公共福利（benefits）、通过频繁或连续访问长期居留、结婚或登记民事伴侣关系（需 Marriage Visitor 签证）。"
                ),
            },
            {
                "chunk_index": 2,
                "content": (
                    "英国 Standard Visitor 签证资格与拒签原因（依据 GOV.UK）：\n"
                    "申请人必须证明：(1) 访问结束后会离开英国；(2) 能自行承担本人和家属在英期间的费用（或有他人资助）；(3) 能支付回程或续程费用（或有他人资助）；(4) 不会通过频繁或连续访问在英国长期居留，或将英国作为主要居住地。\n"
                    "护照或旅行证件需在停留期间内全部有效。\n"
                    "常见拒签原因：资金或收入来源证明不足；旅行计划不清晰（如无酒店/回程机票预订）；之前有英国或其他国家的移民违规记录；未出席生物信息采集。\n"
                    "之前被拒签并不自动意味着之后会被拒签：情况有变可重新申请并提供更充分的证明材料。"
                ),
            },
        ],
    },
    "AU": {
        "visa_type": "subclass_600",
        "effective_date": "2025-07-01",
        "source_url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600",
        "items": [
            {
                "chunk_index": 0,
                "content": (
                    "澳大利亚 Subclass 600 旅游签证所需材料（依据 immi.homeaffairs.gov.au）：\n"
                    "1. 护照（需在你计划停留期间有效）。\n"
                    "2. ImmiAccount 申请确认（在内政部官网在线提交）。\n"
                    "3. 资金证明（银行对账单或收入证明，以支持你在澳大利亚的停留）。\n"
                    "4. 旅行行程和住宿（航班预订、酒店预订或邀请人邀请）。\n"
                    "5. 与本国的联系（就业证明、财产或家庭联系，以证明你将返回）。\n"
                    "6. 体检证明（如内政部要求）。\n"
                    "7. 签证费缴费确认（通过 ImmiAccount 在线支付）。\n"
                    "注：每次停留通常最长为 3 个月，记录在签证标签上。"
                ),
            },
            {
                "chunk_index": 1,
                "content": (
                    "澳大利亚 Subclass 600 费用、有效期与审理时间（依据 immi.homeaffairs.gov.au）：\n"
                    "签证费：190 澳元（最常见的旅游类）。同一份申请若包含多位申请人或申请更长期限的签证，会产生额外费用。\n"
                    "审理时间：大部分 Visitor visa 申请在数周内审结，具体取决于签证类别、申请国和申请量。可在 immi.homeaffairs.gov.au 的 global processing times 工具查询当前预估审理周期。\n"
                    "付款方式：通过 ImmiAccount 提交时使用信用卡在线支付。批签前可能要求补缴第二笔费用（如体检费、采集生物信息费用等）。\n"
                    "有效期：由内政部决定。短期旅游类一般最多 12 个月多次往返、每次停留不超过 3 个月；3 年 / 5 年的常旅客签证只对低风险、有良好记录的申请人开放。\n"
                    "申请方式：通过澳大利亚内政部（Department of Home Affairs）官网的 ImmiAccount 在线提交。境内境外均可申请。\n"
                    "评估因素：访问目的、是否有足够资金支持在澳停留、是否真的只是临时访问、申请人的移民历史等。"
                ),
            },
            {
                "chunk_index": 2,
                "content": (
                    "澳大利亚 Subclass 600 健康、品行与拒签（依据 immi.homeaffairs.gov.au）：\n"
                    "必须满足健康与品行要求。视停留时长、国籍和拟从事的活动而定，可能需要由 panel physician 进行体检或胸片检查。\n"
                    "品行方面：所有犯罪记录（含已过追诉期的部分情况）都必须申报。\n"
                    "未如实申报可能导致签证被撤销并被禁止 3 年内再次申请。\n"
                    "常见拒签原因：资金或回国约束力证明不充分；曾有逾期或被撤销签证记录；申请材料提供虚假或误导性信息；无法证明行程属真实短期访问。\n"
                    "如被拒签，可重新申请或向 Administrative Review Tribunal (ART) 申请复议。每一次新申请都会按当下材料独立评估。"
                ),
            },
        ],
    },
    "FR": {
        "visa_type": "c_short_stay",
        "effective_date": "2024-06-11",
        "source_url": "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en",
        "items": [
            {
                "chunk_index": 0,
                "content": (
                    "申根短期签证（C 类）所需材料（依据 EU 签证法典）：\n"
                    "1. 护照（有效期需超过离开申根区日期 3 个月以上，近 10 年内签发，至少 2 页空白页）。\n"
                    "2. 填写并签字的申请表（向主要目的地或首次入境申根国家的领事馆申请）。\n"
                    "3. 近期生物特征照片（近 6 个月内拍摄）。\n"
                    "4. 旅行医疗保险（最低保额 3 万欧元，覆盖整个申根区及全部停留天数）。\n"
                    "5. 住宿证明（酒店预订单或邀请人邀请函）。\n"
                    "6. 往返或续程机票预订单。\n"
                    "7. 经济能力证明（银行对账单或资助人证明信）。\n"
                    "8. 在职或在学证明（雇主证明信、工资单或在校证明）。\n"
                    "9. 未成年人需父母同意书（如适用）。\n"
                    "10. 生物识别（首次申请采集 10 指指纹并存入签证信息系统 VIS，有效期 59 个月，期间在任一成员国再申请无需重新采集）。\n"
                    "注：只访问一国则向该国申请；访问多国则向主要目的地（停留最久的国家）申请；停留时间相等时，则向首次入境国申请。"
                ),
            },
            {
                "chunk_index": 1,
                "content": (
                    "申根短期签证（C 类）费用、有效期与处理时间（依据 EU 签证法典）：\n"
                    "签证费：90 欧元（成年人），45 欧元（6-12 岁儿童），6 岁以下免费（依据 Commission Delegated Reg. (EU) 2024/1415，自 2024-06-11 起执行）。VFS Global / TLScontact 等外部服务商另收服务费。\n"
                    "有效期：持申根短期签证可在任一 180 天周期内停留最多 90 天，签证通常在整个申根区有效。180 天周期自首次入境之日起算。\n"
                    "处理时间：自申请合规起 15 个自然日内；个别情况下可延长至 45 天。某些与申根签有签证便利协议的国家可缩短处理时间。\n"
                    "法律依据：EU 签证法典 (Reg. (EC) 810/2009，经 2019/1155 和 Commission Delegated Reg. (EU) 2024/1415 修订)。"
                ),
            },
            {
                "chunk_index": 2,
                "content": (
                    "申根短期签证（C 类）拒签与未来系统（依据 EU 规则）：\n"
                    "如被拒签，申请人会收到一份标准化拒签表格，列明拒签理由。常见拒签理由：提交伪造文件、未证明访问目的与停留条件、生活费资金不足、被列入申根信息系统（SIS）入境禁令、未证明有真实回国意愿。\n"
                    "申请人有权在被拒国家提出申诉。申诉须在拒签国法律规定期限内（通常 15-30 天，因国家而异）提交。\n"
                    "即将实施：申根区全面推行 EES（出入境系统）；对免签旅客引入 ETIAS（类似美国 ESTA）。这些系统不替代非免签国家的签证要求，但会影响过境和边境流程。\n"
                    "2026 年 1 月，欧盟委员会通过首份《EU 签证战略》（EU Visa Strategy），长期方向是签证流程更数字化、审批更高效。"
                ),
            },
        ],
    },
}


async def main():
    async with AsyncSessionLocal() as db:
        # Load enabled RagSource rows; pick the (country_code, language=zh-CN) one
        # specifically so we don't accidentally clobber en/id/vi sources when
        # multiple language variants of the same country exist in the table.
        LANG = "zh-CN"
        rows = (
            await db.execute(
                select(RagSource).where(
                    RagSource.enabled.is_(True),
                    RagSource.language == LANG,
                )
            )
        ).scalars().all()

        source_by_country = {r.country_code: r for r in rows}

        total_added = 0
        total_updated = 0

        for country_code, country_def in CHUNKS.items():
            source = source_by_country.get(country_code)
            if source is None:
                print(f"  [WARN] no enabled zh-CN RagSource for {country_code} — run seed_rag_sources.py first")
                continue

            visa_type = country_def["visa_type"]
            # SQLite Date column needs a Python date object, not an ISO string.
            _y, _m, _d = (int(x) for x in country_def["effective_date"].split("-"))
            effective_date = date(_y, _m, _d)
            source_url = country_def["source_url"]

            for chunk_def in country_def["items"]:
                chunk_index = chunk_def["chunk_index"]
                topic = _TOPIC_BY_INDEX.get(chunk_index, "overview")

                # Idempotency: upsert (overwrite content + embedding if exists)
                existing = (
                    await db.execute(
                        select(RagChunk).where(
                            RagChunk.source_id == source.id,
                            RagChunk.chunk_index == chunk_index,
                        )
                    )
                ).scalar_one_or_none()

                content = chunk_def["content"]
                content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()
                embedding_vec = embed(content)
                embedding_dim = len(embedding_vec)

                if existing:
                    existing.content = content
                    existing.content_hash = content_hash
                    existing.embedding = json.dumps(embedding_vec)
                    existing.embedding_dim = embedding_dim
                    existing.topic = topic
                    existing.visa_type = visa_type
                    existing.effective_date = effective_date
                    existing.source_url = source_url
                    print(f"  update: {country_code} chunk #{chunk_index} (dim={embedding_dim} topic={topic})")
                    total_updated += 1
                else:
                    db.add(
                        RagChunk(
                            source_id=source.id,
                            chunk_index=chunk_index,
                            content=content,
                            content_hash=content_hash,
                            embedding=json.dumps(embedding_vec),
                            embedding_dim=embedding_dim,
                            topic=topic,
                            visa_type=visa_type,
                            effective_date=effective_date,
                            source_url=source_url,
                        )
                    )
                    print(f"  add   : {country_code} chunk #{chunk_index} (dim={embedding_dim} topic={topic})")
                    total_added += 1

        await db.commit()
        print(f"\nDone — added {total_added} chunks, updated {total_updated} existing.")


if __name__ == "__main__":
    asyncio.run(main())
