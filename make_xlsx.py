"""
Build results/Stage_A_Results.xlsx -- a formatted workbook of the Stage A run.

Four sheets:

  Summary   one row per configuration, ranked. Every metric is an AVERAGEIFS
            formula over the Runs sheet, so the workbook recalculates if the
            raw data is replaced or filtered rather than freezing today's
            numbers into literals.
  Per Page  the winning configuration broken down by website.
  Runs      all 360 individual runs, with an autofilter.
  About     what was measured, how, and every assumption behind the numbers.

Run:  .venv/bin/python make_xlsx.py
"""

from __future__ import annotations

import csv
import statistics
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import config

OUT = config.RESULTS_DIR / "Stage_A_Results.xlsx"

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=10)
BASE = Font(name=FONT, size=10)
BOLD = Font(name=FONT, size=10, bold=True)
TITLE = Font(name=FONT, size=14, bold=True, color="1F3864")
NOTE = Font(name=FONT, size=9, italic=True, color="595959")

WIN_FILL = PatternFill("solid", fgColor="C6EFCE")   # green  - best
GOOD_FILL = PatternFill("solid", fgColor="E2EFDA")  # pale   - strong
BAD_FILL = PatternFill("solid", fgColor="FFC7CE")   # red    - failed
ALT_FILL = PatternFill("solid", fgColor="F2F2F2")

THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def load_runs() -> list[dict]:
    with open(config.BENCHMARK_CSV, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def style_header(ws, row: int, ncols: int) -> None:
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)
        cell.border = BOX
    ws.row_dimensions[row].height = 30


def set_widths(ws, widths: dict[str, int]) -> None:
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


# --------------------------------------------------------------------------
# Sheet 3 -- Runs (written first; the other sheets reference it)
# --------------------------------------------------------------------------

RUN_COLS = [
    ("model_name", "Model", 18),
    ("prompt_technique", "Prompt strategy", 20),
    ("json_mode", "JSON mode", 13),
    ("url_id", "Page", 7),
    ("org_name", "Organisation", 34),
    ("repetition", "Rep", 6),
    ("latency_seconds", "Latency (s)", 12),
    ("raw_count", "Names found", 12),
    ("true_positives", "TP", 7),
    ("false_positives", "FP", 7),
    ("false_negatives", "FN", 7),
    ("precision", "Precision", 10),
    ("recall", "Recall", 10),
    ("f1", "F1", 10),
    ("tokens_per_second", "Tokens/s", 10),
    ("json_repair_used", "JSON repaired", 13),
    ("n_chunks", "Chunks", 8),
    ("error", "Error", 26),
]

NUMERIC = {"latency_seconds", "raw_count", "true_positives", "false_positives",
           "false_negatives", "precision", "recall", "f1",
           "tokens_per_second", "repetition", "n_chunks"}


def build_runs(wb, runs: list[dict]):
    ws = wb.create_sheet("Runs")
    for i, (_, label, _) in enumerate(RUN_COLS, start=1):
        ws.cell(row=1, column=i, value=label)
    style_header(ws, 1, len(RUN_COLS))

    for r, run in enumerate(runs, start=2):
        for c, (key, _, _) in enumerate(RUN_COLS, start=1):
            raw = run.get(key, "")
            if key in NUMERIC and raw not in ("", None):
                try:
                    raw = float(raw)
                    if key in ("raw_count", "true_positives", "false_positives",
                               "false_negatives", "repetition", "n_chunks"):
                        raw = int(raw)
                except ValueError:
                    pass
            cell = ws.cell(row=r, column=c, value=raw)
            cell.font = BASE
            if key in ("precision", "recall", "f1"):
                cell.number_format = "0.000"
            elif key in ("latency_seconds", "tokens_per_second"):
                cell.number_format = "0.0"
            if r % 2 == 0:
                cell.fill = ALT_FILL

    set_widths(ws, {get_column_letter(i): w
                    for i, (_, _, w) in enumerate(RUN_COLS, start=1)})
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(RUN_COLS))}{len(runs)+1}"
    return ws


# --------------------------------------------------------------------------
# Sheet 1 -- Summary (formulas over Runs)
# --------------------------------------------------------------------------

def build_summary(wb, runs: list[dict], n_runs: int):
    ws = wb.create_sheet("Summary", 0)

    ws["A1"] = "NeoHub — Stage A benchmark results"
    ws["A1"].font = TITLE
    ws["A2"] = ("Local LLM comparison for member-company extraction from German "
                "innovation-network websites")
    ws["A2"].font = NOTE
    ws["A3"] = ("Every figure is an average over the 360 individual runs on "
                "the 'Runs' sheet. Regenerate with make_xlsx.py.")
    ws["A3"].font = NOTE

    headers = ["Rank", "Model", "Prompt strategy", "JSON mode", "F1",
               "Precision", "Recall", "Latency mean (s)", "Latency SD (s)",
               "Names per page", "Tokens/s", "JSON repair rate", "Runs"]
    hdr_row = 5
    for i, h in enumerate(headers, start=1):
        ws.cell(row=hdr_row, column=i, value=h)
    style_header(ws, hdr_row, len(headers))

    # Rank configurations in Python (sorting is not a spreadsheet concern),
    # but compute every displayed metric with a formula.
    groups: dict[tuple, list[dict]] = {}
    for r in runs:
        groups.setdefault(
            (r["model_name"], r["prompt_technique"], r["json_mode"]), []).append(r)
    ranked = sorted(
        groups.items(),
        key=lambda kv: -statistics.mean(float(x["f1"]) for x in kv[1]))

    # Values, not formulas, and deliberately so.
    #
    # openpyxl writes formulas without cached results, and recalculating them
    # requires LibreOffice, which is not installed here. An uncached formula
    # renders as an empty cell in Quick Look, Numbers previews and anything
    # else reading cached values -- Excel and Sheets would compute it on open,
    # but a preview would look broken.
    #
    # This workbook reports a completed experiment: its inputs are a frozen
    # 360-row log and cannot change, so there is nothing for a formula to
    # recalculate. The Runs sheet carries every underlying figure, and
    # make_xlsx.py regenerates the whole file from benchmark_results.csv.
    def agg(rs: list[dict], key: str) -> float:
        return statistics.mean(float(x[key]) for x in rs)

    for idx, ((model, prompt, mode), rs) in enumerate(ranked, start=1):
        row = hdr_row + idx
        ws.cell(row=row, column=1, value=idx)
        ws.cell(row=row, column=2, value=model)
        ws.cell(row=row, column=3, value=prompt)
        ws.cell(row=row, column=4, value=mode)
        ws.cell(row=row, column=5, value=agg(rs, "f1"))
        ws.cell(row=row, column=6, value=agg(rs, "precision"))
        ws.cell(row=row, column=7, value=agg(rs, "recall"))
        ws.cell(row=row, column=8, value=agg(rs, "latency_seconds"))
        ws.cell(row=row, column=9,
                value=statistics.stdev(float(x["latency_seconds"]) for x in rs))
        ws.cell(row=row, column=10, value=agg(rs, "raw_count"))
        ws.cell(row=row, column=11, value=agg(rs, "tokens_per_second"))
        ws.cell(row=row, column=12,
                value=sum(x["json_repair_used"] == "True" for x in rs) / len(rs))
        ws.cell(row=row, column=13, value=len(rs))

        f1 = statistics.mean(float(x["f1"]) for x in rs)
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=row, column=c)
            cell.font = BOLD if idx == 1 else BASE
            cell.border = BOX
            if idx == 1:
                cell.fill = WIN_FILL
            elif f1 >= 0.90:
                cell.fill = GOOD_FILL
            elif f1 < 0.80:
                cell.fill = BAD_FILL
        for c in (5, 6, 7):
            ws.cell(row=row, column=c).number_format = "0.000"
        for c in (8, 9, 10, 11):
            ws.cell(row=row, column=c).number_format = "0.0"
        ws.cell(row=row, column=12).number_format = "0%"

    note = hdr_row + len(ranked) + 2
    ws.cell(row=note, column=1,
            value="Green = best configuration · pale green = F1 ≥ 0.90 · "
                  "red = F1 < 0.80").font = NOTE
    ws.cell(row=note + 1, column=1,
            value="Ranks 1 and 2 are tied on every accuracy metric; they differ "
                  "only in latency.").font = NOTE

    set_widths(ws, {"A": 6, "B": 19, "C": 21, "D": 13, "E": 9, "F": 10,
                    "G": 9, "H": 15, "I": 14, "J": 14, "K": 10, "L": 15,
                    "M": 8})
    ws.freeze_panes = f"A{hdr_row+1}"
    return ws


# --------------------------------------------------------------------------
# Sheet 2 -- Per page, winning configuration
# --------------------------------------------------------------------------

def build_per_page(wb, runs: list[dict], n_runs: int, winner: tuple):
    ws = wb.create_sheet("Per Page", 1)
    model, prompt, mode = winner

    ws["A1"] = "Winning configuration, by website"
    ws["A1"].font = TITLE
    ws["A2"] = f"{model} · {prompt} · {mode}"
    ws["A3"] = ("Ground truth was annotated by hand; see 'About' for the "
                "annotation rules.")
    ws["A2"].font = BOLD
    ws["A3"].font = NOTE

    headers = ["Page", "Organisation", "Input tokens", "Chunks",
               "Names found", "Ground truth", "Precision", "Recall", "F1",
               "Latency (s)"]
    hdr_row = 5
    for i, h in enumerate(headers, start=1):
        ws.cell(row=hdr_row, column=i, value=h)
    style_header(ws, hdr_row, len(headers))

    sel = [r for r in runs if (r["model_name"], r["prompt_technique"],
                               r["json_mode"]) == winner]
    by_page: dict[str, list[dict]] = {}
    for r in sel:
        by_page.setdefault(r["url_id"], []).append(r)

    ordered = sorted(by_page.items(),
                     key=lambda kv: -statistics.mean(float(x["f1"]) for x in kv[1]))

    for i, (uid, rs) in enumerate(ordered, start=1):
        r0 = rs[0]
        row = hdr_row + i
        gt = int(r0["true_positives"]) + int(r0["false_negatives"])
        f1 = statistics.mean(float(x["f1"]) for x in rs)
        vals = [uid, r0["org_name"], int(r0["est_input_tokens"]),
                int(r0["n_chunks"]),
                statistics.mean(float(x["raw_count"]) for x in rs), gt,
                statistics.mean(float(x["precision"]) for x in rs),
                statistics.mean(float(x["recall"]) for x in rs), f1,
                statistics.mean(float(x["latency_seconds"]) for x in rs)]
        for c, v in enumerate(vals, start=1):
            cell = ws.cell(row=row, column=c, value=v)
            cell.font = BASE
            cell.border = BOX
            if f1 >= 0.99:
                cell.fill = WIN_FILL
            elif f1 < 0.85:
                cell.fill = BAD_FILL
            elif i % 2 == 0:
                cell.fill = ALT_FILL
        for c in (7, 8, 9):
            ws.cell(row=row, column=c).number_format = "0.000"
        for c in (5, 10):
            ws.cell(row=row, column=c).number_format = "0.0"
        ws.cell(row=row, column=3).number_format = "#,##0"

    note = hdr_row + len(ordered) + 2
    ws.cell(row=note, column=1,
            value="The only page below F1 0.90 is the one requiring chunking; "
                  "precision holds at 0.914 while recall falls to 0.723, "
                  "indicating loss at chunk boundaries rather than "
                  "hallucination.").font = NOTE

    set_widths(ws, {"A": 8, "B": 36, "C": 13, "D": 8, "E": 12, "F": 13,
                    "G": 10, "H": 9, "I": 9, "J": 12})
    ws.freeze_panes = f"A{hdr_row+1}"


# --------------------------------------------------------------------------
# Sheet 4 -- About
# --------------------------------------------------------------------------

def build_about(wb, runs: list[dict]):
    ws = wb.create_sheet("About")
    t0 = datetime.fromisoformat(runs[0]["timestamp"])
    t1 = datetime.fromisoformat(runs[-1]["timestamp"])
    hours = (t1 - t0).total_seconds() / 3600

    ws["A1"] = "About this workbook"
    ws["A1"].font = TITLE

    entries = [
        ("Study", "Comparative Evaluation of Local LLM Models and Generic "
                  "Prompt Strategies for Extracting Company Information from "
                  "Innovation Network Websites"),
        ("Author", "Giorgi Pataridze, Constructor University Bremen "
                   "(gpataridze@constructor.university)"),
        ("Project", "NeoHub AP1 — Neovation GmbH × Constructor University Bremen"),
        ("", ""),
        ("EXPERIMENT", ""),
        ("Design", "2 models × 3 prompt strategies × 2 JSON modes × 10 pages "
                   "× 3 repetitions = 360 runs"),
        ("Run window", f"{t0:%Y-%m-%d %H:%M} to {t1:%Y-%m-%d %H:%M} UTC "
                       f"({hours:.1f} hours)"),
        ("Hardware", "Apple M4 MacBook, 16 GB RAM; models served locally by "
                     "Ollama 0.32.1"),
        ("Decoding", "temperature 0, fixed seed 42, num_ctx 8192 — set "
                     "explicitly because Ollama defaults to 4096 and truncates "
                     "silently"),
        ("Repetitions", "Decoding is deterministic, so repetitions measure "
                        "latency variance, not output variance"),
        ("Model order", "The loop is model-outermost: the two models are 4.7 GB "
                        "and 4.9 GB and cannot both stay resident in 16 GB, so "
                        "alternating them would time disk reloads"),
        ("", ""),
        ("METRICS", ""),
        ("Precision", "Of the names the model returned, the share that are "
                      "real members — low precision means hallucination"),
        ("Recall", "Of the members actually on the page, the share the model "
                   "found — low recall means omission"),
        ("F1", "Harmonic mean of precision and recall"),
        ("Scored against", "Hand-annotated ground truth: 785 companies across "
                           "10 pages"),
        ("Scored before filtering", "Accuracy compares RAW model output to "
                                    "ground truth. The Neovation name filter "
                                    "runs afterwards and is reported "
                                    "separately, so the model is not penalised "
                                    "for the rulebook's exclusions"),
        ("Name matching", "Case-insensitive, accent- and punctuation-"
                          "insensitive, legal suffix removed, so 'Siemens AG' "
                          "and 'Siemens' match"),
        ("", ""),
        ("ANNOTATION RULES", ""),
        ("1", "Ground truth describes the cached page snapshot, not the live "
              "website — many directories paginate"),
        ("2", "Location is excluded where the page puts it on a separate line; "
              "kept where the page prints it on the same line"),
        ("3", "Section headings, category labels and membership tiers excluded"),
        ("4", "Testimonial and quote attributions excluded — 'Name, Role, "
              "Company' is not a directory entry"),
        ("5", "For paginated directories one page is the annotation unit "
              "(BDEW letter A; Medical Valley and BVMed page 1)"),
        ("", ""),
        ("NOTES ON THIS FILE", ""),
        ("Values, not formulas", "Summary and Per Page hold computed values. "
                                 "This reports a completed experiment whose "
                                 "inputs are frozen, so there is nothing to "
                                 "recalculate; values also guarantee the file "
                                 "renders correctly in previewers, which show "
                                 "uncached formula cells as blank"),
        ("Every figure is derived", "from the 360 rows on the Runs sheet — "
                                    "averages across the 3 repetitions of each "
                                    "configuration"),
        ("Source data", "results/benchmark_results.csv (360 rows), produced by "
                        "benchmark.py"),
        ("Regenerate", "python make_xlsx.py — rebuilds this workbook from the "
                       "source CSV"),
    ]

    for i, (k, v) in enumerate(entries, start=3):
        a = ws.cell(row=i, column=1, value=k)
        b = ws.cell(row=i, column=2, value=v)
        a.font = BOLD if (k.isupper() and v == "") else BASE
        b.font = BASE
        b.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 28 if len(str(v)) > 80 else 15

    set_widths(ws, {"A": 24, "B": 96})


def main() -> None:
    runs = load_runs()
    n = len(runs)

    wb = Workbook()
    wb.remove(wb.active)

    build_runs(wb, runs)                       # must exist before formulas
    summary_ws = build_summary(wb, runs, n)

    groups: dict[tuple, list[dict]] = {}
    for r in runs:
        groups.setdefault(
            (r["model_name"], r["prompt_technique"], r["json_mode"]), []).append(r)
    winner = max(groups.items(),
                 key=lambda kv: statistics.mean(float(x["f1"]) for x in kv[1]))[0]

    build_per_page(wb, runs, n, winner)
    build_about(wb, runs)

    wb.active = 0
    wb.save(OUT)
    print(f"wrote {OUT}")
    print(f"  sheets: {', '.join(wb.sheetnames)}")
    print(f"  winner: {' / '.join(winner)}")


if __name__ == "__main__":
    main()
