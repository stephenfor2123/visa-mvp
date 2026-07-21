"""RAG pipeline regression tests — crawler / chunker / embedder / retriever /
refresh / API endpoints.

Covers the previously-untested `app/services/rag/*` modules and
`/api/v2/rag/*` endpoints (tests/rag/ was an empty directory before this).
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.api.v2.rag import _parse_materials_from_text, _split_respecting_parens
from app.core.db import AsyncSessionLocal
from app.models.rag import RagChunk, RagSource
from app.services.rag import crawler as crawler_mod
from app.services.rag.chunker import chunk_text
from app.services.rag.embedder import cosine_sim, embed, keyword_score
from app.services.rag.refresh import CURATED_CONTENT, refresh_all, refresh_source


# --------------------------------------------------------------------------- #
# Unit: chunker                                                                #
# --------------------------------------------------------------------------- #
class TestChunker:
    def test_short_text_single_chunk(self):
        chunks = chunk_text("短文本，不需要切分。", chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0].index == 0

    def test_empty_text_no_chunks(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_long_text_splits_with_overlap(self):
        # NOTE: the sentence-boundary regex requires whitespace *after* the
        # terminator (`(?<=[.!?。!?])\s+`), matching real curated content
        # where paragraphs are separated by "\n\n" but CJK sentences within
        # a paragraph run together without a space after "。".
        sentence = "这是一句用于测试切分逻辑的中文句子。\n\n"
        text = sentence * 60  # comfortably over chunk_size
        chunks = chunk_text(text, chunk_size=200, overlap=20)
        assert len(chunks) > 1
        # indices are sequential starting at 0
        assert [c.index for c in chunks] == list(range(len(chunks)))
        # every chunk respects the size budget with some slack for overlap prefix
        for c in chunks:
            assert len(c.text) <= 200 + 20 + len(sentence)

    def test_never_exceeds_chunk_size_by_much_for_short_sentences(self):
        text = "A. " * 500  # many tiny "sentences"
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c.text) < 200  # generous upper bound, no runaway growth


# --------------------------------------------------------------------------- #
# Unit: checklist material parsing (W38 — paren-aware split)                  #
# --------------------------------------------------------------------------- #
class TestSplitRespectingParens:
    def test_does_not_split_commas_inside_parens(self):
        section = "旅行医疗保险 (覆盖申根区, 保额 ≥ 3万欧元, 涵盖整个行程), 完整填写的申根签证申请表"
        parts = [p.strip(" ,") for p in _split_respecting_parens(section) if p.strip(" ,")]
        assert "旅行医疗保险 (覆盖申根区, 保额 ≥ 3万欧元, 涵盖整个行程)" in parts
        assert "涵盖整个行程)" not in parts  # would be an orphan fragment under the old bug

    def test_splits_top_level_separators(self):
        section = "护照原件、签证照片；申请表\n银行流水"
        parts = [p for p in _split_respecting_parens(section) if p]
        assert parts == ["护照原件", "签证照片", "申请表", "银行流水"]

    def test_splits_on_comma_space_outside_parens(self):
        section = "护照原件 (有效期6个月以上), 签证照片"
        parts = [p.strip(" ,") for p in _split_respecting_parens(section) if p.strip(" ,")]
        assert parts == ["护照原件 (有效期6个月以上)", "签证照片"]


class TestParseMaterialsFromText:
    def test_bracketed_multi_comma_detail_stays_one_item(self):
        text = "所需材料: 旅行医疗保险 (覆盖申根区, 保额 ≥ 3万欧元, 涵盖整个行程), 护照原件 (有效期6个月以上)\n\n签证费: 80欧元"
        items = _parse_materials_from_text(text)
        names = [i.name for i in items]
        assert "旅行医疗保险 (覆盖申根区, 保额 ≥ 3万欧元, 涵盖整个行程)" in names
        # the old bug produced an orphan "涵盖整个行程)" fragment as its own item
        assert not any(n.startswith("涵盖整个行程") for n in names)

    def test_all_curated_content_yields_well_formed_items(self):
        """Every real product line's curated FAQ must parse into items with
        balanced parens and no truncated/orphan fragments (W38 regression)."""
        for text in CURATED_CONTENT.values():
            items = _parse_materials_from_text(text)
            assert items, "expected at least one material item"
            for it in items:
                assert it.name.count("(") == it.name.count(")")
                assert it.name.count("（") == it.name.count("）")


# --------------------------------------------------------------------------- #
# Unit: embedder                                                              #
# --------------------------------------------------------------------------- #
class TestEmbedder:
    def test_embed_deterministic(self):
        v1 = embed("美国签证费用")
        v2 = embed("美国签证费用")
        assert v1 == v2

    def test_embed_dim_default(self):
        v = embed("hello world")
        assert len(v) == 256

    def test_embed_l2_normalized(self):
        v = embed("申根签证材料清单")
        norm = sum(x * x for x in v) ** 0.5
        assert norm == pytest.approx(1.0, abs=1e-6)

    def test_embed_empty_text_zero_vector(self):
        v = embed("")
        assert v == [0.0] * 256

    def test_cosine_sim_identical_is_one(self):
        v = embed("英国签证 申请材料")
        assert cosine_sim(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_cosine_sim_dim_mismatch_returns_zero(self):
        assert cosine_sim([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0

    def test_cosine_sim_unrelated_lower_than_related(self):
        a = embed("美国签证费用是多少")
        b = embed("美国签证费用")
        c = embed("巴西烤肉自助餐推荐")
        assert cosine_sim(a, b) > cosine_sim(a, c)

    def test_keyword_score_matches_overlap(self):
        score, matched = keyword_score("签证费用", "本次申请的签证费用较高")
        assert score > 0
        assert matched

    def test_keyword_score_no_overlap_is_zero(self):
        score, matched = keyword_score("签证费用", "今天天气不错")
        assert score == 0.0
        assert matched == []

    def test_keyword_score_empty_inputs(self):
        assert keyword_score("", "文本") == (0.0, [])
        assert keyword_score("查询", "") == (0.0, [])


# --------------------------------------------------------------------------- #
# Unit: crawler (network mocked — no real HTTP calls in tests)                #
# --------------------------------------------------------------------------- #
class TestCrawler:
    def test_fetch_url_http_error_status(self, monkeypatch):
        class _FakeResp:
            status_code = 404
            content = b""
            encoding = "utf-8"

        class _FakeClient:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get(self, url):
                return _FakeResp()

        monkeypatch.setattr(crawler_mod.httpx, "Client", _FakeClient)
        result = crawler_mod.fetch_url("https://example.com/gone")
        assert result.status == 404
        assert result.error == "http 404"
        assert result.text == ""

    def test_fetch_url_network_exception(self, monkeypatch):
        class _RaisingClient:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get(self, url):
                raise RuntimeError("connection refused")

        monkeypatch.setattr(crawler_mod.httpx, "Client", _RaisingClient)
        result = crawler_mod.fetch_url("https://unreachable.example")
        assert result.status == 0
        assert "connection refused" in (result.error or "")

    def test_fetch_url_regex_fallback_extracts_title_and_text(self, monkeypatch):
        html = (
            "<html><head><title>Visa Info</title>"
            '<meta name="description" content="Official visa page"></head>'
            "<body><script>ignored()</script>"
            "<p>Required documents: passport, photo.</p></body></html>"
        ).encode("utf-8")

        class _FakeResp:
            status_code = 200
            content = html
            encoding = "utf-8"

        class _FakeClient:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get(self, url):
                return _FakeResp()

        monkeypatch.setattr(crawler_mod.httpx, "Client", _FakeClient)
        monkeypatch.setattr(crawler_mod, "_TRAFILATURA", False)
        result = crawler_mod.fetch_url("https://example.com/visa")
        assert result.status == 200
        assert result.extractor == "regex"
        assert result.title == "Visa Info"
        assert result.description == "Official visa page"
        assert "Required documents" in result.text
        assert "<p>" not in result.text
        assert "ignored()" not in result.text


# --------------------------------------------------------------------------- #
# Integration: refresh pipeline + DB persistence                              #
# --------------------------------------------------------------------------- #
@pytest.fixture()
def curated_source_name():
    # Any real key from CURATED_CONTENT so refresh_source finds real text.
    return next(iter(CURATED_CONTENT))


class TestRefreshPipeline:
    async def test_refresh_curated_source_persists_chunks(self, app, curated_source_name):
        async with AsyncSessionLocal() as db:
            source = RagSource(
                name=curated_source_name,
                country_code="GB",
                url="https://www.gov.uk/standard-visitor",
                content_type="curated",
                enabled=True,
            )
            db.add(source)
            await db.commit()
            await db.refresh(source)
            source_id = source.id

            result = await refresh_source(db, source)
            assert result["status"] == "ok"
            assert result["chunk_count"] > 0

            chunks = (
                await db.execute(select(RagChunk).where(RagChunk.source_id == source_id))
            ).scalars().all()
            assert len(chunks) == result["chunk_count"]
            for c in chunks:
                vec = json.loads(c.embedding)
                assert len(vec) == c.embedding_dim
                assert c.embedding_dim > 0

    async def test_refresh_disabled_source_is_skipped(self, app, curated_source_name):
        async with AsyncSessionLocal() as db:
            source = RagSource(
                name=curated_source_name,
                country_code="GB",
                content_type="curated",
                enabled=False,
            )
            db.add(source)
            await db.commit()
            result = await refresh_source(db, source)
            assert result["status"] == "skipped"

    async def test_refresh_curated_source_unknown_name_errors(self, app):
        async with AsyncSessionLocal() as db:
            source = RagSource(
                name="不存在的签证 (curated FAQ)",
                country_code="ZZ",
                content_type="curated",
                enabled=True,
            )
            db.add(source)
            await db.commit()
            result = await refresh_source(db, source)
            assert result["status"] == "error"
            assert "no curated content" in result["error"]

    async def test_refresh_web_source_uses_crawler(self, app, monkeypatch):
        from app.services.rag import refresh as refresh_mod

        def _fake_fetch_url(url, **kw):
            return crawler_mod.CrawlResult(
                url=url,
                title="Fake Title",
                description=None,
                text="签证材料包括护照、照片和银行流水证明。" * 5,
                status=200,
                extractor="regex",
            )

        monkeypatch.setattr(refresh_mod, "fetch_url", _fake_fetch_url)

        async with AsyncSessionLocal() as db:
            source = RagSource(
                name="Fake Web Source",
                country_code="ZZ",
                url="https://example.com/visa",
                content_type="web",
                enabled=True,
            )
            db.add(source)
            await db.commit()
            result = await refresh_source(db, source)
            assert result["status"] == "ok"
            assert result["chunk_count"] > 0

    async def test_refresh_web_source_error_sets_last_error(self, app, monkeypatch):
        from app.services.rag import refresh as refresh_mod

        def _fake_fetch_url(url, **kw):
            return crawler_mod.CrawlResult(
                url=url, title=None, description=None, text="",
                status=404, error="http 404",
            )

        monkeypatch.setattr(refresh_mod, "fetch_url", _fake_fetch_url)

        async with AsyncSessionLocal() as db:
            source = RagSource(
                name="Broken Web Source",
                country_code="ZZ",
                url="https://example.com/missing",
                content_type="web",
                enabled=True,
            )
            db.add(source)
            await db.commit()
            result = await refresh_source(db, source)
            assert result["status"] == "error"
            assert source.last_status == "error"
            assert source.last_error

    async def test_refresh_idempotent_replaces_old_chunks(self, app, curated_source_name):
        async with AsyncSessionLocal() as db:
            source = RagSource(
                name=curated_source_name,
                country_code="GB",
                content_type="curated",
                enabled=True,
            )
            db.add(source)
            await db.commit()
            await db.refresh(source)

            first = await refresh_source(db, source)
            second = await refresh_source(db, source)
            assert first["chunk_count"] == second["chunk_count"]

            chunks = (
                await db.execute(select(RagChunk).where(RagChunk.source_id == source.id))
            ).scalars().all()
            # not doubled — old chunks were wiped before re-insert
            assert len(chunks) == second["chunk_count"]

    async def test_refresh_all_filters_by_country(self, app):
        async with AsyncSessionLocal() as db:
            for name, cc in list(CURATED_CONTENT.items())[:2]:
                db.add(RagSource(name=name, country_code="XX1", content_type="curated", enabled=True))
            db.add(RagSource(
                name=list(CURATED_CONTENT.keys())[2], country_code="XX2",
                content_type="curated", enabled=True,
            ))
            await db.commit()

            results = await refresh_all(db, country_code="XX1")
            assert len(results) == 2
            assert all(r["status"] == "ok" for r in results)


# --------------------------------------------------------------------------- #
# Integration: HTTP API                                                       #
# --------------------------------------------------------------------------- #
async def _register(client, username: str, email: str, password: str = "Pass1234") -> str:
    r = await client.post(
        "/api/v2/auth/register",
        json={"username": username, "email": email, "password": password, "email_code": "123456", "age_confirmed_16": True},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["access_token"]


async def _admin_token(client) -> str:
    r = await client.post(
        "/api/v2/admin/login",
        json={"username": "admin", "password": "visa-admin-2024"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _seed_curated_source(country_code: str, name: str) -> int:
    async with AsyncSessionLocal() as db:
        source = RagSource(name=name, country_code=country_code, content_type="curated", enabled=True)
        db.add(source)
        await db.commit()
        await db.refresh(source)
        await refresh_source(db, source)
        return source.id


class TestRagSourcesEndpoint:
    async def test_list_sources_requires_login(self, client):
        r = await client.get("/api/v2/rag/sources")
        assert r.status_code == 401

    async def test_list_sources_authenticated(self, client):
        token = await _register(client, "raguser1", "raguser1@htex.test")
        await _seed_curated_source("GB", next(iter(CURATED_CONTENT)))
        r = await client.get(
            "/api/v2/rag/sources", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 1
        assert data[0]["country_code"] == "GB"
        assert data[0]["last_status"] == "ok"


class TestRagRefreshEndpoint:
    async def test_refresh_requires_admin_token(self, client):
        r = await client.post("/api/v2/rag/refresh")
        assert r.status_code == 401

    async def test_refresh_rejects_user_token(self, client):
        token = await _register(client, "raguser2", "raguser2@htex.test")
        r = await client.post(
            "/api/v2/rag/refresh", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code in (401, 403)

    async def test_refresh_as_admin_persists_chunks(self, client):
        async with AsyncSessionLocal() as db:
            for name in list(CURATED_CONTENT.keys())[:2]:
                db.add(RagSource(name=name, country_code="GB", content_type="curated", enabled=True))
            await db.commit()

        admin_tok = await _admin_token(client)
        r = await client.post(
            "/api/v2/rag/refresh", headers={"Authorization": f"Bearer {admin_tok}"}
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["refreshed"] == 2
        assert data["errors"] == 0

    async def test_refresh_filtered_by_country_code(self, client):
        names = list(CURATED_CONTENT.keys())
        async with AsyncSessionLocal() as db:
            db.add(RagSource(name=names[0], country_code="GB", content_type="curated", enabled=True))
            db.add(RagSource(name=names[1], country_code="US", content_type="curated", enabled=True))
            await db.commit()

        admin_tok = await _admin_token(client)
        r = await client.post(
            "/api/v2/rag/refresh?country_code=US",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["refreshed"] == 1


class TestRagQueryEndpoint:
    async def test_query_no_data_returns_no_result_message(self, client):
        r = await client.post("/api/v2/rag/query", json={"query": "签证费用是多少"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["chunks"] == []
        assert "未找到相关官方信息" in data["answer"]

    async def test_query_public_no_auth_required(self, client):
        await _seed_curated_source("US", "美国 B1/B2 旅游商务签证 (curated FAQ)")
        r = await client.post(
            "/api/v2/rag/query",
            json={"query": "美国签证费用是多少", "country_code": "US"},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data["chunks"]) > 0
        assert data["chunks"][0]["source_name"] == "美国 B1/B2 旅游商务签证 (curated FAQ)"
        assert "来源" in data["answer"]
        assert len(data["followups"]) == 3

    async def test_query_debug_flag_includes_score_breakdown(self, client):
        await _seed_curated_source("GB", "英国 Standard Visitor 签证 (curated FAQ)")
        r = await client.post(
            "/api/v2/rag/query",
            json={"query": "英国签证材料", "country_code": "GB", "debug": True},
        )
        assert r.status_code == 200
        debug = r.json()["data"]["debug"]
        assert debug is not None
        assert "hybrid_weights" in debug
        assert debug["chunks"]

    async def test_query_country_filter_excludes_other_countries(self, client):
        await _seed_curated_source("GB", "英国 Standard Visitor 签证 (curated FAQ)")
        await _seed_curated_source("US", "美国 B1/B2 旅游商务签证 (curated FAQ)")
        r = await client.post(
            "/api/v2/rag/query",
            json={"query": "签证材料要求", "country_code": "US"},
        )
        assert r.status_code == 200
        for chunk in r.json()["data"]["chunks"]:
            assert chunk["source_name"] == "美国 B1/B2 旅游商务签证 (curated FAQ)"


class TestRagChecklistEndpoint:
    async def test_checklist_extracts_materials_for_seeded_country(self, client):
        await _seed_curated_source("GB", "英国 Standard Visitor 签证 (curated FAQ)")
        r = await client.get("/api/v2/rag/checklist", params={"country_code": "GB"})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["country_code"] == "GB"
        assert len(data["materials"]) > 0
        names = [m["name"] for m in data["materials"]]
        assert any("护照" in n for n in names)
        categories = {m["category"] for m in data["materials"]}
        assert "financial" in categories

    async def test_checklist_normalizes_legacy_uk_code_to_gb(self, client):
        await _seed_curated_source("GB", "英国 Standard Visitor 签证 (curated FAQ)")
        r = await client.get("/api/v2/rag/checklist", params={"country_code": "UK"})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["country_code"] == "GB"
        assert len(data["materials"]) > 0
        assert data["source_name"] == "英国 Standard Visitor 签证 (curated FAQ)"

    async def test_checklist_extracts_fee_and_processing_time(self, client):
        await _seed_curated_source("GB", "英国 Standard Visitor 签证 (curated FAQ)")
        r = await client.get("/api/v2/rag/checklist", params={"country_code": "GB"})
        data = r.json()["data"]
        assert data["fee"] is not None
        assert data["processing_time"] is not None

    async def test_checklist_unknown_country_falls_back_to_retrieval_empty(self, client):
        r = await client.get("/api/v2/rag/checklist", params={"country_code": "ZZ"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["materials"] == []

    async def test_checklist_schengen_member_falls_back_to_france_content(self, client):
        # Only "FR" carries curated Schengen content; other 25 member states
        # (e.g. DE) must still resolve materials via the W35 fallback.
        await _seed_curated_source("FR", "申根 (Schengen) 短期签证 (curated FAQ)")
        r = await client.get("/api/v2/rag/checklist", params={"country_code": "DE"})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["country_code"] == "DE"
        assert len(data["materials"]) > 0
        assert data["source_name"] == "申根 (Schengen) 短期签证 (curated FAQ)"

    async def test_checklist_non_schengen_country_does_not_use_fallback(self, client):
        # A non-Schengen country with no seeded source must NOT silently
        # inherit France's content — it should stay empty.
        await _seed_curated_source("FR", "申根 (Schengen) 短期签证 (curated FAQ)")
        r = await client.get("/api/v2/rag/checklist", params={"country_code": "JP"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["materials"] == []
