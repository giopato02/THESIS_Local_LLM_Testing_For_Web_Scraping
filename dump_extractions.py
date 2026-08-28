"""
Flatten every per-run extraction into one raw, inspectable file.

benchmark.py already writes what each run returned to
results/extractions/<run_id>.json, but one file per run is not something a
human can read, and benchmark_results.csv only carries the counts. This joins
the two so the actual names and URLs can be looked at directly.

Two outputs:

  extractions_long.csv    one row per extracted company per run. Every model x
                          strategy x JSON mode x page x repetition combination
                          that produced that name appears as its own row, so
                          nothing is aggregated away.

  extractions_review.xlsx  the same data plus an agreement sheet: for each
                          page, every distinct company name and how many of
                          the runs found it, against whether it is in the
                          ground truth. This is where systematic misses and
                          shared hallucinations become visible -- a name that
                          every configuration invents is a page-formatting
                          problem, one that a single configuration invents is
                          a model problem.

Run:  .venv/bin/python dump_extractions.py
      .venv/bin/python dump_extractions.py --results RESULTS-Final.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import config

EXTRACTIONS = config.RESULTS_DIR / "extractions"
LONG_CSV = config.RESULTS_DIR / "extractions_long.csv"
REVIEW_XLSX = config.RESULTS_DIR / "extractions_review.xlsx"

# Grouped rather than alphabetical: which run produced the row, then what the
# model returned, then what this script worked out afterwards.
FIELDS = [
    # -- provenance: which run this row came from
    "url_id", "org_name", "model_name", "prompt_technique", "json_mode",
    "repetition",
    # -- what the model returned
    "name", "in_ground_truth",
    "company_url",
    "street", "postcode", "city", "phone", "email",
    # -- derived here, deterministically, not by any model
    "profile_url", "link_status",
]

# link_status values, and what each one means for the next pipeline stage.
#   company_site  the model returned a company website and it is on the page
#   unverified    a URL was returned that is NOT in the page text -- treat as
#                 fabricated until checked; these must not reach the database
#   profile_only  no company website on the page, but the directory links this
#                 member to its own profile page. This is the stage-2 queue.
#   none          neither. The company URL has to come from search or Impressum



def match_key(name: str) -> str:
    """Same normalisation the scorer uses, so 'found' here means found there."""
    import benchmark
    return benchmark.match_key(name)


def load_ground_truth() -> dict[str, set[str]]:
    truth = {}
    for path in sorted(config.GROUND_TRUTH_DIR.glob("*.json")):
        names = json.loads(path.read_text(encoding="utf-8"))["companies"]
        truth[path.stem] = {match_key(n) for n in names if match_key(n)}
    return truth


def load_page_text() -> dict[str, str]:
    """
    Cached page text per url_id, lowercased, for checking whether a returned
    URL was actually on the page or constructed by the model.
    """
    import cleaner
    import fetcher

    out: dict[str, str] = {}
    with open(config.URLS_CSV, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            path = fetcher.cache_path(row["url"])
            if path.exists():
                page = cleaner.process(
                    path.read_text(encoding="utf-8", errors="ignore"), row["url"])
                out[row["id"]] = page.text.lower()
    return out


def load_profile_links() -> dict[str, dict[str, str]]:
    """
    Per page, map a company name to its profile page on the association's own
    site: {url_id: {match_key(name): href}}.

    This is deliberately NOT done by a model. Deciding whether a link points
    at the association or at a company is a hostname comparison, which Python
    does exactly and for free, so spending tokens on it would be strictly
    worse. annotate_links() drops these links before the model ever sees the
    page (a profile page is not a company website), which is correct for
    extraction but means the profile URL has to be recovered here.

    The result is the work queue for stage 2: every member whose company
    website is not printed in the directory, but whose details can be reached
    with one more fetch.
    """
    import fetcher
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlparse

    out: dict[str, dict[str, str]] = {}
    with open(config.URLS_CSV, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    for row in rows:
        path = fetcher.cache_path(row["url"])
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"),
                             "lxml")
        own = urlparse(row["url"]).netloc.replace("www.", "").lower()
        found: dict[str, str] = {}

        # <base> redefines what relative links resolve against; ignoring it
        # produces doubled paths that 404 (see link_coverage.py).
        base_tag = soup.find("base", href=True)
        base = (urljoin(row["url"], base_tag["href"].strip())
                if base_tag else row["url"])

        for a in soup.find_all("a", href=True):
            href = urljoin(base, a["href"].strip())
            if not href.startswith("http"):
                continue
            if urlparse(href).netloc.replace("www.", "").lower() != own:
                continue                      # outbound: handled by the model

            text = " ".join(a.get_text(separator=" ").split())
            if not text:
                img = a.find("img")
                if img:
                    text = (img.get("alt") or img.get("title") or "").strip()
            key = match_key(text)
            # Navigation entries ("Startseite", "Kontakt") are short and
            # repeat on every page; a member name is longer and appears once.
            if len(key) < 5 or key in found:
                continue
            found[key] = href

        out[row["id"]] = found
    return out


def url_core(url: str) -> str:
    u = url.strip().lower()
    for prefix in ("https://", "http://", "//"):
        if u.startswith(prefix):
            u = u[len(prefix):]
            break
    u = u.split("?")[0].split("#")[0]
    if u.startswith("www."):
        u = u[4:]
    return u.rstrip("/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(config.BENCHMARK_CSV),
                    help="benchmark CSV, used for org_name and error status")
    ap.add_argument("--no-xlsx", action="store_true")
    args = ap.parse_args()

    if not EXTRACTIONS.exists():
        raise SystemExit(f"no extractions directory at {EXTRACTIONS}")

    # org_name and failure status live in the CSV, keyed by run_id.
    meta: dict[str, dict] = {}
    results_path = Path(args.results)
    if results_path.exists():
        with open(results_path, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                meta[row["run_id"]] = row

    truth = load_ground_truth()
    pages = load_page_text()
    profiles = load_profile_links()

    rows = []
    skipped = 0
    for path in sorted(EXTRACTIONS.glob("*.json")):
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            skipped += 1
            continue

        # stage|model|strategy|json_mode|url_id|repetition
        parts = blob.get("key", "").split("|")
        if len(parts) != 6:
            skipped += 1
            continue
        _, model, strategy, json_mode, url_id, rep = parts

        info = meta.get(path.stem, {})
        org = info.get("org_name", "")
        gold = truth.get(url_id, set())
        haystack = pages.get(url_id, "")
        page_profiles = profiles.get(url_id, {})

        # records is populated for every strategy; name-only strategies leave
        # the optional fields empty rather than omitting the record.
        records = blob.get("records") or [{"name": n} for n in blob.get("raw", [])]

        for rec in records:
            name = (rec.get("name") or "").strip()
            key = match_key(name)
            url = (rec.get("url") or "").strip()

            on_page = ""
            if url:
                host = url_core(url).split("/")[0]
                on_page = "yes" if (host and host in haystack) else "NO"

            profile = page_profiles.get(key, "")

            if url and on_page == "yes":
                status = "company_site"
            elif url:
                status = "unverified"
            elif profile:
                status = "profile_only"
            else:
                status = "none"

            rows.append({
                "url_id": url_id,
                "org_name": org,
                "model_name": model,
                "prompt_technique": strategy,
                "json_mode": json_mode,
                "repetition": rep,
                "name": name,
                "in_ground_truth": ("yes" if key in gold
                                    else "NO" if gold else ""),
                "company_url": url,
                "street": rec.get("street", ""),
                "postcode": rec.get("postcode", ""),
                "city": rec.get("city", ""),
                "phone": rec.get("phone", ""),
                "email": rec.get("email", ""),
                "profile_url": profile,
                "link_status": status,
            })

    rows.sort(key=lambda r: (r["url_id"], r["model_name"], r["prompt_technique"],
                             r["json_mode"], int(r["repetition"]), r["name"].lower()))

    with open(LONG_CSV, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    runs = {(r["url_id"], r["model_name"], r["prompt_technique"],
             r["json_mode"], r["repetition"]) for r in rows}
    print(f"  {len(rows):,} extracted rows from {len(runs):,} runs "
          f"across {len({r['url_id'] for r in rows})} pages")
    if skipped:
        print(f"  {skipped} extraction file(s) unreadable, skipped")
    print(f"  -> {LONG_CSV}")

    if not args.no_xlsx:
        write_xlsx(rows, truth)
        print(f"  -> {REVIEW_XLSX}")


def write_xlsx(rows: list[dict], truth: dict[str, set[str]]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    head = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="365F91")
    miss = PatternFill("solid", fgColor="FFC7CE")   # in truth, not found
    ghost = PatternFill("solid", fgColor="FFEB9C")  # found, not in truth

    def header(ws, labels, row=1):
        for c, label in enumerate(labels, start=1):
            cell = ws.cell(row=row, column=c, value=label)
            cell.font, cell.fill = head, fill
            cell.alignment = Alignment(horizontal="center")
        ws.freeze_panes = ws.cell(row=row + 1, column=1)

    # --- sheet 1: every extraction, unaggregated --------------------------
    ws = wb.active
    ws.title = "raw extractions"
    header(ws, FIELDS)
    for r in rows:
        ws.append([r[f] for f in FIELDS])
    for col, width in zip("ABCDEFGHIJKLMNOP",
                          (8, 26, 18, 22, 12, 5, 38, 9, 34,
                           24, 9, 16, 16, 26, 34, 13)):
        ws.column_dimensions[col].width = width
    ws.auto_filter.ref = ws.dimensions

    # --- sheet 1b: field coverage ----------------------------------------
    # Which fields the pages actually publish. A field that is empty
    # everywhere is a property of the corpus, not a failure of the model, and
    # this is the sheet that tells the two apart.
    wsc = wb.create_sheet("field coverage")
    header(wsc, ["url_id", "org_name", "prompt_technique", "records",
                 "company_url", "profile_url", "street", "postcode",
                 "city", "phone", "email"])

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["url_id"], r["prompt_technique"])].append(r)

    for (page, strategy), items in sorted(groups.items()):
        # One repetition is enough for a coverage count; averaging identical
        # deterministic runs would just scale every number by the same factor.
        first_run = items[0]
        same = [r for r in items
                if (r["model_name"], r["json_mode"], r["repetition"])
                == (first_run["model_name"], first_run["json_mode"],
                    first_run["repetition"])]
        n = len(same) or 1

        def pct(field: str) -> str:
            filled = sum(1 for r in same if str(r.get(field, "")).strip())
            return f"{filled}/{n}" if filled else "-"

        wsc.append([page, first_run["org_name"], strategy, n,
                    pct("company_url"), pct("profile_url"), pct("street"),
                    pct("postcode"), pct("city"), pct("phone"), pct("email")])

    for col, width in zip("ABCDEFGHIJK",
                          (8, 26, 20, 9, 12, 12, 9, 10, 8, 8, 8)):
        wsc.column_dimensions[col].width = width
    wsc.auto_filter.ref = wsc.dimensions

    # --- sheet 2: agreement across configurations -------------------------
    # How many runs found each name, per page. A name every configuration
    # returns but the ground truth lacks is worth re-checking by hand: it is
    # more likely an annotation miss than a shared hallucination.
    ws2 = wb.create_sheet("agreement")
    header(ws2, ["url_id", "org_name", "name", "in_ground_truth",
                 "runs_found", "runs_total", "found_pct", "models_finding"])

    per_page_runs: dict[str, set] = defaultdict(set)
    per_name: dict[tuple[str, str], dict] = {}
    for r in rows:
        run = (r["model_name"], r["prompt_technique"], r["json_mode"], r["repetition"])
        per_page_runs[r["url_id"]].add(run)
        key = (r["url_id"], match_key(r["name"]))
        entry = per_name.setdefault(key, {
            "display": r["name"], "org": r["org_name"],
            "in_gt": r["in_ground_truth"], "runs": set(), "models": set(),
        })
        entry["runs"].add(run)
        entry["models"].add(r["model_name"].split(":")[0])

    # Ground-truth names that nothing found are the most useful rows here, so
    # add them explicitly rather than letting them be absent.
    display_of = {}
    for (page, key), e in per_name.items():
        display_of[(page, key)] = e["display"]
    for page, gold in truth.items():
        if page not in per_page_runs:
            continue
        for key in gold:
            if (page, key) not in per_name:
                per_name[(page, key)] = {
                    "display": f"[missed] {key}", "org": "",
                    "in_gt": "yes", "runs": set(), "models": set(),
                }

    for (page, _), e in sorted(per_name.items(),
                               key=lambda kv: (kv[0][0], -len(kv[1]["runs"]),
                                               kv[1]["display"].lower())):
        total = len(per_page_runs.get(page, ())) or 1
        found = len(e["runs"])
        ws2.append([page, e["org"], e["display"], e["in_gt"], found, total,
                    round(found / total, 3), ", ".join(sorted(e["models"]))])
        if e["in_gt"] == "yes" and found == 0:
            for c in range(1, 9):
                ws2.cell(row=ws2.max_row, column=c).fill = miss
        elif e["in_gt"] == "NO":
            for c in range(1, 9):
                ws2.cell(row=ws2.max_row, column=c).fill = ghost

    for col, width in zip("ABCDEFGH", (8, 26, 42, 9, 10, 10, 10, 24)):
        ws2.column_dimensions[col].width = width
    ws2.auto_filter.ref = ws2.dimensions

    # --- sheet 3: how to read the colours ---------------------------------
    ws3 = wb.create_sheet("readme")
    for i, line in enumerate([
        "Raw extraction dump",
        "",
        "'raw extractions' is every company every run returned, one row each.",
        "Nothing is averaged. Filter by model_name / prompt_technique /",
        "json_mode / url_id to see exactly what one configuration produced.",
        "",
        "'agreement' collapses the repetitions and shows, per page, how many",
        "runs returned each name.",
        "",
        "  red    in the ground truth, no run found it -- a systematic miss",
        "  yellow returned by at least one run, not in the ground truth --",
        "         either a hallucination or a gap in the annotation",
        "",
        "'field coverage' counts how many records carry each field, per page",
        "and per strategy. Empty columns there mean the directory does not",
        "publish that field, not that the model failed to read it.",
        "",
        "COLUMNS",
        "",
        "in_ground_truth is blank for pages that have no ground truth file.",
        "",
        "company_url  what the model returned as the company's own website.",
        "             Verified against the cached page: see link_status,",
        "             which is 'unverified' when the domain is not on the page.",
        "",
        "profile_url  NOT from the model. Worked out here by matching the",
        "             company name against links that stay on the association's",
        "             own site. This is the member's profile page, and it is",
        "             where address / phone / email live when the directory",
        "             listing itself does not print them.",
        "",
        "link_status  company_site  a verified company website was returned",
        "             unverified    a URL was returned but is not on the page",
        "             profile_only  no company site, but a profile page exists",
        "                           -- this is the stage-2 fetch queue",
        "             none          neither; needs search or Impressum lookup",
        "",
        "street / postcode / city / phone / email are populated only by",
        "few_shot_full_record, which is the only strategy that asks for them.",
        "The other strategies leave them blank by design, not by failure.",
    ], start=1):
        ws3.cell(row=i, column=1, value=line)
    ws3.column_dimensions["A"].width = 76

    wb.save(REVIEW_XLSX)


if __name__ == "__main__":
    main()
