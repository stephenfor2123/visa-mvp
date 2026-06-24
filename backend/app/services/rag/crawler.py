"""RAG: web crawler — fetch a URL and extract clean text.

For the MVP we use stdlib + simple regex. No external parser dependency
(BeautifulSoup would be better but stdlib keeps the surface area small).
"""
from __future__ import annotations

import re
import socket
import urllib.request
from dataclasses import dataclass
from typing import Optional

socket.setdefaulttimeout(10)


@dataclass
class CrawlResult:
    url: str
    title: Optional[str]
    description: Optional[str]
    text: str  # cleaned plain text
    status: int
    error: Optional[str] = None


_SCRIPT_STYLE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_META_DESC = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
    re.IGNORECASE,
)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _clean_html(html: str) -> tuple[Optional[str], Optional[str], str]:
    # strip script/style/noscript blocks first
    html = _SCRIPT_STYLE.sub(" ", html)
    # meta description
    desc_m = _META_DESC.search(html)
    description = desc_m.group(1).strip() if desc_m else None
    # title
    title_m = _TITLE.search(html)
    title = title_m.group(1).strip() if title_m else None
    # strip remaining tags
    text = _HTML_TAG.sub(" ", html)
    # decode common entities
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    text = _WS.sub(" ", text).strip()
    return title, description, text


def fetch_url(url: str, max_bytes: int = 1_500_000) -> CrawlResult:
    """Fetch URL and return cleaned text. Caps payload at 1.5MB."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "visa-mvp-rag/0.1 (+https://visa-mvp.example)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read(max_bytes)
            status = resp.status
            charset = resp.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="ignore")
    except Exception as exc:
        return CrawlResult(url=url, title=None, description=None, text="", status=0, error=str(exc)[:300])
    title, desc, text = _clean_html(html)
    return CrawlResult(url=url, title=title, description=desc, text=text, status=status)
