"""
Phase 1b -- turn raw HTML into compact text an 8B model can actually read.

Two jobs:
  1. Strip everything that is not content (scripts, chrome, cookie banners).
     Raw pages here run to 800 KB; the useful text is a few percent of that.
  2. Split what remains into chunks that fit the context window, because one
     page in this corpus cleans down to ~39,000 tokens and a truncated prompt
     produces a short answer with no error -- the worst kind of failure.

Run standalone to inspect one file:
    .venv/bin/python cleaner.py results/html_cache/<hash>.html
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment

import config


@dataclass
class CleanedPage:
    """Cleaned text plus the metadata the benchmark needs to log."""
    text: str
    chunks: list[str] = field(default_factory=list)
    est_tokens: int = 0
    word_count: int = 0
    was_chunked: bool = False

    @property
    def n_chunks(self) -> int:
        return len(self.chunks)


def estimate_tokens(text: str) -> int:
    """Rough token count. German compounds split badly, so ~3 chars/token."""
    return len(text) // config.CHARS_PER_TOKEN_ESTIMATE


def annotate_links(soup, page_url: str) -> int:
    """
    Write each outbound link's URL into the text, next to its anchor text.

    Text extraction discards `href` attributes, so before this existed the
    model received zero URLs and could not have returned a company website
    however it was prompted. Member directories put the company's own site on
    the company's name, so the link has to survive into the text the model
    reads:

        Robert Bosch GmbH   ->   Robert Bosch GmbH <https://www.bosch.de>

    Only links leaving the association's own domain are annotated. Internal
    links are navigation and profile pages; annotating those would add
    thousands of useless tokens and invite the model to return the
    association's own URLs as company websites.

    Returns the number of links annotated.
    """
    def labels(netloc: str) -> set[str]:
        # Meaningful name parts of a hostname, ignoring generic ones. NMWP
        # serves its directory from verein.nmwp.nrw and its member profiles
        # from portal.nmwp.de -- different domains, same organisation. Comparing
        # only the first label would treat those profile pages as company
        # websites.
        parts = netloc.replace("www.", "").lower().split(".")
        return {p for p in parts
                if len(p) >= 4 and p not in {"com", "net", "org", "info",
                                             "portal", "verein", "www"}}

    own = labels(urlparse(page_url).netloc)
    count = 0

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http"):
            continue
        if own & labels(urlparse(href).netloc):
            continue                      # same organisation: navigation

        text = " ".join(a.get_text(separator=" ").split())
        if not text:
            # Logo-only entries: the company name lives in the image's alt
            # text, which get_text() would drop entirely. Several directories
            # are built this way, so recovering it also recovers the name.
            img = a.find("img")
            if img:
                text = (img.get("alt") or img.get("title") or "").strip()
                if text:
                    a.append(f" {text}")
        if not text or len(text) > 90:
            continue

        a.append(f" <{href}>")
        count += 1

    return count


def clean_html(html: str, page_url: str = "") -> str:
    """Reduce an HTML document to its readable text content."""
    # lxml is far faster than html.parser on the 800 KB pages in this corpus,
    # but it chokes on a few malformed documents -- fall back rather than die.
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # Annotation must happen before ANY tag is removed, for two reasons.
    # get_text() discards href attributes, which is the obvious one. The
    # subtle one is <img>: many association directories list members as logo
    # links, <a href="company.de"><img alt="Company GmbH"></a>, where the
    # company name exists only in the alt attribute. Stripping images first
    # left annotate_links() with an empty anchor and no img to recover the
    # name from, so those entries were dropped silently -- 27 of 29 member
    # links on NMWP.NRW, and every link on four other ground-truth pages.
    #
    # Annotating first is safe: anchors inside nav/header/footer are removed
    # with their subtree a few lines below, and the annotation goes with them.
    if page_url and config.PRESERVE_LINKS:
        annotate_links(soup, page_url)

    for tag in soup(config.STRIP_TAGS):
        tag.decompose()

    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    for selector in config.STRIP_SELECTORS:
        try:
            for el in soup.select(selector):
                el.decompose()
        except Exception:
            # A malformed selector should never abort the whole clean.
            continue

    # Table rows and list items carry the member names on most of these sites,
    # so mark those boundaries before flattening -- otherwise adjacent company
    # names run together into one unreadable string.
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for el in soup.find_all(["tr", "li", "p", "div", "h1", "h2", "h3", "h4"]):
        el.append("\n")

    text = soup.get_text(separator=" ")

    # Collapse whitespace but keep line structure, then drop repeated blanks.
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]

    # Drop 1-2 character lines: leftover bullets, arrows, pagination digits.
    lines = [ln for ln in lines if len(ln) > 2]

    return "\n".join(lines)


def chunk_text(text: str, budget: int | None = None) -> list[str]:
    """
    Split on line boundaries so a company name is never cut in half.

    A small overlap carries context across the seam, which matters when a
    heading like "Ordentliche Mitglieder" sits just above the list it labels.
    """
    budget = budget or config.CHUNK_TOKEN_BUDGET
    max_chars = budget * config.CHARS_PER_TOKEN_ESTIMATE
    overlap_chars = config.CHUNK_OVERLAP_TOKENS * config.CHARS_PER_TOKEN_ESTIMATE

    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    size = 0

    for line in text.split("\n"):
        line_len = len(line) + 1
        if size + line_len > max_chars and current:
            chunks.append("\n".join(current))
            # Re-seed the next chunk with the tail of this one.
            tail = []
            taken = 0
            for prev in reversed(current):
                if taken + len(prev) > overlap_chars:
                    break
                tail.insert(0, prev)
                taken += len(prev)
            current = tail
            size = taken
        current.append(line)
        size += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks


def process(html: str, page_url: str = "") -> CleanedPage:
    """Full clean + chunk pipeline for one page."""
    text = clean_html(html, page_url)
    chunks = chunk_text(text)
    return CleanedPage(
        text=text,
        chunks=chunks,
        est_tokens=estimate_tokens(text),
        word_count=len(text.split()),
        was_chunked=len(chunks) > 1,
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    path = Path(sys.argv[1])
    page = process(path.read_text(encoding="utf-8", errors="ignore"))
    print(f"words={page.word_count}  est_tokens={page.est_tokens}  "
          f"chunks={page.n_chunks}")
    print("-" * 60)
    print(page.text[:2000])
