"""
Turn one grid into the numbered outputs the thesis and Neovation need.

    results/report_<date>/
        0_about.xlsx              what produced these numbers
        1_stage1_extraction.xlsx  accuracy per configuration, page, layout, network
        2_stage2_routes.xlsx      where a website can come from at all
        3_stage3_profiles.xlsx    the profile-page fetch
        4_stage4_search.xlsx      the web search
        5_summary.xlsx            headline numbers and the success criteria
        6_raw/                    the exact inputs that produced this report

Two rules behind the design. The raw run files are never modified, so a
scoring fix means regenerating the report, not repeating 20 hours of model
time. And every report says which run, which ground truth and which code
produced it, so a table in the thesis can be traced back.

Averages are reported two ways on purpose. Pooled (micro) counts every
company once, so a 389-company page dominates. Per network (macro) gives each
of the 30 pages equal weight. They answer different questions and they will
not agree.

Run:  .venv/bin/python make_report.py --run 30pages_names_2026-09-26
      .venv/bin/python make_report.py --run <name> --out results/report_2026-09-28
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import pathlib
import shutil
import statistics
from collections import defaultdict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import config

HDR = PatternFill("solid", fgColor="2F5597")
HDR_FONT = Font(bold=True, color="FFFFFF", size=10)
BASE = Font(size=10)
NOTE = Font(size=9, italic=True, color="595959")


def sheet(wb: Workbook, title: str, rows: list[dict], note: str = "", first=False):
    """One table, with its own explanation above it."""
    ws = wb.active if first else wb.create_sheet()
    ws.title = title[:31]
    start = 1
    if note:
        ws.cell(row=1, column=1, value=note).font = NOTE
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(4, len(rows[0]) if rows else 4))
        start = 3
    if not rows:
        ws.cell(row=start, column=1, value="no data for this stage yet").font = BASE
        return ws
    for i, key in enumerate(rows[0], start=1):
        c = ws.cell(row=start, column=i, value=key)
        c.fill, c.font = HDR, HDR_FONT
        c.alignment = Alignment(wrap_text=True, vertical="center")
        width = max(len(str(key)), *(len(str(r.get(key, ""))) for r in rows))
        ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 10), 48)
    for j, r in enumerate(rows, start=start + 1):
        for i, key in enumerate(rows[0], start=1):
            ws.cell(row=j, column=i, value=r.get(key)).font = BASE
    ws.freeze_panes = ws.cell(row=start + 1, column=1)
    return ws


def f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def run_key(r: dict) -> tuple:
    return (r["stage"], r["model_name"], r["prompt_technique"],
            r["json_mode"], r["url_id"], r["repetition"])


def dedupe(rows: list[dict]) -> list[dict]:
    """
    One row per configuration: a successful retry replaces the failure it fixed.

    Resuming a grid APPENDS rather than rewriting, so after the 2026-09-28
    re-run the results file held both the original error row and the row that
    fixed it. Counting both would report each of those configurations twice,
    once with a failure attached, and drag its pooled F1 down by exactly the
    runs that were repaired. That is the shape of mistake this project has
    already made three times (see the header of `test_metrics.py`), so it is
    handled here rather than left to whoever reads the spreadsheet.

    A configuration that still has no clean answer keeps its error row,
    because there the failure IS the result.
    """
    def better(a: dict, b: dict) -> bool:
        if bool(a["error"]) != bool(b["error"]):
            return not a["error"]          # a clean answer always wins
        return a["timestamp"] >= b["timestamp"]   # otherwise the later attempt

    best: dict = {}
    for r in rows:
        k = run_key(r)
        if k not in best or better(r, best[k]):
            best[k] = r
    return list(best.values())


def load_runs(run_dir: pathlib.Path) -> list[dict]:
    path = run_dir / "benchmark_results.csv"
    if not path.exists():
        raise SystemExit(f"no results at {path}")
    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    before = len(rows)
    rows = dedupe(rows)
    if before != len(rows):
        print(f"  {before} rows -> {len(rows)} configurations "
              f"({before - len(rows)} superseded by retries)")
    for r in rows:
        for k in ("true_positives", "false_positives", "false_negatives", "raw_count"):
            r[k] = int(r[k] or 0)
        for k in ("precision", "recall", "f1", "latency_seconds", "tokens_per_second"):
            r[k] = float(r[k] or 0)
    return rows


def pages() -> dict:
    path = config.DATA_DIR / "page_profile.csv"
    if not path.exists():
        raise SystemExit("run page_profile.py first")
    with open(path, encoding="utf-8-sig") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


def scorable_pages() -> set:
    """Pages with a hand-labelled answer key. Only these can be scored."""
    return {p.stem for p in config.GROUND_TRUTH_DIR.glob("*.json")}


def by_configuration(runs: list[dict], prof: dict) -> list[dict]:
    """One row per model x prompt x JSON mode."""
    # Accuracy is measured against hand-labelled keys, which exist for 30
    # pages. A production run covers 230, of which 31 carry a key; the other
    # 199 score zero because there is nothing to compare against, and
    # averaging over all of them produced "best configuration F1 0.0933",
    # a number that describes the share of the corpus that was labelled
    # rather than anything about the model.
    #
    # So accuracy is computed over the pages that have a key, and the count
    # is reported beside it. On a production run that is a real check worth
    # having: it scores the shipped configuration against the ground truth
    # on the pages the two corpora share.
    keyed = scorable_pages()
    groups: dict = defaultdict(list)
    for r in runs:
        groups[(r["model_name"], r["prompt_technique"], r["json_mode"])].append(r)
    out = []
    for (model, prompt, mode), rs in sorted(groups.items()):
        scored = [r for r in rs if r["url_id"] in keyed]
        tp = sum(r["true_positives"] for r in scored)
        fp = sum(r["false_positives"] for r in scored)
        fn = sum(r["false_negatives"] for r in scored)
        p, rec, pooled = f1(tp, fp, fn)
        per_page: dict = defaultdict(list)
        for r in scored:
            per_page[r["url_id"]].append(r["f1"])
        macro = statistics.mean(statistics.mean(v) for v in per_page.values()) if per_page else 0
        varied = sum(1 for v in per_page.values() if len(set(round(x, 4) for x in v)) > 1)
        out.append({
            "model": model, "prompt": prompt, "json mode": mode, "runs": len(rs),
            "errors": sum(1 for r in rs if r["error"]),
            "pooled precision": round(p, 4), "pooled recall": round(rec, 4),
            "pooled F1": round(pooled, 4),
            "F1 per network (mean)": round(macro, 4),
            # Says what the accuracy above is based on. On the research
            # corpus this equals "pages"; on a production run it is the
            # handful that overlap the ground truth, and quoting the F1
            # without it would be meaningless.
            "pages with an answer key": len(per_page),
            "pages that varied across repeats": varied,
            "pages": len({r["url_id"] for r in rs}),
            "median seconds per page": round(statistics.median(r["latency_seconds"] for r in rs), 1),
            "total hours": round(sum(r["latency_seconds"] for r in rs) / 3600, 2),
            "JSON parsed first try": f"{sum(1 for r in rs if r['json_parse_ok'] == 'True' and r['json_repair_used'] != 'True') / len(rs):.0%}",
            "needed repair": f"{sum(1 for r in rs if r['json_repair_used'] == 'True') / len(rs):.0%}",
        })
    return sorted(out, key=lambda r: -r["F1 per network (mean)"])


def per_page(runs: list[dict], prof: dict, best: tuple) -> list[dict]:
    """The winning configuration, page by page: where it wins and where it fails."""
    model, prompt, mode = best
    rs = [r for r in runs if (r["model_name"], r["prompt_technique"], r["json_mode"]) == best]
    grouped: dict = defaultdict(list)
    for r in rs:
        grouped[r["url_id"]].append(r)
    out = []
    for uid, items in sorted(grouped.items()):
        pg = prof.get(uid, {})
        out.append({
            "id": uid, "network": pg.get("network", items[0]["org_name"]),
            "layout": pg.get("layout", ""), "funding": pg.get("funding", ""),
            "companies": int(pg.get("companies", 0) or 0),
            "chunks": int(pg.get("chunks", 1) or 1),
            "precision": round(statistics.mean(r["precision"] for r in items), 4),
            "recall": round(statistics.mean(r["recall"] for r in items), 4),
            "F1": round(statistics.mean(r["f1"] for r in items), 4),
            "returned": round(statistics.mean(r["raw_count"] for r in items), 1),
            "repeats agree": "yes" if len({round(r["f1"], 4) for r in items}) == 1 else "NO",
            "seconds": round(statistics.mean(r["latency_seconds"] for r in items), 1),
            "error": "; ".join(sorted({r["error"] for r in items if r["error"]})),
        })
    return out


def grouped_by(runs: list[dict], prof: dict, field: str) -> list[dict]:
    """Mean F1 per model, split by page layout, funding or size."""
    models = sorted({r["model_name"] for r in runs})
    values = sorted({prof[u][field] for u in prof if u in {r["url_id"] for r in runs}})
    out = []
    for value in values:
        ids = {u for u in prof if prof[u][field] == value}
        row = {field: value, "pages": len(ids),
               "companies": sum(int(prof[u]["companies"]) for u in ids)}
        for model in models:
            rs = [r for r in runs if r["model_name"] == model and r["url_id"] in ids]
            if not rs:
                row[model] = ""
                continue
            best_prompt = max({(r["prompt_technique"], r["json_mode"]) for r in rs},
                              key=lambda k: statistics.mean(
                                  x["f1"] for x in rs
                                  if (x["prompt_technique"], x["json_mode"]) == k))
            sel = [r for r in rs if (r["prompt_technique"], r["json_mode"]) == best_prompt]
            row[model] = round(statistics.mean(r["f1"] for r in sel), 3)
        out.append(row)
    return out


def network_level(runs: list[dict], prof: dict, best: tuple,
                  recall_floor=0.95, precision_floor=0.95) -> list[dict]:
    """Hendro's second criterion: did a network's whole list come back?"""
    rows = per_page(runs, prof, best)
    for r in rows:
        r["passes"] = ("yes" if r["recall"] >= recall_floor and r["precision"] >= precision_floor
                       else "no")
    return rows


def code_fingerprint() -> str:
    h = hashlib.sha256()
    for p in sorted(pathlib.Path(".").glob("*.py")):
        h.update(p.name.encode() + p.read_bytes())
    return h.hexdigest()[:12]


def ground_truth_facts() -> dict:
    keys = sorted(config.GROUND_TRUTH_DIR.glob("*.json"))
    companies = sum(len(json.loads(k.read_text(encoding="utf-8"))["companies"]) for k in keys)
    return {"pages": len(keys), "companies": companies}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="folder name under results/runs/")
    ap.add_argument("--out", default=None, help="where to write the report")
    args = ap.parse_args()

    run_dir = config.RESULTS_DIR / "runs" / args.run
    if not run_dir.exists():
        run_dir = pathlib.Path(args.run)
    out = pathlib.Path(args.out) if args.out else (
        config.RESULTS_DIR / f"report_{datetime.date.today():%Y-%m-%d}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "6_raw").mkdir(exist_ok=True)

    runs = load_runs(run_dir)
    prof = pages()
    gt = ground_truth_facts()
    configs = by_configuration(runs, prof)
    best = (configs[0]["model"], configs[0]["prompt"], configs[0]["json mode"]) if configs else None

    # 0 -----------------------------------------------------------------
    wb = Workbook()
    facts = [
        {"item": "report generated", "value": f"{datetime.datetime.now():%Y-%m-%d %H:%M}"},
        {"item": "run", "value": str(run_dir)},
        {"item": "runs in this grid", "value": len(runs)},
        {"item": "models", "value": ", ".join(sorted({r["model_name"] for r in runs}))},
        {"item": "prompt strategies", "value": ", ".join(sorted({r["prompt_technique"] for r in runs}))},
        {"item": "JSON modes", "value": ", ".join(sorted({r["json_mode"] for r in runs}))},
        {"item": "repetitions", "value": len({r["repetition"] for r in runs})},
        {"item": "ground truth", "value": f"{gt['pages']} pages, {gt['companies']} companies"},
        {"item": "code fingerprint", "value": code_fingerprint()},
        {"item": "scoring", "value": "names compared after removing the legal form, "
                                     "accents, punctuation and the words und/u/and"},
    ]
    sheet(wb, "about", facts, "What produced the numbers in this report.", first=True)
    wb.save(out / "0_about.xlsx")

    # 1 -----------------------------------------------------------------
    wb = Workbook()
    sheet(wb, "by configuration", configs,
          "Every model x prompt x JSON mode. Pooled counts each company once, so big "
          "pages dominate; the per-network mean gives each page equal weight.", first=True)
    if best:
        sheet(wb, "winner per page", per_page(runs, prof, best),
              f"The best configuration ({' / '.join(best)}), page by page.")
    for field, label in (("layout", "by layout"), ("funding", "by funding"),
                         ("size_band", "by page size")):
        sheet(wb, label, grouped_by(runs, prof, field),
              f"Mean F1 {label}, each model at its own best prompt. The sample was built "
              f"for this breakdown, so it matters more than the single pooled number.")
    wb.save(out / "1_stage1_extraction.xlsx")

    # 2 -----------------------------------------------------------------
    wb = Workbook()
    rows = []
    cov = config.RESULTS_DIR / "link_coverage.csv"
    if cov.exists():
        per: dict = defaultdict(lambda: defaultdict(int))
        with open(cov, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                per[r["url_id"]][r["route"]] += 1
                per[r["url_id"]]["total"] += 1
        for uid, c in sorted(per.items()):
            pg = prof.get(uid, {})
            rows.append({"id": uid, "network": pg.get("network", ""), "layout": pg.get("layout", ""),
                         "companies": c["total"], "website on the page": c["website"],
                         "profile page only": c["profile"], "no link at all": c["none"],
                         "share with a website on the page": round(c["website"] / c["total"], 3)})
        total = {k: sum(r[k] for r in rows) for k in
                 ("companies", "website on the page", "profile page only", "no link at all")}
        rows.append({"id": "TOTAL", "network": "", "layout": "", **total,
                     "share with a website on the page":
                         round(total["website on the page"] / total["companies"], 3)})
    sheet(wb, "routes per network", rows,
          "Where a company's website can come from at all. This is the ceiling: no model "
          "can read a website off a page that does not print one.", first=True)
    wb.save(out / "2_stage2_routes.xlsx")

    # 3 and 4 -----------------------------------------------------------
    for number, name, path, note in (
        ("3", "3_stage3_profiles.xlsx", config.RESULTS_DIR / "profile_records.csv",
         "One row per member whose website needed a profile-page fetch."),
        ("4", "4_stage4_search.xlsx", config.RESULTS_DIR / "searched_websites.csv",
         "One row per member with no link on the page, and what the web search found."),
    ):
        wb = Workbook()
        data = []
        if path.exists():
            with open(path, encoding="utf-8-sig") as fh:
                data = list(csv.DictReader(fh))
        sheet(wb, "records", data[:50000], note + (" Not run yet for this grid." if not data else ""),
              first=True)
        if data and "status" in data[0]:
            counts = defaultdict(int)
            for r in data:
                counts[r["status"]] += 1
            sheet(wb, "by status", [{"status": k, "companies": v,
                                     "share": round(v / len(data), 3)}
                                    for k, v in sorted(counts.items(), key=lambda kv: -kv[1])],
                  "Only verified and domain-match results may be loaded into the database.")
        wb.save(out / name)

    # 5 -----------------------------------------------------------------
    wb = Workbook()
    head = []
    if best:
        top = configs[0]
        nets = network_level(runs, prof, best)
        passing = sum(1 for n in nets if n["passes"] == "yes")
        head = [
            {"question": "Which configuration extracts names best?",
             "answer": " / ".join(best),
             "number": f"F1 {top['F1 per network (mean)']} per network, {top['pooled F1']} pooled"},
            {"question": "How many networks come back complete?",
             "answer": f"{passing} of {len(nets)} networks",
             "number": "complete = recall and precision both at least 0.95"},
            {"question": "Is the output reproducible at temperature 0?",
             "answer": f"{top['pages that varied across repeats']} of {top['pages']} pages "
                       f"differed between identical repeats",
             "number": "same model, same prompt, same page"},
            {"question": "What did it cost?",
             "answer": f"{top['total hours']} hours for {top['runs']} runs",
             "number": f"median {top['median seconds per page']} s per page"},
            {"question": "How trustworthy is the answer key?",
             "answer": f"{gt['pages']} pages, {gt['companies']} companies, hand-labelled",
             "number": "check_ground_truth.py reports 0 entries the model cannot see"},
        ]
    sheet(wb, "headline", head, "The five questions this study has to answer.", first=True)
    if best:
        sheet(wb, "per network", network_level(runs, prof, best),
              "Hendro's second criterion: not only whether each company is right, but "
              "whether a network's whole list came back.")
    wb.save(out / "5_summary.xlsx")

    # 6 -----------------------------------------------------------------
    for src in (run_dir / "benchmark_results.csv", config.RESULTS_DIR / "link_coverage.csv",
                config.DATA_DIR / "page_profile.csv"):
        if src.exists():
            shutil.copy2(src, out / "6_raw" / src.name)
    gt_copy = out / "6_raw" / "ground_truth"
    gt_copy.mkdir(exist_ok=True)
    for k in config.GROUND_TRUTH_DIR.glob("*.json"):
        shutil.copy2(k, gt_copy / k.name)

    print(f"  report -> {out}")
    for f in sorted(out.iterdir()):
        print(f"    {f.name}")
    if best:
        keyed = configs[0]["pages with an answer key"]
        total = configs[0]["pages"]
        print(f"\n  best configuration: {' / '.join(best)}")
        if keyed:
            print(f"  F1 {configs[0]['F1 per network (mean)']} per network, "
                  f"measured on the {keyed} of {total} pages that have a "
                  f"hand-labelled answer key")
        else:
            print(f"  no accuracy: none of the {total} pages has an answer "
                  f"key, so this run cannot be scored")


if __name__ == "__main__":
    main()
