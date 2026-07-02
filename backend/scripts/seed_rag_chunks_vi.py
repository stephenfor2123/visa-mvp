"""Seed curated FAQ chunks for US/GB/AU/FR in **Tiếng Việt (vi)** so the
/v2/rag/checklist endpoint can serve Vietnamese content when the frontend is
on the Vietnamese locale.

Pairs with seed_rag_chunks_en.py (English), seed_rag_chunks_id.py (Indonesian),
and seed_rag_chunks.py (Chinese). Re-running this script is safe — existing
Vietnamese chunks at the same (country, chunk_index) are overwritten.

Run:  cd backend && python scripts/seed_rag_chunks_vi.py
"""
from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.rag import RagChunk, RagSource
from app.services.rag.embedder import embed

LANG = "vi"

# Per-country curated FAQ chunks in Tiếng Việt.
CHUNKS = {
    "US": [
        {
            "chunk_index": 0,
            "content": (
                "Giấy tờ cần thiết cho Visa B1/B2 Hoa Kỳ (Du lịch/Kinh doanh):\n"
                "1. Hộ chiếu còn hiệu lực (tối thiểu 6 tháng sau ngày dự kiến rời khỏi)\n"
                "2. Trang xác nhận DS-160 (in sau khi điền trực tuyến, có mã vạch)\n"
                "3. Biên lai phí xin visa ($160 USD phí MRV)\n"
                "4. Một ảnh màu nền trắng (51mm × 51mm, chính diện, không đeo kính)\n"
                "5. Giấy xác nhận việc làm hoặc bản sao giấy phép kinh doanh (có đóng dấu công ty)\n"
                "6. Sao kê ngân hàng hoặc giấy chứng nhận tiền gửi gần đây (3 tháng gần nhất được khuyến nghị)\n"
                "7. Lịch trình chuyến đi và đặt vé máy bay/khách sạn\n"
                "8. Thư xác nhận phỏng vấn (được tạo sau khi đặt lịch hẹn lãnh sự)"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Phí Visa B1/B2 Hoa Kỳ và Thời gian xử lý:\n"
                "Lệ phí Visa: $160 USD (phí MRV), thanh toán trực tuyến trước khi đặt lịch phỏng vấn.\n"
                "Thời gian xử lý: Thông thường 5-15 ngày làm việc tùy thuộc khối lượng công việc của đại sứ quán; mùa cao điểm (mùa hè, Tết Nguyên Đán) có thể kéo dài đến 3-4 tuần.\n"
                "Thời hạn: Thường được cấp dưới dạng visa nhập cảnh nhiều lần 10 năm (loại B1/B2).\n"
                "Thời gian lưu trú tối đa: Được quyết định bởi nhân viên CBP tại cửa khẩu, thường không quá 6 tháng mỗi lần.\n"
                "Mẹo nộp đơn: Đặt lịch phỏng vấn sớm, chuẩn bị câu trả lời ngắn gọn và trung thực, sắp xếp giấy tờ theo thứ tự yêu cầu."
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "Lý do từ chối visa B1/B2 Hoa Kỳ phổ biến và giấy tờ tăng cường:\n"
                "Từ chối phổ biến: Mục 214(b) (suy đoán mục đích nhập cư) — lý do từ chối phổ biến nhất.\n"
                "Giấy tờ tăng cường: Bằng chứng ràng buộc mạnh với quê hương (sổ đỏ, giấy xác nhận việc làm, sổ hộ khẩu), lịch sử du lịch phong phú, sao kê thu nhập ổn định, kế hoạch chuyến đi Hoa Kỳ chi tiết.\n"
                "Mẹo phỏng vấn: Nêu rõ mục đích du lịch, trả lời ngắn gọn và trung thực, không tự đề cập các chủ đề liên quan đến nhập cư.\n"
                "Người nộp đơn lần đầu (hộ chiếu trắng): Cung cấp nhiều bằng chứng ràng buộc với quê hương hơn."
            ),
        },
    ],
    "GB": [
        {
            "chunk_index": 0,
            "content": (
                "Giấy tờ cần thiết cho Visa Standard Visitor Anh:\n"
                "1. Hộ chiếu còn hiệu lực (có ít nhất một trang trống)\n"
                "2. Đơn xin trực tuyến (in sau khi nộp, có số tham chiếu)\n"
                "3. Giấy chứng nhận xét nghiệm Lao (TB test, có hiệu lực 6 tháng)\n"
                "4. Giấy xác nhận việc làm hoặc giấy xác nhận sinh viên\n"
                "5. Sao kê ngân hàng gần đây (3 tháng gần nhất, thể hiện nguồn thu nhập ổn định)\n"
                "6. Đặt phòng khách sạn và vé máy bay khứ hồi\n"
                "7. Hai ảnh cỡ hộ chiếu nền trắng"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Phí Visa Standard Visitor Anh và Thời gian xử lý:\n"
                "Lệ phí Visa: £95 GBP cho visa thăm ngắn hạn (6 tháng).\n"
                "Thời gian xử lý: Dịch vụ tiêu chuẩn 15 ngày làm việc; dịch vụ ưu tiên 5 ngày làm việc; siêu ưu tiên 24 giờ.\n"
                "Thời hạn: Tối đa 6 tháng nhập cảnh nhiều lần; visa thăm dài hạn (2/5/10 năm) có sẵn với phí cao hơn.\n"
                "Xét nghiệm Lao: Phải được thực hiện tại phòng khám được Home Office phê duyệt; giấy chứng nhận từ phòng khám khác không được chấp nhận."
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "Lý do từ chối visa Anh phổ biến:\n"
                "Bằng chứng tài chính không đủ: Số dư ngân hàng thấp hoặc nguồn tiền không rõ ràng.\n"
                "Ràng buộc yếu với quê hương: Không thể chứng minh ý định rời Anh đúng hạn (không có tài sản, không có việc làm ổn định).\n"
                "Xét nghiệm Lao không đạt: Bệnh nhân Lao đang hoạt động phải hoàn thành điều trị trước khi nộp đơn.\n"
                "Thông tin đơn mâu thuẫn: Lịch trình không khớp với đặt phòng khách sạn/vé máy bay.\n"
                "Khuyến nghị: Cung cấp giấy tờ gốc đầy đủ, lịch trình hợp lý, và mua vé máy bay/khách sạn không hoàn lại (giữ biên lai thanh toán)."
            ),
        },
    ],
    "AU": [
        {
            "chunk_index": 0,
            "content": (
                "Giấy tờ cần thiết cho Visa Du lịch Úc (Subclass 600):\n"
                "1. Hộ chiếu còn hiệu lực (bản scan màu)\n"
                "2. Ảnh cỡ hộ chiếu gần đây\n"
                "3. Giấy tờ tùy thân (CMND/CCCD, sổ hộ khẩu)\n"
                "4. Giấy xác nhận việc làm hoặc giấy phép kinh doanh\n"
                "5. Sao kê ngân hàng gần đây (3-6 tháng gần nhất)\n"
                "6. Lịch trình chuyến đi và đặt vé máy bay khứ hồi\n"
                "7. Đặt phòng khách sạn hoặc thư mời từ người chủ tại Úc"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Phí Visa Du lịch Úc (Subclass 600) và Thời gian xử lý:\n"
                "Lệ phí Visa: AUD $190 (khoảng 3.000.000 VND), thanh toán trực tuyến bằng thẻ tín dụng.\n"
                "Thời gian xử lý: Tiêu chuẩn 15-25 ngày làm việc; mùa cao điểm (mùa hè / Tết Nguyên Đán / Quốc khánh) có thể kéo dài đến 30-40 ngày làm việc.\n"
                "Thời hạn: Thường được cấp dưới dạng visa nhập cảnh nhiều lần có giá trị đến 1 năm; mỗi lần lưu trú đến 3 tháng.\n"
                "Mẹo nộp đơn: Nộp đơn ít nhất 1-2 tháng trước chuyến đi; đảm bảo tất cả giấy tờ bằng tiếng Anh hoặc kèm bản dịch công chứng."
            ),
        },
    ],
    "FR": [
        {
            "chunk_index": 0,
            "content": (
                "Giấy tờ cần thiết cho Visa Schengen Pháp Ngắn hạn (Loại C):\n"
                "1. Hộ chiếu còn hiệu lực (được cấp trong 10 năm gần đây, hiệu lực ít nhất 3 tháng sau ngày về, ít nhất 2 trang trống)\n"
                "2. Đơn xin visa Schengen (điền và ký tên)\n"
                "3. Hai ảnh gần đây nền trắng (35mm × 45mm, chính diện)\n"
                "4. Bảo hiểm du lịch y tế (bao gồm khu vực Schengen, tối thiểu €30.000, có hiệu lực suốt thời gian lưu trú)\n"
                "5. Đặt vé máy bay khứ hồi\n"
                "6. Đặt phòng khách sạn hoặc giấy tờ chứng minh chỗ ở cho toàn bộ thời gian lưu trú\n"
                "7. Giấy xác nhận việc làm hoặc giấy xác nhận sinh viên\n"
                "8. Sao kê ngân hàng gần đây (3 tháng gần nhất)\n"
                "9. Biên lai thuế thu nhập cá nhân hoặc sổ đỏ (tùy chọn nhưng tăng cường hồ sơ)"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Phí Visa Schengen Pháp và Thời gian xử lý:\n"
                "Lệ phí Visa: €80 EUR (người lớn), €40 EUR (trẻ em 6-12 tuổi), miễn phí cho trẻ dưới 6 tuổi.\n"
                "Thời gian xử lý: Tiêu chuẩn 15 ngày lịch; có thể kéo dài đến 45 ngày trong mùa cao điểm hoặc nếu cần xem xét thêm.\n"
                "Thời hạn: Visa ngắn hạn (tối đa 90 ngày trong 180 ngày); nhập cảnh nhiều lần có thể dựa trên lịch sử du lịch.\n"
                "Mẹo nộp đơn: Đặt lịch hẹn tại trung tâm visa VFS Global ít nhất 4-6 tuần trước chuyến đi; dữ liệu sinh trắc học (vân tay) được thu thập tại buổi hẹn."
            ),
        },
    ],
}


async def upsert_source(db, country_code: str) -> int:
    existing = (await db.execute(
        select(RagSource).where(
            RagSource.country_code == country_code,
            RagSource.language == LANG,
        )
    )).scalar_one_or_none()
    if existing:
        return existing.id

    src = RagSource(
        name=f"Curated FAQ — {country_code} ({LANG})",
        country_code=country_code,
        language=LANG,
        url=None,
        content_type="curated",
        enabled=True,
        last_refresh_at=None,
        last_status="ok",
        last_error=None,
    )
    db.add(src)
    await db.flush()
    return src.id


async def upsert_chunks(db, source_id: int, country_code: str) -> int:
    items = CHUNKS.get(country_code, [])
    n = 0
    for c in items:
        existing = (await db.execute(
            select(RagChunk).where(
                RagChunk.source_id == source_id,
                RagChunk.chunk_index == c["chunk_index"],
            )
        )).scalar_one_or_none()
        emb = embed(c["content"])
        if existing:
            existing.content = c["content"]
            existing.embedding = json.dumps(emb)
            existing.embedding_dim = len(emb)
            existing.language = LANG
        else:
            db.add(RagChunk(
                source_id=source_id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                embedding=json.dumps(emb),
                embedding_dim=len(emb),
                language=LANG,
            ))
        n += 1
    return n


async def main() -> None:
    async with AsyncSessionLocal() as db:
        total_sources = 0
        total_chunks = 0
        for cc in CHUNKS:
            sid = await upsert_source(db, cc)
            n = await upsert_chunks(db, sid, cc)
            total_sources += 1
            total_chunks += n
            print(f"  {cc}: source_id={sid}, {n} chunks upserted")
        await db.commit()
        print(f"Done. Sources={total_sources}, chunks upserted={total_chunks}, lang={LANG}")


if __name__ == "__main__":
    asyncio.run(main())