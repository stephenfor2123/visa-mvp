"""LLM-assisted itinerary fill-in (W40, extended W41/W42).

Given a day-by-day itinerary skeleton (date + city, optionally transport/
hotel/attraction already filled in by the user), asks MiniMax to fill in
blank `transport`, `hotel`, and `attraction` fields. `city` is always
user-owned and is never touched here.

Flight context is built from the outbound leg (origin -> destination,
depart_date, flight_out_no) and the return leg (return_origin ->
return_destination, return_date, flight_back_no) — both explicitly editable
by the user, independent of each other (open-jaw trips: the return doesn't
have to go back to the same city the outbound came from). Which day is the
arrival/departure day is matched by DATE (day.date == depart_date /
day.date == return_date), never by table position (day 1 / last row) —
the day list can be reordered or extended without breaking this.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from app.services.llm.minimax_client import MiniMaxError, get_minimax_client

_LANG_NAMES = {
    "zh-CN": "Simplified Chinese (简体中文)",
    "en": "English",
    "vi-VN": "Vietnamese",
    "id-ID": "Indonesian",
}

_TRANSPORT_VALUES = ("flight", "train", "car", "bus", "walk", "other")


def _build_flight_context(flight_ctx: Optional[dict[str, Any]]) -> str:
    if not flight_ctx:
        return ""
    lines = []
    origin = flight_ctx.get("origin")
    destination = flight_ctx.get("destination")
    return_origin = flight_ctx.get("return_origin") or destination
    return_destination = flight_ctx.get("return_destination") or origin
    depart_date = flight_ctx.get("depart_date")
    return_date = flight_ctx.get("return_date")

    if flight_ctx.get("flight_out_no") and origin and destination and depart_date:
        lines.append(
            f"Outbound flight {flight_ctx['flight_out_no']}: {origin} -> {destination}, "
            f"arriving on {depart_date}. Match this to the day entry whose date == \"{depart_date}\" "
            "— that day's transport should be 'flight' (it's an arrival day with limited time)."
        )
    if flight_ctx.get("flight_back_no") and return_origin and return_destination and return_date:
        lines.append(
            f"Return flight {flight_ctx['flight_back_no']}: {return_origin} -> {return_destination}, "
            f"departing on {return_date}. Match this to the day entry whose date == \"{return_date}\" "
            "— that day's transport should be 'flight' (it's a departure day)."
        )
    if not lines and origin and destination:
        lines.append(f"Outbound: {origin} -> {destination}. Return: {return_origin} -> {return_destination}.")
    return "\n".join(lines)


def _build_prompt(
    days: list[dict[str, Any]],
    country_name: str,
    lang: str,
    flight_ctx: Optional[dict[str, Any]] = None,
) -> list[dict[str, str]]:
    lang_name = _LANG_NAMES.get(lang, "Simplified Chinese (简体中文)")
    day_lines = []
    for d in days:
        day_lines.append(json.dumps({
            "day": d.get("day"),
            "date": d.get("date", ""),
            "city": d.get("city", ""),
            "transport": d.get("transport", ""),
            "hotel": d.get("hotel", ""),
            "attraction": d.get("attraction", ""),
        }, ensure_ascii=False))
    skeleton = "[\n  " + ",\n  ".join(day_lines) + "\n]"
    flight_info = _build_flight_context(flight_ctx)
    system = (
        "You are a travel itinerary assistant helping a visa applicant fill in a "
        "day-by-day trip plan. You will be given flight context and a JSON array "
        "of day entries (day number, date, city, and 'transport'/'hotel'/'attraction' "
        "fields that may be blank). For every entry with a blank field, fill it in:\n"
        f"- 'transport': exactly one of {', '.join(_TRANSPORT_VALUES)}. Match the flight "
        "context by DATE (not by position in the list) — the day whose 'date' equals the "
        "outbound flight's date, and the day whose 'date' equals the return flight's date, "
        "should both be 'flight'; infer a sensible mode for other days where the city "
        "changes from the previous day (e.g. 'train'), otherwise a local mode.\n"
        "- 'hotel': one real, well-known, centrally-located hotel name in that city, "
        f"written in {lang_name}.\n"
        "- 'attraction': 1-2 well-known, plausible attractions or activities for that "
        f"city, written in {lang_name}, suitable for a short tourist/business visa trip.\n"
        "ALSO, for EVERY entry (whether or not you filled a field), output English "
        "mirror fields — this document is bilingual (target language + English) for a "
        "consulate:\n"
        "- 'city_en': the city's common English (or romanized) name.\n"
        "- 'hotel_en': the hotel's official/romanized English name.\n"
        "- 'attraction_en': the same attraction(s), in English.\n"
        f"If {lang_name} is already English, copy each value into its *_en field verbatim.\n"
        "NEVER change 'day', 'date', or 'city'. NEVER overwrite a localized field that is "
        "already non-empty — copy it through unchanged (but still produce its *_en mirror). "
        "Respond with ONLY a JSON array in the exact same shape as the input plus the three "
        "English mirror keys (objects with day, date, city, transport, hotel, attraction, "
        "city_en, hotel_en, attraction_en) — no markdown code fences, no commentary."
    )
    user = f"Destination country: {country_name}\n{flight_info}\n\nDay entries:\n{skeleton}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", cleaned)
    if fence:
        cleaned = fence.group(1)
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise MiniMaxError("MiniMax response did not contain a JSON array")
    return json.loads(cleaned[start : end + 1])


def _is_blank(value: Any) -> bool:
    return not (str(value or "").strip())


async def generate_itinerary_fields(
    days: list[dict[str, Any]],
    country_name: str,
    lang: str = "zh-CN",
    flight_ctx: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Return a new `days` list with blank transport/hotel/attraction fields filled in.

    Raises MiniMaxError (not configured / upstream failure) — caller maps
    this to a BizException so the frontend gets a clean error toast instead
    of a stack trace.
    """
    # Run the LLM if any localized field is blank OR any English mirror is
    # missing for a non-empty localized field (W47 — the bilingual PDF needs
    # an English mirror for every filled city/hotel/attraction).
    def _needs_llm(d: dict[str, Any]) -> bool:
        if _is_blank(d.get("transport")) or _is_blank(d.get("hotel")) or _is_blank(d.get("attraction")):
            return True
        return (
            (not _is_blank(d.get("city")) and _is_blank(d.get("city_en")))
            or (not _is_blank(d.get("hotel")) and _is_blank(d.get("hotel_en")))
            or (not _is_blank(d.get("attraction")) and _is_blank(d.get("attraction_en")))
        )

    if not any(_needs_llm(d) for d in days):
        return days  # nothing to fill or translate, skip the LLM round-trip entirely

    client = get_minimax_client()
    messages = _build_prompt(days, country_name, lang, flight_ctx)
    content = await client.chat(messages, temperature=0.7)

    try:
        filled = _extract_json_array(content)
    except (json.JSONDecodeError, MiniMaxError) as exc:
        raise MiniMaxError(f"could not parse MiniMax response as JSON: {exc}") from exc

    filled_by_day = {int(item["day"]): item for item in filled if "day" in item}
    result = []
    for d in days:
        out = dict(d)
        match = filled_by_day.get(d.get("day"))
        if match:
            if _is_blank(d.get("transport")) and match.get("transport") in _TRANSPORT_VALUES:
                out["transport"] = match["transport"]
            if _is_blank(d.get("hotel")) and match.get("hotel"):
                out["hotel"] = str(match["hotel"]).strip()
            if _is_blank(d.get("attraction")) and match.get("attraction"):
                out["attraction"] = str(match["attraction"]).strip()
            # English mirrors — always take the LLM's value (it describes the
            # final localized value); only overwrite when the LLM provided one.
            for en_key in ("city_en", "hotel_en", "attraction_en"):
                if match.get(en_key):
                    out[en_key] = str(match[en_key]).strip()
        result.append(out)
    return result
