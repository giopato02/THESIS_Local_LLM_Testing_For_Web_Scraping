"""
Describe every ground-truth page: layout, size, funding programme.

Accuracy averaged over 30 pages hides the thing the sample was built to show.
The pages were chosen for variety (THESIS_NOTES 3.14), so results have to be
reported per layout as well as pooled, and that needs one table saying what
each page is. Written once here, used by make_report.py and by the thesis.

Nothing here uses a model: the layout is decided by counting which kind of
link dominates the page, exactly as during the selection.

Run:  .venv/bin/python page_profile.py
      -> data/page_profile.csv
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from urllib.parse import urlparse

from bs4 import BeautifulSoup

import cleaner
import config
import fetcher
import link_coverage as L
import make_ground_truth as G

OUT = config.DATA_DIR / "page_profile.csv"
LEGAL = re.compile(r"\b(GmbH|mbH|AG|KG|SE|e\.?\s?V\.?|eG|KGaA)\b")
SOCIAL = re.compile(r"linkedin|xing|facebook|twitter|instagram|youtube|x\.com", re.I)

# Where the 73-URL list came from, when a page is not in the Finalv1 sheet.
SOURCE_LABELS = {
    "Private_funded_innovation_clubs_FINAL_200": "Private funded",
    "Deutsche_technische_Verbaende_erweitert": "Technical association",
}
FINALV1 = "NEOHUB_final_merged_QA_reviewed (1)(Finalv1).csv"


def funding_lookup() -> dict:
    """{host -> ZIM network | Private funded} from the Finalv1 sheet."""
    path = config.THESIS_WORK / FINALV1
    out: dict = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            dataset = (r.get("Source dataset") or "").strip()
            if not dataset:
                continue
            for column in ("Companies / members URL", "Verified / corrected network URL",
                           "Network homepage / exact hosted page"):
                url = (r.get(column) or "").strip()
                if url.startswith("http"):
                    out.setdefault(L.host_of(url), dataset)
    return out


def layout_of(html: str, url: str) -> tuple[str, Counter]:
    """
    Which kind of entry dominates: how a reader would describe the page.

    The six kinds are the ones found across the 291 networks: the name links
    to the company's own site, the name links to a profile page, the name sits
    beside a separate "Web" link, the name exists only inside a logo image, a
    table, or plain text with no links at all.
    """
    soup = BeautifulSoup(html, "lxml")
    own = urlparse(url).netloc
    c: Counter = Counter()
    for a in soup.find_all("a", href=True):
        href = L.resolve(a["href"], url)
        if not href.startswith("http") or SOCIAL.search(href):
            continue
        text = " ".join(a.get_text(" ").split())
        img = a.find("img")
        alt = (img.get("alt") or img.get("title") or "").strip() if img else ""
        if not L.same_org(own, urlparse(href).netloc):
            if not text and alt:
                c["logo grid"] += 1
            elif text.casefold() in L.GENERIC_LABELS:
                c["name + separate Web link"] += 1
            elif LEGAL.search(text or alt) or len(text) >= 6:
                c["name links to company site"] += 1
        elif LEGAL.search(text or alt):
            c["name links to profile page"] += 1
    best = max(c, key=c.get) if c else ""
    if best and c[best] >= 5:
        return best, c
    return ("table" if len(soup.find_all("tr")) >= 10 else "plain text, no links"), c


def main() -> None:
    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}
    funding = funding_lookup()
    routes: dict = {}
    cov = config.RESULTS_DIR / "link_coverage.csv"
    if cov.exists():
        with open(cov, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                routes.setdefault(r["url_id"], Counter())[r["route"]] += 1

    rows = []
    for uid in G.SAMPLE_IDS:
        key = config.GROUND_TRUTH_DIR / f"{uid}.json"
        if not key.exists():
            continue
        row = urls[uid]
        html = fetcher.cache_path(row["url"]).read_text(encoding="utf-8", errors="ignore")
        page = cleaner.process(html, row["url"])
        companies = json.loads(key.read_text(encoding="utf-8"))["companies"]
        layout, counts = layout_of(html, row["url"])
        n = len(companies)
        r = routes.get(uid, Counter())
        rows.append({
            "id": uid,
            "network": row["org_name"],
            "url": row["url"],
            "funding": (funding.get(L.host_of(row["url"]))
                        or SOURCE_LABELS.get(row.get("source_file", ""), "")
                        or "unknown"),
            "layout": layout,
            "companies": n,
            "size_band": "large (100+)" if n >= 100 else "medium (30-99)" if n >= 30 else "small (<30)",
            "words": page.word_count,
            "chunks": page.n_chunks,
            "website_on_page": r.get("website", 0),
            "profile_only": r.get("profile", 0),
            "no_link": r.get("none", 0),
            "round": "1" if uid in G.SAMPLE_IDS[:10] else "2",
        })
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"  {len(rows)} pages -> {OUT}")
    for field in ("layout", "funding", "size_band"):
        print(f"\n  by {field}:")
        for value, count in Counter(r[field] for r in rows).most_common():
            companies = sum(r["companies"] for r in rows if r[field] == value)
            print(f"    {value:<30}{count:>3} pages{companies:>7} companies")
    print(f"\n  long pages (2+ chunks): {sum(1 for r in rows if r['chunks'] > 1)}")


if __name__ == "__main__":
    main()
