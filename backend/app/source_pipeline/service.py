from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from urllib import request

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
        )

    cleaned = unescape(HTML_TAG_RE.sub(" ", raw_content))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    summary = cleaned[:320] if cleaned else f"Fetched source content for {newsletter.name}"
    return SourceItem(
        source_id=f"src_{index}",
        url=url,
        title=url,
        summary=summary,
        source_type="operator_url_fetched",
    )


def serialize_source_bundle(source_items: list[SourceItem]) -> str:
    return json.dumps(
        [
            {
                "source_id": item.source_id,
                "url": item.url,
                "title": item.title,
                "summary": item.summary,
                "source_type": item.source_type,
            }
            for item in source_items
        ]
    )
