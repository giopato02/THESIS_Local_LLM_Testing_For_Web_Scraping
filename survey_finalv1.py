"""
Health-check every members URL in the Finalv1 sheet.

Yusif and Diego added a "Companies / members URL" column and marked 291 rows
VERIFIED. That verification means a human opened the link and saw a member
page, which is not the same question as "can the pipeline extract from it" --
a JavaScript-rendered directory looks correct in a browser and arrives here as
an empty page.

This measures the second question across all 291, and caches the HTML so the
fetch is not repeated for the production run.

Categories:
    directory     a member list is present in the HTML
    sparse        HTTP 200 but little text: JS-rendered, or a search form
    thin          HTTP 200 and almost nothing at all
    http_error    4xx / 5xx
    unreachable   DNS or connection failure

Run:  .venv/bin/python survey_finalv1.py
      .venv/bin/python survey_finalv1.py --limit 40
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import time

import requests

import cleaner
import config

SOURCE = config.THESIS_WORK / "NEOHUB_final_merged_QA_reviewed (1)(Finalv1).csv"
OUT = config.RESULTS_DIR / "finalv1_health.csv"
CACHE = config.RESULTS_DIR / "html_cache_finalv1"
CACHE.mkdir(parents=True, exist_ok=True)

MEMBERS = "Companies / members URL"
LEGAL = re.compile(r"\b(GmbH|mbH|AG|KG|SE|e\.?\s?V\.?|eG|KGaA)\b")

# A page carrying this many legal forms is a member list rather than prose.
DIRECTORY_MIN = 10
SPARSE_MAX_WORDS = 150


def classify(code, words: int, legal: int) -> str:
    if code == "ERR":
        return "unreachable"
    if code != 200:
        return "http_error"
    if legal >= DIRECTORY_MIN:
        return "directory"
    if words < SPARSE_MAX_WORDS:
        return "thin"
    return "sparse"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    with open(SOURCE, encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh, delimiter=";")
                if r[MEMBERS].strip().lower().startswith("http")]
    if args.limit:
        rows = rows[: args.limit]

    session = requests.Session()
    session.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    })

    out = []
    counts: dict[str, int] = {}
    for i, r in enumerate(rows, start=1):
        url = r[MEMBERS].strip()
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        path = CACHE / f"{digest}.html"

        code, words, legal = "ERR", 0, 0
        try:
            if path.exists():
                html, code = path.read_text(encoding="utf-8", errors="ignore"), 200
            else:
                resp = session.get(url, timeout=25)
                code = resp.status_code
                if code == 200:
                    resp.encoding = resp.apparent_encoding or resp.encoding
                    html = resp.text
                    path.write_text(html, encoding="utf-8")
                else:
                    html = ""
            if code == 200 and html:
                page = cleaner.process(html, url)
                words, legal = page.word_count, len(LEGAL.findall(page.text))
        except requests.RequestException:
            pass

        cat = classify(code, words, legal)
        counts[cat] = counts.get(cat, 0) + 1
        out.append({
            "network": r["Netzwerkname"].strip(),
            "members_url": url,
            "source_dataset": r["Source dataset"].strip(),
            "http_code": code,
            "words": words,
            "legal_forms": legal,
            "category": cat,
        })

        mark = {"directory": "  ", "sparse": "~ ", "thin": "~ "}.get(cat, "! ")
        print(f"{mark}[{i:>3}/{len(rows)}] {cat:<12}{words:>6}w {legal:>4}L  "
              f"{r['Netzwerkname'][:36]}")
        if not path.exists() or code != 200:
            time.sleep(config.REQUEST_DELAY)

    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    print("\n" + "=" * 56)
    for cat in ("directory", "sparse", "thin", "http_error", "unreachable"):
        n = counts.get(cat, 0)
        print(f"  {cat:<14}{n:>4}   {n/len(rows)*100:>5.1f}%")
    print(f"\n  cached HTML -> {CACHE}")
    print(f"  report      -> {OUT}")


if __name__ == "__main__":
    main()
