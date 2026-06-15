"""modules/news/schema.py — news shapes (NEWS-1). FROZEN on commit.

A NewsItem is one captured headline: title + short summary + the SOURCE url it came
from + when it was published + which feed + asset/topic tags. The digest is a NEUTRAL
roll-up: it ONLY lists captured items, each citing its source — no commentary, no
prediction, no "good/bad for price".
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    """One captured news headline. `url` is the real source link (grounding anchor);
    `publishedTs` is ISO-8601 UTC; `tags` are uppercased asset symbols / topic words."""

    id: int = Field(..., description="row id")
    title: str = Field(..., min_length=1)
    summary: str = Field("", description="short blurb from the feed (may be empty)")
    url: str = Field(..., min_length=1, description="source link — the grounding anchor")
    source: str = Field(..., description="feed name, e.g. 'CoinDesk'")
    publishedTs: str = Field(..., description="ISO-8601 UTC publish time")
    tags: list[str] = Field(default_factory=list, description="asset symbols / topics")


class NewsList(BaseModel):
    """GET /news payload — captured headlines (newest first) + count + the asof of the
    last successful capture (None if never captured)."""

    items: list[NewsItem] = Field(default_factory=list)
    count: int = 0
    asOf: str | None = Field(None, description="ISO-8601 UTC of the last successful capture")
    tag: str | None = Field(None, description="the tag filter applied, if any")


class DigestItem(BaseModel):
    """One line of the neutral digest — a captured headline + its citation. NO analysis."""

    title: str
    source: str
    url: str
    publishedTs: str
    tags: list[str] = Field(default_factory=list)


class NewsDigest(BaseModel):
    """GET /news/digest payload — a NEUTRAL, source-cited roll-up of captured news.

    `headline` is a factual count sentence ("N captured headlines …"), never an opinion.
    `items` each carry a source url (grounding). `note` carries the honest empty-state
    message when nothing has been captured. The digest NEVER predicts or editorialises.
    """

    headline: str
    items: list[DigestItem] = Field(default_factory=list)
    count: int = 0
    asOf: str | None = None
    note: str | None = Field(None, description="honest empty-state / fail-open note")
