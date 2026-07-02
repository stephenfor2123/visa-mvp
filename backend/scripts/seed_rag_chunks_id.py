"""Seed curated FAQ chunks for US/GB/AU/FR in **Bahasa Indonesia (id)** so the
/v2/rag/checklist endpoint can serve Indonesian content when the frontend is
on the Indonesian locale.

Pairs with seed_rag_chunks_en.py (English variants) and seed_rag_chunks.py
(Chinese variants). Re-running this script is safe — existing Indonesian
chunks at the same (country, chunk_index) are overwritten.

Run:  cd backend && python scripts/seed_rag_chunks_id.py
"""
from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.rag import RagChunk, RagSource
from app.services.rag.embedder import embed

LANG = "id"

# Per-country curated FAQ chunks in Bahasa Indonesia.
# Same 3-chunk structure (materials / fee+timing / rejection reasons) as the
# Chinese and English variants for parser parity.
CHUNKS = {
    "US": [
        {
            "chunk_index": 0,
            "content": (
                "Dokumen yang Dibutuhkan untuk Visa B1/B2 Amerika Serikat (Turis/Bisnis):\n"
                "1. Paspor yang masih berlaku (minimal 6 bulan setelah tanggal rencana kepulangan)\n"
                "2. Halaman konfirmasi DS-160 (dicetak setelah pengisian online, dengan barcode)\n"
                "3. Tanda terima biaya aplikasi visa ($160 USD MRV fee)\n"
                "4. Satu foto berwarna latar belakang putih (51mm × 51mm, frontal, tanpa kacamata)\n"
                "5. Surat keterangan kerja atau salinan izin usaha (dengan cap perusahaan)\n"
                "6. Rekening koran atau sertifikat deposito terbaru (3 bulan terakhir disarankan)\n"
                "7. Itinierari perjalanan dan pemesanan tiket pesawat/hotel\n"
                "8. Surat konfirmasi wawancara (dihasilkan setelah menjadwalkan janji temu konsuler)"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Biaya Visa B1/B2 Amerika Serikat dan Waktu Proses:\n"
                "Biaya Visa: $160 USD (MRV fee), dibayar online sebelum menjadwalkan wawancara.\n"
                "Waktu Proses: Umumnya 5-15 hari kerja tergantung beban kerja kedutaan; musim ramai (musim panas, Tahun Baru Imlek) dapat memperpanjang hingga 3-4 minggu.\n"
                "Masa Berlaku: Biasanya diterbitkan sebagai visa masuk ganda 10 tahun (kategori B1/B2).\n"
                "Durasi Tinggal Maksimum: Ditentukan oleh petugas CBP di pelabuhan masuk, biasanya tidak melebihi 6 bulan per kunjungan.\n"
                "Tips Aplikasi: Jadwalkan wawancara sedini mungkin, siapkan jawaban yang ringkas dan jujur, atur dokumen sesuai urutan yang diminta."
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "Alasan Penolakan Visa B1/B2 Amerika Serikat yang Umum dan Dokumen Penguat:\n"
                "Penolakan Umum: Bagian 214(b) (dugaan niat imigrasi) — alasan penolakan paling umum.\n"
                "Dokumen Penguat: Bukti ikatan kuat dengan negara asal (sertifikat properti, surat keterangan kerja, kartu keluarga), riwayat perjalanan yang luas, laporan pendapatan stabil, rencana perjalanan ke AS yang terperinci.\n"
                "Tips Wawancara: Nyatakan tujuan wisata dengan jelas, jaga jawaban tetap ringkas dan jujur, hindari menyebut topik terkait imigrasi secara spontan.\n"
                "Pemohon Pertama (Paspor Kosong): Berikan bukti ikatan yang lebih kuat dengan negara asal."
            ),
        },
    ],
    "GB": [
        {
            "chunk_index": 0,
            "content": (
                "Dokumen yang Dibutuhkan untuk Visa Standard Visitor Inggris:\n"
                "1. Paspor yang masih berlaku (minimal satu halaman kosong)\n"
                "2. Formulir aplikasi online (dicetak setelah pengisian, dengan nomor referensi)\n"
                "3. Sertifikat tes Tuberkulosis (TB test, berlaku 6 bulan)\n"
                "4. Surat keterangan kerja atau surat keterangan pelajar\n"
                "5. Rekening koran terbaru (3 bulan terakhir, menunjukkan sumber pendapatan stabil)\n"
                "6. Pemesanan hotel dan tiket pesawat pulang-pergi\n"
                "7. Dua foto ukuran paspor latar belakang putih"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Biaya Visa Standard Visitor Inggris dan Waktu Proses:\n"
                "Biaya Visa: £95 GBP untuk visa kunjungan jangka pendek (6 bulan).\n"
                "Waktu Proses: Layanan standar 15 hari kerja; layanan prioritas 5 hari kerja; super prioritas 24 jam.\n"
                "Masa Berlaku: Hingga 6 bulan masuk ganda; visa kunjungan jangka panjang (2/5/10 tahun) tersedia dengan biaya lebih tinggi.\n"
                "Tes TB: Harus dilakukan di klinik yang disetujui Home Office di negara asal; sertifikat dari klinik lain tidak diterima."
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "Alasan Penolakan Visa Inggris yang Umum:\n"
                "Bukti keuangan tidak cukup: Saldo bank rendah atau sumber dana tidak jelas.\n"
                "Ikatan lemah dengan negara asal: Tidak dapat menunjukkan niat untuk meninggalkan Inggris tepat waktu (tanpa properti, tanpa pekerjaan tetap).\n"
                "Tes TB gagal: Pasien TB aktif harus menyelesaikan pengobatan sebelum mengajukan.\n"
                "Informasi aplikasi kontradiktif: Itinierari tidak sesuai dengan pemesanan hotel/penerbangan.\n"
                "Rekomendasi: Berikan dokumen asli yang lengkap, itinierari yang masuk akal, dan beli tiket pesawat/hotel yang tidak dapat dibatalkan (simpan bukti pembayaran)."
            ),
        },
    ],
    "AU": [
        {
            "chunk_index": 0,
            "content": (
                "Dokumen yang Dibutuhkan untuk Visa Turis Australia (Subclass 600):\n"
                "1. Paspor yang masih berlaku (salinan pindaian berwarna)\n"
                "2. Foto ukuran paspor terbaru\n"
                "3. Dokumen identitas (KTP, kartu keluarga)\n"
                "4. Surat keterangan kerja atau izin usaha\n"
                "5. Rekening koran terbaru (3-6 bulan terakhir)\n"
                "6. Itinierari perjalanan dan pemesanan tiket pesawat pulang-pergi\n"
                "7. Pemesanan hotel atau surat undangan dari tuan rumah di Australia"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Biaya Visa Turis Australia (Subclass 600) dan Waktu Proses:\n"
                "Biaya Visa: AUD $190 (sekitar Rp 2.000.000), dibayar online dengan kartu kredit.\n"
                "Waktu Proses: Standar 15-25 hari kerja; musim ramai (musim panas / Tahun Baru Imlek / Hari Nasional) dapat memperpanjang hingga 30-40 hari kerja.\n"
                "Masa Berlaku: Biasanya diterbitkan sebagai visa masuk ganda berlaku hingga 1 tahun; setiap kunjungan hingga 3 bulan.\n"
                "Tips Aplikasi: Ajukan setidaknya 1-2 bulan sebelum perjalanan; pastikan semua dokumen dalam bahasa Inggris atau disertai terjemahan resmi."
            ),
        },
    ],
    "FR": [
        {
            "chunk_index": 0,
            "content": (
                "Dokumen yang Dibutuhkan untuk Visa Schengen Prancis Jangka Pendek (Tipe C):\n"
                "1. Paspor yang masih berlaku (dikeluarkan dalam 10 tahun terakhir, berlaku minimal 3 bulan setelah tanggal kembali, minimal 2 halaman kosong)\n"
                "2. Formulir aplikasi visa Schengen (diisi dan ditandatangani)\n"
                "3. Dua foto terbaru latar belakang putih (35mm × 45mm, frontal)\n"
                "4. Asuransi perjalanan medis (mencakup area Schengen, minimum €30.000, berlaku selama seluruh masa tinggal)\n"
                "5. Pemesanan tiket pesawat pulang-pergi\n"
                "6. Pemesanan hotel atau bukti akomodasi untuk seluruh masa tinggal\n"
                "7. Surat keterangan kerja atau surat keterangan pelajar\n"
                "8. Rekening koran terbaru (3 bulan terakhir)\n"
                "9. Tanda terima pajak penghasilan pribadi atau sertifikat properti (opsional tapi memperkuat aplikasi)"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Biaya Visa Schengen Prancis dan Waktu Proses:\n"
                "Biaya Visa: €80 EUR (dewasa), €40 EUR (anak-anak 6-12 tahun), gratis untuk anak di bawah 6 tahun.\n"
                "Waktu Proses: Standar 15 hari kalender; dapat memperpanjang hingga 45 hari selama musim ramai atau jika diperlukan tinjauan tambahan.\n"
                "Masa Berlaku: Visa jangka pendek (hingga 90 hari dalam 180 hari); masuk ganda dimungkinkan berdasarkan riwayat perjalanan.\n"
                "Tips Aplikasi: Jadwalkan janji temu Anda di pusat aplikasi visa VFS Global setidaknya 4-6 minggu sebelum perjalanan; data biometrik (sidik jari) dikumpulkan pada janji temu."
            ),
        },
    ],
}


async def upsert_source(db, country_code: str) -> int:
    """Ensure a RagSource row exists for (country_code, lang); return its id."""
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