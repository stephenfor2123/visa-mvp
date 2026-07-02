"""W40/W41 — LLM itinerary field fill-in (transport/hotel/attraction). MiniMax
is mocked; no network/balance dependency, so these run in CI without a real
API key.
"""
from __future__ import annotations

import json

import pytest

from app.services.llm.itinerary_generator import (
    _build_flight_context,
    _build_prompt,
    _extract_json_array,
    generate_itinerary_fields,
)
from app.services.llm.minimax_client import MiniMaxError


def _day(day, date, city, transport="", hotel="", attraction=""):
    return {"day": day, "date": date, "city": city, "transport": transport, "hotel": hotel, "attraction": attraction}


class TestExtractJsonArray:
    def test_plain_json(self):
        text = '[{"day": 1, "attraction": "Eiffel Tower"}]'
        assert _extract_json_array(text) == [{"day": 1, "attraction": "Eiffel Tower"}]

    def test_json_in_markdown_fence(self):
        text = '```json\n[{"day": 1, "attraction": "Eiffel Tower"}]\n```'
        assert _extract_json_array(text) == [{"day": 1, "attraction": "Eiffel Tower"}]

    def test_json_with_surrounding_commentary(self):
        text = 'Here is the itinerary:\n[{"day": 1, "attraction": "Eiffel Tower"}]\nHope this helps!'
        assert _extract_json_array(text) == [{"day": 1, "attraction": "Eiffel Tower"}]

    def test_no_array_raises(self):
        with pytest.raises(MiniMaxError):
            _extract_json_array("sorry, I cannot help with that")


class TestBuildPrompt:
    def test_includes_country_and_days(self):
        days = [_day(1, "2026-08-01", "Paris")]
        messages = _build_prompt(days, "France", "en")
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "France" in messages[1]["content"]
        assert "Paris" in messages[1]["content"]

    def test_lang_name_in_system_prompt(self):
        messages = _build_prompt([], "France", "vi-VN")
        assert "Vietnamese" in messages[0]["content"]

    def test_flight_context_included(self):
        days = [_day(1, "2026-08-01", "Paris")]
        flight_ctx = {
            "origin": "Beijing", "destination": "Paris",
            "flight_out_no": "CA933", "flight_back_no": "CA934",
            "depart_date": "2026-08-01", "return_date": "2026-08-06",
        }
        messages = _build_prompt(days, "France", "en", flight_ctx)
        content = messages[1]["content"]
        assert "CA933" in content
        assert "CA934" in content
        assert "Beijing" in content

    def test_matches_by_date_not_position(self):
        # W42: the prompt must tell the model to match flight days by DATE,
        # not by "day 1 / last row" — a day list can be reordered or extended
        # without breaking which day is the arrival/departure day.
        messages = _build_prompt([_day(1, "2026-08-01", "Paris")], "France", "en")
        assert "date" in messages[0]["content"].lower()
        assert "position" in messages[0]["content"].lower() or "DATE" in messages[0]["content"]

    def test_no_flight_context_does_not_crash(self):
        messages = _build_prompt([_day(1, "2026-08-01", "Paris")], "France", "en", None)
        assert messages[1]["role"] == "user"


class TestBuildFlightContext:
    def test_matches_outbound_and_return_by_date(self):
        ctx = _build_flight_context({
            "origin": "Beijing", "destination": "Paris",
            "flight_out_no": "CA933", "flight_back_no": "CA934",
            "depart_date": "2026-08-01", "return_date": "2026-08-06",
        })
        assert 'date == "2026-08-01"' in ctx
        assert 'date == "2026-08-06"' in ctx
        assert "Beijing -> Paris" in ctx

    def test_open_jaw_return_uses_explicit_cities_not_outbound_reversed(self):
        # W42: return leg is independently editable — flying into Paris,
        # out of Rome, is a valid (open-jaw) trip. The old positional
        # "Trip: A -> B -> A" framing assumed a round trip to the same city.
        ctx = _build_flight_context({
            "origin": "Beijing", "destination": "Paris",
            "return_origin": "Rome", "return_destination": "Beijing",
            "flight_out_no": "CA933", "flight_back_no": "CA934",
            "depart_date": "2026-08-01", "return_date": "2026-08-06",
        })
        assert "Rome -> Beijing" in ctx
        assert "Paris -> Beijing" not in ctx  # must NOT assume return reverses the outbound

    def test_return_defaults_to_reverse_outbound_when_not_set(self):
        # backward-compat: if the user never touches the new return fields,
        # behave like before (destination -> origin).
        ctx = _build_flight_context({
            "origin": "Beijing", "destination": "Paris",
            "flight_out_no": "CA933", "flight_back_no": "CA934",
            "depart_date": "2026-08-01", "return_date": "2026-08-06",
        })
        assert "Paris -> Beijing" in ctx

    def test_no_context_returns_empty_string(self):
        assert _build_flight_context(None) == ""
        assert _build_flight_context({}) == ""


class TestGenerateItineraryFields:
    async def test_skips_llm_call_when_nothing_blank(self, monkeypatch):
        called = False

        async def fake_chat(self, messages, **kw):
            nonlocal called
            called = True
            return "[]"

        monkeypatch.setattr("app.services.llm.minimax_client.MiniMaxClient.chat", fake_chat)
        days = [_day(1, "2026-08-01", "Paris", transport="flight", hotel="Hotel Ibis", attraction="Louvre")]
        # W47 — also fill the English mirror fields, otherwise the
        # "English mirror missing" check in _needs_llm still triggers.
        days[0]["city_en"] = "Paris"
        days[0]["hotel_en"] = "Hotel Ibis"
        days[0]["attraction_en"] = "Louvre"
        out = await generate_itinerary_fields(days, "France", "en")
        assert out == days
        assert called is False

    async def test_fills_blank_transport_hotel_attraction(self, monkeypatch):
        async def fake_chat(self, messages, **kw):
            return json.dumps([
                {"day": 1, "date": "2026-08-01", "city": "Paris", "transport": "flight", "hotel": "Hotel Lutetia", "attraction": "Eiffel Tower"},
            ])

        monkeypatch.setattr("app.services.llm.minimax_client.MiniMaxClient.chat", fake_chat)
        monkeypatch.setattr("app.services.llm.minimax_client.MiniMaxClient.configured", property(lambda self: True))
        days = [_day(1, "2026-08-01", "Paris")]
        out = await generate_itinerary_fields(days, "France", "en")
        assert out[0]["transport"] == "flight"
        assert out[0]["hotel"] == "Hotel Lutetia"
        assert out[0]["attraction"] == "Eiffel Tower"

    async def test_never_overwrites_user_filled_fields(self, monkeypatch):
        async def fake_chat(self, messages, **kw):
            return json.dumps([
                {"day": 1, "date": "2026-08-01", "city": "Paris", "transport": "train", "hotel": "SHOULD NOT BE USED", "attraction": "SHOULD NOT BE USED"},
                {"day": 2, "date": "2026-08-02", "city": "Paris", "transport": "walk", "hotel": "Hotel B", "attraction": "Louvre"},
            ])

        monkeypatch.setattr("app.services.llm.minimax_client.MiniMaxClient.chat", fake_chat)
        days = [
            _day(1, "2026-08-01", "Paris", hotel="User Hotel (keep)"),
            _day(2, "2026-08-02", "Paris"),
        ]
        out = await generate_itinerary_fields(days, "France", "en")
        assert out[0]["hotel"] == "User Hotel (keep)"  # never overwritten
        assert out[0]["transport"] == "train"  # was blank, filled
        assert out[1]["hotel"] == "Hotel B"
        assert out[1]["attraction"] == "Louvre"

    async def test_ignores_invalid_transport_value(self, monkeypatch):
        async def fake_chat(self, messages, **kw):
            return json.dumps([{"day": 1, "date": "2026-08-01", "city": "Paris", "transport": "spaceship", "hotel": "Hotel A", "attraction": "Louvre"}])

        monkeypatch.setattr("app.services.llm.minimax_client.MiniMaxClient.chat", fake_chat)
        days = [_day(1, "2026-08-01", "Paris")]
        out = await generate_itinerary_fields(days, "France", "en")
        assert out[0]["transport"] == ""  # invalid value rejected, stays blank
        assert out[0]["hotel"] == "Hotel A"

    async def test_upstream_error_propagates(self, monkeypatch):
        async def fake_chat(self, messages, **kw):
            raise MiniMaxError("MiniMax error 1008: insufficient balance")

        monkeypatch.setattr("app.services.llm.minimax_client.MiniMaxClient.chat", fake_chat)
        days = [_day(1, "2026-08-01", "Paris")]
        with pytest.raises(MiniMaxError, match="insufficient balance"):
            await generate_itinerary_fields(days, "France", "en")
