"""
Score the company website field properly: is it the RIGHT address, not merely
a real one.

benchmark.py checks whether a returned web address appears anywhere in the
page text. That catches invention, which is the worst failure, but it passes
a different one: a genuine address from the page attached to the wrong
company. Measured on NMWP.NRW, the model returns 27 addresses for a page
carrying 12 member websites, so roughly 15 are real links bound to companies
they do not belong to, and every one of them counts as "verified".

link_coverage.py already knows which address sits with which company, worked
out positionally from the cleaned text. Comparing against that turns one weak
measure into four:

    correct     the address that belongs to this company
    wrong       a real address from the page, bound to the wrong company
    invented    not on the page at all
    unscored    the company has no website on the page, so nothing to compare

Precision and recall follow, on the website field alone:

    precision = correct / (correct + wrong + invented)
    recall    = correct / (companies whose website IS on the page)

Recall is measured against the ceiling from link_coverage.py, not against the
company count, because no model can return a website that was never printed.

This reads saved extractions rather than calling a model, so it re-scores
finished runs without repeating them.

Run:  .venv/bin/python score_websites.py
      .venv/bin/python score_websites.py --by page
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import json
from collections import defaultdict

import config

EXTRACTIONS = config.RESULTS_DIR / "extractions"


def use_run(results_csv: str) -> None:
    """Score one grid: its extraction files sit next to its results CSV."""
    global EXTRACTIONS
    folder = pathlib.Path(results_csv).resolve().parent / "extractions"
    if folder.is_dir():
        EXTRACTIONS = folder
COVERAGE_CSV = config.RESULTS_DIR / "link_coverage.csv"
OUT_CSV = config.RESULTS_DIR / "website_scores.csv"


def match_key(name: str) -> str:
    import benchmark
    return benchmark.match_key(name)


def host_of(url: str) -> str:
    """Bare hostname, so scheme and trailing slash differences do not count."""
    u = url.strip().lower()
    for prefix in ("https://", "http://", "//"):
        if u.startswith(prefix):
            u = u[len(prefix):]
            break
    u = u.split("?")[0].split("#")[0].split("/")[0]
    return u[4:] if u.startswith("www.") else u


def classify(host: str, want: str, on_page: set) -> str:
    """
    One returned address, sorted into the only four things it can be.

        correct   the pairing has an address for this company and it matches
        wrong     the pairing has a DIFFERENT address for this company
        unscored  the pairing has no address for this company, so there is
                  nothing to compare against
        invented  the address is nowhere on the page

    `unscored` is the one that was missing, and its absence produced a
    confidently wrong result on 2026-09-30. Without it, every company that
    `link_coverage.py` had not paired was counted as a misattribution the
    moment the model returned anything: 4,632 of them, reported as "21.9%
    wrong company" and precision 0.779.

    Two checks showed that reading was false. Across the winning
    configuration there were **zero** disagreements on companies the pairing
    DOES cover, and a sample of the unpaired ones showed the model right and
    the pairing incomplete:

        Technologie Zentrum Dortmund GmbH  ->  tzdo.de
        Deutsche Edelstahlwerke Services   ->  dew-stahl.com

    The pairing covers 1,134 of 2,638 companies, so it has no opinion about
    most of them. Counting its silence as the model's error measures the
    yardstick, not the model. Reporting `unscored` separately states how much
    of the output this method cannot judge, which is the honest answer.
    """
    if want and host == want:
        return "correct"
    if want:
        return "wrong"
    if host in on_page:
        return "unscored"
    return "invented"


def load_expected() -> tuple[dict[str, dict[str, str]], dict[str, set[str]]]:
    """
    Returns (expected, on_page) where

        expected[url_id][company_key] = the host that belongs to that company
        on_page[url_id]               = every host printed anywhere on the page

    The two come from different sources on purpose.

    `expected` comes from link_coverage.py, which pairs a company with the
    address printed beside it. Only companies in the ground truth appear.

    `on_page` must come from the page itself, NOT from link_coverage. A
    directory carries links the ground truth says nothing about: companies
    that were not annotated, partners, sponsors. Building this set from the
    matched subset would count every one of those as invented, which
    overstates hallucination badly. Measured on a first attempt: 48 addresses
    were reported invented that were in fact printed on the page.

    Invention means the address is nowhere on the page. That claim is serious
    enough that the check has to be made against the page.
    """
    if not COVERAGE_CSV.exists():
        raise SystemExit(f"run link_coverage.py first: {COVERAGE_CSV} is missing")

    expected: dict[str, dict[str, str]] = defaultdict(dict)
    with open(COVERAGE_CSV, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r["route"] == "website" and r["target"]:
                expected[r["url_id"]][match_key(r["company"])] = host_of(r["target"])

    import re

    import cleaner
    import fetcher
    marker = re.compile(r"<(https?://[^>\s]+)>")

    on_page: dict[str, set[str]] = defaultdict(set)
    with open(config.URLS_CSV, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            path = fetcher.cache_path(row["url"])
            if not path.exists():
                continue
            text = cleaner.process(
                path.read_text(encoding="utf-8", errors="ignore"), row["url"]).text
            on_page[row["id"]] = {host_of(u) for u in marker.findall(text)}
    return expected, on_page


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=None,
                    help="results CSV of one run, e.g. results/runs/<name>/benchmark_results.csv")
    ap.add_argument("--by", default="config",
                    choices=["config", "page", "model"],
                    help="what to group the report by")
    args = ap.parse_args()
    if args.results:
        use_run(args.results)

    expected, on_page = load_expected()

    rows = []
    for path in sorted(EXTRACTIONS.glob("*.json")):
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        parts = blob.get("key", "").split("|")
        if len(parts) != 6:
            continue
        _, model, strategy, json_mode, url_id, rep = parts

        records = blob.get("records") or []
        if not any((r.get("url") or "").strip() for r in records):
            continue                      # a names-only run, nothing to score

        exp = expected.get(url_id, {})
        real = on_page.get(url_id, set())
        correct = wrong = invented = unscored = 0

        for rec in records:
            url = (rec.get("url") or "").strip()
            if not url:
                continue
            host = host_of(url)
            want = exp.get(match_key(rec.get("name", "")))
            verdict = classify(host, want, real)
            correct += verdict == "correct"
            wrong += verdict == "wrong"
            unscored += verdict == "unscored"
            invented += verdict == "invented"

        returned = correct + wrong + invented + unscored
        ceiling = len(exp)
        rows.append({
            "url_id": url_id, "model_name": model,
            "prompt_technique": strategy, "json_mode": json_mode,
            "repetition": rep,
            "returned": returned, "correct": correct,
            "wrong_company": wrong, "invented": invented,
            "unscored": unscored,
            "ceiling": ceiling,
            # Precision is over what CAN be judged. An unscored address is
            # neither right nor wrong here, so including it in the
            # denominator would report the pairing's coverage as the model's
            # error rate, which is the mistake this column exists to undo.
            "precision": (round(correct / (correct + wrong + invented), 4)
                          if (correct + wrong + invented) else ""),
            "recall": round(correct / ceiling, 4) if ceiling else "",
        })

    if not rows:
        raise SystemExit("no extraction files carry website data yet")

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    keyfn = {
        "config": lambda r: (r["model_name"], r["prompt_technique"], r["json_mode"]),
        "page":   lambda r: (r["url_id"],),
        "model":  lambda r: (r["model_name"],),
    }[args.by]

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[keyfn(r)].append(r)

    def totals(g):
        s = {k: sum(r[k] for r in g) for k in
             ("returned", "correct", "wrong_company", "invented",
              "unscored", "ceiling")}
        judged = s["correct"] + s["wrong_company"] + s["invented"]
        s["precision"] = s["correct"] / judged if judged else 0
        s["recall"] = s["correct"] / s["ceiling"] if s["ceiling"] else 0
        return s

    label = {"config": 46, "page": 10, "model": 20}[args.by]
    head = (f"\n{'group':<{label}}{'runs':>6}{'returned':>10}{'correct':>9}"
            f"{'wrong co':>10}{'invented':>10}{'unscored':>10}"
            f"{'prec':>7}{'recall':>8}")
    print(head)
    print("-" * (label + 70))
    for k in sorted(groups):
        s = totals(groups[k])
        print(f"{' '.join(k)[:label]:<{label}}{len(groups[k]):>6}"
              f"{s['returned']:>10}{s['correct']:>9}{s['wrong_company']:>10}"
              f"{s['invented']:>10}{s['unscored']:>10}"
              f"{s['precision']:>7.3f}{s['recall']:>8.3f}")

    s = totals(rows)
    print("-" * (label + 70))
    print(f"{'TOTAL':<{label}}{len(rows):>6}{s['returned']:>10}{s['correct']:>9}"
          f"{s['wrong_company']:>10}{s['invented']:>10}{s['unscored']:>10}"
          f"{s['precision']:>7.3f}{s['recall']:>8.3f}")
    print(f"\n  correct        {s['correct']:>6}  the right address for that company")
    print(f"  wrong company  {s['wrong_company']:>6}  the pairing has a DIFFERENT "
          f"address for this company")
    print(f"  invented       {s['invented']:>6}  not on the page at all")
    print(f"  unscored       {s['unscored']:>6}  the pairing has no address for this "
          f"company, so there is")
    print(f"  {'':>6}         nothing to compare. NOT counted as an error: a sample")
    print(f"  {'':>6}         showed these are mostly the model right and the")
    print(f"  {'':>6}         pairing incomplete (see THESIS_NOTES 3.19).")
    print(f"\n  precision is over what can be judged: "
          f"correct / (correct + wrong + invented)")
    print(f"  -> {OUT_CSV}")


if __name__ == "__main__":
    main()
