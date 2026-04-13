from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.models import Newsletter

URL_RE = re.compile(r"https?://[^\s]+")


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
        SourceItem(
            source_id=f"src_{index + 1}",
            url=url,
            title=url,
            summary=f"Operator-provided source URL for {newsletter.name}",
            source_type="operator_url",
        )
        for index, url in enumerate(deduped_urls)
    ]

    if source_items:
        return source_items

    return [
        SourceItem(
            source_id="src_context",
            url=f"pulse-news://newsletter/{newsletter.slug}",
            title=f"{newsletter.name} context",
            summary=(
                f"Fallback operator context for audience '{newsletter.audience_name}' and "
                f"topic '{newsletter.delivery_topic}'."
            ),
            source_type="operator_context",
        )
    ]


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
