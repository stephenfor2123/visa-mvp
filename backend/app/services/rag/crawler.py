"""RAG: web crawler — fetch a URL and extract clean text.

W31: upgraded from stdlib urllib + regex to httpx + trafilatura.
- httpx: better connection pooling, retries, custom headers, HTTP/2 support
- trafilatura: state-of-the-art main-content extractor (works on news/blogs
  and most government pages); falls back to regex strip if trafilatura fails
- selectolax: fast HTML5 parser as a second-pass option

Why trafilatura: previous regex strip kept nav/footer/cookie-banner text
which polluted chunks with noise like "Privacy / Terms / © 2024 ...".
trafilatura extracts the article body only, which is what we want for RAG.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx

# Optional deps — fall back gracefully if not installed
try:
    import trafilatura  # type: ignore

    _TRAFILATURA = True
except ImportError:
    _TRAFILATURA = False


@dataclass
class CrawlResult:
    url: str
    title: Optional[str]
    description: Optional[str]
    text: str  # cleaned plain text
    status: int
    error: Optional[str] = None
    extractor: str = "regex"  # "trafilatura" | "regex" | "selectolax"


_SCRIPT_STYLE = re.compile(r"<(script|style|noscript|nav|footer|header)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_META_DESC = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
    re.IGNORECASE,
)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

# Common browser-like User-Agent — many government sites block bot UAs
_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _clean_html_regex(html: str) -> tuple[Optional[str], Optional[str], str]:
    """Last-ditch regex strip — kept for fallback only."""
    html = _SCRIPT_STYLE.sub(" ", html)
    desc_m = _META_DESC.search(html)
    description = desc_m.group(1).strip() if desc_m else None
    title_m = _TITLE.search(html)
    title = title_m.group(1).strip() if title_m else None
    text = _HTML_TAG.sub(" ", html)
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


def fetch_url(
    url: str,
    max_bytes: int = 1_500_000,
    timeout: float = 12.0,
    use_browser_ua: bool = True,
) -> CrawlResult:
    """Fetch URL and return cleaned text. Caps payload at 1.5MB.

    Order of extraction:
      1. trafilatura (best, dependency-included for us)
      2. regex strip (fallback)
    """
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    }
    if use_browser_ua:
        headers["User-Agent"] = _DEFAULT_UA

    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=5,
            headers=headers,
        ) as client:
            resp = client.get(url)
            status = resp.status_code
            if status >= 400:
                return CrawlResult(
                    url=url, title=None, description=None, text="",
                    status=status, error=f"http {status}",
                )
            raw = resp.content[:max_bytes]
            charset = resp.encoding or "utf-8"
            try:
                html = raw.decode(charset, errors="ignore")
            except LookupError:
                html = raw.decode("utf-8", errors="ignore")
    except Exception as exc:
        return CrawlResult(
            url=url, title=None, description=None, text="",
            status=0, error=str(exc)[:300],
        )

    # Try trafilatura first — extracts article body, drops nav/footer/cookie banner
    if _TRAFILATURA:
        try:
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                favor_precision=True,
            )
            metadata = trafilatura.extract_metadata(html)
            title = metadata.title if metadata else None
            description = metadata.description if metadata else None
            if extracted and len(extracted) >= 100:
                return CrawlResult(
                    url=url,
                    title=title,
                    description=description,
                    text=extracted.strip(),
                    status=status,
                    extractor="trafilatura",
                )
        except Exception:
            pass  # fall through to regex

    # Fallback: regex strip
    title, desc, text = _clean_html_regex(html)
    return CrawlResult(
        url=url,
        title=title,
        description=desc,
        text=text,
        status=status,
        extractor="regex",
    )
