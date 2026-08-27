"""
Headless-browser fetching for paginated and JavaScript-rendered member lists.

WHY THIS EXISTS
---------------
`fetcher.py` makes one HTTP request and takes whatever HTML comes back. That
is correct for a static page, but nearly half of this corpus is not static:

  * 24 of 53 usable pages carry pagination or lazy-load markers.
  * Medical Valley advertises "posts_per_page": 20 and serves exactly 20
    members per request; the remaining hundreds arrive only via AJAX. Every
    URL pagination pattern (?paged=2, /page/2/, ?page=2) returns page one,
    and the WordPress REST route for the custom post type is closed.
  * 8 further pages return HTTP 200 with no member list in the HTML at all.

The dangerous part is that this failure is SILENT. A truncated page looks
perfectly healthy: 200 OK, plenty of text, plausible company names. Nothing
in the static pipeline can tell "this association has 20 members" from "this
page shows the first 20 of 400".

So this module loads the page in a real browser, then repeatedly:
    scroll to the bottom -> click any "load more" control -> wait
until the number of member-ish elements stops growing. The final rendered DOM
is what gets cached, so the rest of the pipeline is unchanged.

It deliberately does NOT reverse-engineer per-site AJAX endpoints. The thesis
requires a generic pipeline; a per-site endpoint map would not scale to 817
networks and would undermine that claim. Scrolling and clicking is what a
human does, and it works the same way everywhere.

USAGE
    .venv/bin/python browser_fetcher.py --ids 040 012 050 043
    .venv/bin/python browser_fetcher.py --auto      # every page with markers
    .venv/bin/python browser_fetcher.py --compare 040
"""

from __future__ import annotations

import argparse
import csv
import re
import time

import cleaner
import config
import fetcher

# Markers that mean "this page probably has more content than it first shows".
PAGINATION_MARKERS = re.compile(
    r"posts_per_page|load_more|loadmore|infinite[_-]?scroll|"
    r"jet-filters-pagination|data-page=|next[_-]?page|\bpagination\b",
    re.I,
)

# Text on buttons that reveal more entries, German and English.
LOAD_MORE_TEXT = [
    "mehr laden", "mehr anzeigen", "weitere laden", "weitere anzeigen",
    "alle anzeigen", "alle laden", "mehr", "weiter",
    "load more", "show more", "view all", "see all", "more",
]

# Elements that plausibly represent one member entry. Used only to decide
# whether the page grew, never to extract names -- extraction stays with the LLM.
COUNT_SELECTOR = (
    "article, li, tr, "
    ".member.mitglied.partner.card.entry, "
    "[class*='member'], [class*='mitglied'], [class*='partner'], "
    "[class*='card'], [class*='item']"
)

MAX_ROUNDS = 40           # hard stop; some directories are very long
SETTLE_MS = 1400          # how long to wait for new content after an action


def _count_entries(page) -> int:
    try:
        return page.locator(COUNT_SELECTOR).count()
    except Exception:
        return 0


def _click_load_more(page) -> bool:
    """Click a 'load more' style control if one is visible. True if clicked."""
    for label in LOAD_MORE_TEXT:
        try:
            # Case-insensitive exact-ish text match on clickable elements.
            btn = page.locator(
                f"button:has-text('{label}'), a:has-text('{label}'), "
                f"[role=button]:has-text('{label}')"
            ).first
            if btn.count() and btn.is_visible(timeout=800):
                btn.click(timeout=2500)
                return True
        except Exception:
            continue
    return False


def _walk_numbered_pagination(page, verbose: bool = True) -> list[str]:
    """
    Click through a numbered pagination widget, collecting each page's HTML.

    Medical Valley is the reference case: its directory is 14 pages of 20
    members driven by JetSmartFilters. The URL never changes, no ?page=N
    variant works, and the WordPress REST route is closed -- clicking is the
    only way through. Returns the HTML of every page visited after the first.
    """
    selectors = [
        ".jet-filters-pagination__link",
        ".page-numbers a", ".pagination a", ".pager a",
        "[class*='pagination'] a", "nav[role='navigation'] a",
    ]

    link_sel = None
    for sel in selectors:
        try:
            if page.locator(sel).count() > 1:
                link_sel = sel
                break
        except Exception:
            continue
    if not link_sel:
        return []

    # Collect the page labels offered. Two conventions appear in this corpus:
    #   plain page numbers   2, 3, 4 ... 14
    #   record ranges        0-50, 51-100, 101-150
    # Both are just "click this to see more", so both are accepted.
    RANGE = re.compile(r"^\d+\s*[--, ]\s*\d+$")
    labels: list[str] = []
    loc = page.locator(link_sel)
    for i in range(min(loc.count(), 80)):
        try:
            txt = loc.nth(i).inner_text(timeout=500).strip()
        except Exception:
            continue
        if not txt or txt in labels:
            continue
        if txt.isdigit() and txt != "1":
            labels.append(txt)
        elif RANGE.match(txt):
            # Skip the range that starts at the beginning -- already shown.
            if not re.match(r"^(0|1)\s*[--, ]", txt):
                labels.append(txt)

    if not labels:
        return []

    def _sort_key(label: str) -> int:
        m = re.match(r"^(\d+)", label)
        return int(m.group(1)) if m else 0

    labels.sort(key=_sort_key)
    if verbose:
        print(f"      numbered pagination: pages {labels[0]}-{labels[-1]}")

    parts: list[str] = []
    for label in labels[:MAX_ROUNDS]:
        try:
            link = page.locator(
                link_sel, has_text=re.compile(rf"^\s*{re.escape(label)}\s*$")).first
            if not link.count():
                continue
            link.scroll_into_view_if_needed(timeout=3000)
            link.click(timeout=5000)
            page.wait_for_timeout(SETTLE_MS + 600)
            parts.append(page.content())
            if verbose:
                print(f"      page {label} captured", end="\r")
        except Exception:
            continue

    return parts


def _dismiss_cookie_banner(page) -> None:
    """Consent overlays intercept clicks. Decline rather than accept."""
    for label in ["Nur notwendige", "Nur essenzielle", "Ablehnen", "Reject",
                  "Decline", "Alle ablehnen", "Essenzielle", "Necessary only",
                  "Akzeptieren", "Accept all", "Alle akzeptieren", "OK"]:
        try:
            btn = page.locator(
                f"button:has-text('{label}'), a:has-text('{label}')").first
            if btn.count() and btn.is_visible(timeout=600):
                btn.click(timeout=2000)
                page.wait_for_timeout(500)
                return
        except Exception:
            continue


def render_fully(url: str, verbose: bool = True) -> tuple[str, dict]:
    """
    Load `url` in a headless browser and exhaust its pagination.

    Returns (final HTML, stats).
    """
    from playwright.sync_api import sync_playwright

    stats = {"rounds": 0, "clicks": 0, "entries_start": 0, "entries_end": 0}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=config.USER_AGENT,
            locale="de-DE",
            viewport={"width": 1400, "height": 1000},
        )
        page = ctx.new_page()

        try:
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
        except Exception as exc:
            browser.close()
            raise RuntimeError(f"navigation failed: {exc}") from exc

        page.wait_for_timeout(1500)
        _dismiss_cookie_banner(page)

        stats["entries_start"] = _count_entries(page)
        previous = stats["entries_start"]
        stagnant = 0

        for round_no in range(MAX_ROUNDS):
            stats["rounds"] = round_no + 1

            page.mouse.wheel(0, 20000)
            page.wait_for_timeout(SETTLE_MS)

            if _click_load_more(page):
                stats["clicks"] += 1
                page.wait_for_timeout(SETTLE_MS)

            current = _count_entries(page)
            if verbose:
                print(f"      round {round_no+1:>2}: {current} entries", end="\r")

            if current <= previous:
                stagnant += 1
                # Two quiet rounds in a row means nothing more is coming.
                if stagnant >= 2:
                    break
            else:
                stagnant = 0
            previous = current

        # Scrolling and "load more" are exhausted; now walk any numbered
        # pagination and concatenate every page into one document.
        first_html = page.content()
        extra = _walk_numbered_pagination(page, verbose)
        stats["extra_pages"] = len(extra)
        stats["entries_end"] = previous

        if extra:
            parts = [f'<div data-pagination-part="1">{first_html}</div>']
            parts += [f'<div data-pagination-part="{i+2}">{h}</div>'
                      for i, h in enumerate(extra)]
            html = "<html><body>\n" + "\n".join(parts) + "\n</body></html>"
        else:
            html = first_html

        browser.close()

    return html, stats


def needs_browser(html: str) -> bool:
    """Cheap check: does this cached page look like it hides more content?"""
    return bool(PAGINATION_MARKERS.search(html))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="+", help="specific url ids to re-fetch")
    ap.add_argument("--auto", action="store_true",
                    help="re-fetch every cached page showing pagination markers")
    ap.add_argument("--compare", help="render one id and report the difference")
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting ground-truth pages (see below)")
    args = ap.parse_args()

    # The ten hand-labelled pages are frozen. Their answer keys describe the
    # exact cached snapshot, so re-fetching one silently invalidates hours of
    # manual work -- a page-1 unit would become a 14-page document while the
    # answer key still listed 20 members, and recall would collapse.
    import make_ground_truth
    protected = set(make_ground_truth.SAMPLE_IDS)

    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}

    if args.compare:
        row = urls[args.compare]
        old = fetcher.cache_path(row["url"]).read_text(
            encoding="utf-8", errors="ignore")
        old_page = cleaner.process(old)
        print(f"  {row['org_name']}\n  {row['url']}\n")
        print(f"  static  : {old_page.word_count:>6} words, "
              f"{old_page.est_tokens:>6} tokens")
        html, stats = render_fully(row["url"])
        new_page = cleaner.process(html)
        print(f"  rendered: {new_page.word_count:>6} words, "
              f"{new_page.est_tokens:>6} tokens")
        print(f"\n  entries {stats['entries_start']} -> {stats['entries_end']} "
              f"in {stats['rounds']} rounds ({stats['clicks']} clicks)")
        gain = new_page.word_count - old_page.word_count
        print(f"  gain: {gain:+} words "
              f"({gain/max(old_page.word_count,1)*100:+.0f}%)")
        return

    if args.auto:
        targets = []
        for uid, row in urls.items():
            path = fetcher.cache_path(row["url"])
            if path.exists() and needs_browser(
                    path.read_text(encoding="utf-8", errors="ignore")):
                targets.append(uid)
    else:
        targets = args.ids or []

    if not args.force:
        skipped = [t for t in targets if t in protected]
        targets = [t for t in targets if t not in protected]
        if skipped:
            print(f"  skipping {len(skipped)} ground-truth page(s): "
                  f"{', '.join(skipped)}")
            print("  (their answer keys describe the current snapshot; "
                  "use --force to override)\n")

    if not targets:
        raise SystemExit("nothing to do; pass --ids or --auto")

    print(f"  re-fetching {len(targets)} page(s) with a headless browser\n")
    for i, uid in enumerate(targets, start=1):
        row = urls[uid]
        path = fetcher.cache_path(row["url"])
        before = cleaner.process(
            path.read_text(encoding="utf-8", errors="ignore")).word_count \
            if path.exists() else 0

        print(f"  [{i}/{len(targets)}] {uid} {row['org_name'][:40]}")
        try:
            html, stats = render_fully(row["url"])
        except Exception as exc:
            print(f"      FAILED: {str(exc)[:90]}")
            continue

        after = cleaner.process(html).word_count
        if after < before * 0.6:
            # Rendering produced markedly less than the static fetch -- a
            # consent wall or a bot check. Keep the better document.
            print(f"      rendered smaller ({before} -> {after} words); "
                  f"keeping static version")
            continue

        path.write_text(html, encoding="utf-8")
        print(f"      {before} -> {after} words "
              f"({stats['entries_end']} entries, {stats['rounds']} rounds)")
        time.sleep(1.0)

    print("\n  done. Re-run fetcher.py to refresh the manifest:")
    print("      .venv/bin/python fetcher.py")


if __name__ == "__main__":
    main()
