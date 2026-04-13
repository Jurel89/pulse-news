from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html import unescape
from urllib import request
from urllib.parse import urlparse

from app.models import Newsletter

URL_RE = re.compile(r"https?://[^\s]+")
HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class SourceItem:
    source_id: str
    url: str
    title: str
    summary: str
    source_type: str
    published_at: str | None
    relevance_score: float
    dedupe_hash: str


def build_source_bundle(newsletter: Newsletter) -> list[SourceItem]:
    raw_sources = []
    for candidate in (newsletter.prompt, newsletter.notes, newsletter.draft_body_text):
        if candidate:
            raw_sources.extend(URL_RE.findall(candidate))

    deduped_urls: list[str] = []
    for url in raw_sources:
        if url not in deduped_urls:
            deduped_urls.append(url)

    source_items = [
        _fetch_source_item(newsletter, url=url, index=index + 1)
        for index, url in enumerate(deduped_urls)
    ]

    return source_items


def _fetch_source_item(newsletter: Newsletter, *, url: str, index: int) -> SourceItem:
    try:
        req = request.Request(url, headers={"User-Agent": "Pulse-News/1.0"})
        with request.urlopen(req, timeout=5) as response:
            raw_content = response.read(120_000).decode("utf-8", errors="ignore")
    except Exception as exc:  # pragma: no cover - network availability varies
        return SourceItem(
            source_id=f"src_{index}",
            url=url,
            title=url,
            summary=f"Unable to fetch source content directly: {type(exc).__name__}",
            source_type="operator_url_unfetched",
            published_at=None,
            relevance_score=0.0,
            dedupe_hash=_dedupe_hash(url, ""),
        )

    cleaned = unescape(HTML_TAG_RE.sub(" ", raw_content))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    summary = cleaned[:320] if cleaned else f"Fetched source content for {newsletter.name}"
    last_modified = response.headers.get("Last-Modified") if hasattr(response, "headers") else None
    return SourceItem(
        source_id=f"src_{index}",
        url=url,
        title=url,
        summary=summary,
        source_type="operator_url_fetched",
        published_at=_normalize_published_at(last_modified),
        relevance_score=_relevance_score(newsletter, url, summary),
        dedupe_hash=_dedupe_hash(url, summary),
    )


def serialize_source_bundle(source_items: list[SourceItem]) -> str:
    return json.dumps([asdict(item) for item in source_items])


def has_usable_source_bundle(source_items: list[SourceItem]) -> bool:
    return any(item.source_type == "operator_url_fetched" for item in source_items)


def _dedupe_hash(url: str, summary: str) -> str:
    return hashlib.sha256(f"{url}\n{summary}".encode()).hexdigest()[:16]


def _normalize_published_at(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z")
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC).isoformat()


def _relevance_score(newsletter: Newsletter, url: str, summary: str) -> float:
    haystack = (
        f"{newsletter.name} {newsletter.description or ''} "
        f"{newsletter.prompt} {newsletter.delivery_topic}"
    ).lower()
    tokens = {token for token in re.split(r"[^a-z0-9]+", haystack) if len(token) > 3}
    source_text = f"{urlparse(url).netloc} {url} {summary}".lower()
    hits = sum(1 for token in tokens if token in source_text)
    if not tokens:
        return 0.5
    return round(min(1.0, max(0.1, hits / max(len(tokens), 1))), 2)
