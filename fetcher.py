"""
Phase 1a -- fetch the 73 pages once and cache them to disk.

Why fetching is a separate phase from extraction:

  * Both models must see byte-identical input. If each benchmark run re-fetched,
    a site could change between runs and the comparison would be meaningless.
  * Network time must never leak into Latency_Seconds. We are measuring model
    inference, not someone's web server.
  * Re-running the benchmark 800+ times must not hammer 73 real organisations.

Etiquette: honest User-Agent naming the research project, a delay between
requests, exponential backoff on failure, and robots.txt parsed and recorded
per URL (logged for the thesis methodology section, not hard-enforced).

Run:  .venv/bin/python fetcher.py            # fetch all, skip cached
      .venv/bin/python fetcher.py --refetch  # ignore cache
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import time
import urllib.robotparser
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

import requests

import cleaner
import config


@dataclass
class FetchResult:
    """One row of fetch_manifest.csv."""
    id: str
    org_name: str
    url: str
    url_type: str
    status: str            # ok | http_error | timeout | connection_error | thin_content
    http_code: int | None
    raw_bytes: int
    word_count: int
    est_tokens: int
    would_chunk: bool
    robots_allowed: str    # allowed | disallowed | unknown
    cache_file: str
    error: str


class AdaptiveDelay:
    """
    Politeness delay that tracks how hard the server is working.

    Modelled on Scrapy's AUTOTHROTTLE, as configured in Neovation's scraperng.
    A fixed pause is either wasteful on a fast host or rude to a slow one; here
    the delay follows measured response latency, bounded at both ends. A server
    that starts struggling gets more room automatically.
    """

    def __init__(self) -> None:
        self.delay = config.REQUEST_DELAY

    def observe(self, latency: float) -> None:
        if not config.AUTOTHROTTLE_ENABLED:
            return
        target = latency * config.AUTOTHROTTLE_TARGET_LATENCY_RATIO
        # Smooth rather than jump, so one slow response does not stall the run.
        self.delay = (self.delay + target) / 2
        self.delay = max(config.AUTOTHROTTLE_MIN_DELAY,
                         min(config.AUTOTHROTTLE_MAX_DELAY, self.delay))

    def penalise(self) -> None:
        """Back off hard after a failure -- the host may be rate-limiting."""
        self.delay = min(config.AUTOTHROTTLE_MAX_DELAY, self.delay * 2)

    def wait(self) -> None:
        time.sleep(self.delay)


def cache_path(url: str):
    """Stable filename per URL so re-runs reuse the same cached document."""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return config.HTML_CACHE_DIR / f"{digest}.html"


def check_robots(url: str, session: requests.Session) -> str:
    """Report whether robots.txt permits this path. Recorded, not enforced."""
    try:
        parts = urlparse(url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        resp = session.get(robots_url, timeout=10)
        if resp.status_code != 200:
            return "unknown"
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(resp.text.splitlines())
        return "allowed" if parser.can_fetch(config.USER_AGENT, url) else "disallowed"
    except Exception:
        return "unknown"


def fetch_one(row: dict, session: requests.Session, refetch: bool,
              throttle: "AdaptiveDelay | None" = None) -> FetchResult:
    """Fetch a single URL with retries, cache the HTML, and measure the result."""
    url = row["url"]
    path = cache_path(url)

    base = dict(
        id=row["id"], org_name=row["org_name"], url=url, url_type=row["url_type"],
        http_code=None, raw_bytes=0, word_count=0, est_tokens=0,
        would_chunk=False, robots_allowed="unknown",
        cache_file=path.name, error="",
    )

    html: str | None = None

    if path.exists() and not refetch:
        html = path.read_text(encoding="utf-8", errors="ignore")
        base["http_code"] = 200
        base["error"] = "(from cache)"
    else:
        base["robots_allowed"] = check_robots(url, session)

        last_error = ""
        for attempt in range(config.MAX_RETRIES):
            try:
                _t0 = time.perf_counter()
                resp = session.get(url, timeout=config.REQUEST_TIMEOUT)
                if throttle:
                    throttle.observe(time.perf_counter() - _t0)
                base["http_code"] = resp.status_code
                if resp.status_code == 200:
                    # Let requests infer encoding; German pages are a mix of
                    # UTF-8 and Latin-1 and mojibake would corrupt every umlaut.
                    resp.encoding = resp.apparent_encoding or resp.encoding
                    html = resp.text
                    path.write_text(html, encoding="utf-8")
                    break
                last_error = f"HTTP {resp.status_code}"
                # 4xx is a decision by the server; retrying will not change it.
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    break
            except requests.Timeout:
                last_error = "timeout"
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"[:160]

            if attempt < config.MAX_RETRIES - 1:
                time.sleep(config.RETRY_BACKOFF ** (attempt + 1))

        if html is None:
            status = "timeout" if "timeout" in last_error else (
                "http_error" if last_error.startswith("HTTP") else "connection_error")
            return FetchResult(status=status, **{**base, "error": last_error})

    page = cleaner.process(html)
    base.update(
        raw_bytes=len(html),
        word_count=page.word_count,
        est_tokens=page.est_tokens,
        would_chunk=page.was_chunked,
    )

    # A page that returns 200 but cleans down to almost nothing is a
    # JavaScript-rendered shell: the member list exists, but not in the HTML.
    status = "thin_content" if page.word_count < config.THIN_CONTENT_WORD_THRESHOLD else "ok"
    return FetchResult(status=status, **base)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true", help="ignore the cache")
    ap.add_argument("--limit", type=int, default=None, help="stop after N URLs")
    args = ap.parse_args()

    with open(config.URLS_CSV, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if args.limit:
        rows = rows[: args.limit]

    session = requests.Session()
    session.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    })

    throttle = AdaptiveDelay()
    results: list[FetchResult] = []
    for i, row in enumerate(rows, start=1):
        was_cached = cache_path(row["url"]).exists() and not args.refetch
        res = fetch_one(row, session, args.refetch, throttle)
        if res.status not in ("ok", "thin_content"):
            throttle.penalise()
        results.append(res)

        flag = {"ok": "  ", "thin_content": "~ "}.get(res.status, "! ")
        print(f"{flag}[{i:>2}/{len(rows)}] {res.status:<16} "
              f"{res.word_count:>6}w {res.est_tokens:>7}tok  "
              f"{res.org_name[:38]}")

        # Only pause when we actually touched the network.
        if not was_cached and i < len(rows):
            throttle.wait()

    with open(config.FETCH_MANIFEST_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for res in results:
            writer.writerow(asdict(res))

    print("\n" + "=" * 58)
    counts: dict[str, int] = {}
    for res in results:
        counts[res.status] = counts.get(res.status, 0) + 1
    for status, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {status:<18} {n:>3}")
    usable = [r for r in results if r.status == "ok"]
    if usable:
        toks = sorted(r.est_tokens for r in usable)
        print(f"\n  usable pages:      {len(usable)}")
        print(f"  tokens min/med/max {toks[0]} / {toks[len(toks)//2]} / {toks[-1]}")
        print(f"  need chunking:     {sum(r.would_chunk for r in usable)}")
    print(f"\n  manifest -> {config.FETCH_MANIFEST_CSV}")


if __name__ == "__main__":
    main()
