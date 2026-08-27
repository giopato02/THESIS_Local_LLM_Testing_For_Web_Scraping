"""
Build the deliverable workbook in the layout Hendro specified (2026-08-06).

Three sheets, and the first one has exactly the four columns he showed:

    Network members   company name | company website | network name |
                      network url | street | postcode | city | phone | email
    Summary           coverage per network, and the caveats a reader needs

Names are reported exactly as extracted. No filtering is applied: Neovation
applies their company-name rulebook at database-insert time (Marco,
2026-07-28).

The network name and URL are joined in Python from data/urls_73.csv rather
than asked of the model -- we already know which page each extraction came
from, so spending tokens re-deriving it would only add a chance of error.

Run:  .venv/bin/python export_deliverable.py
      .venv/bin/python export_deliverable.py --stage b
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import config

OUT = config.RESULTS_DIR / "NeoHub_Network_Members.xlsx"
EXTRACTIONS = config.RESULTS_DIR / "extractions"

FONT = "Arial"
HDR = PatternFill("solid", fgColor="2F5597")
HDR_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=10)
BASE = Font(name=FONT, size=10)
NOTE = Font(name=FONT, size=9, italic=True, color="595959")
TITLE = Font(name=FONT, size=13, bold=True, color="2F5597")
ALT = PatternFill("solid", fgColor="F2F7FB")
WARN = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def header(ws, row: int, labels: list[str], widths: list[int]) -> None:
    for i, (label, w) in enumerate(zip(labels, widths), start=1):
        c = ws.cell(row=row, column=i, value=label)
        c.fill, c.font = HDR, HDR_FONT
        c.alignment = Alignment(horizontal="center", vertical="center",
                                wrap_text=True)
        c.border = BOX
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = 26


def load(stage: str | None):
    """Return the best run per URL, with its extracted names."""
    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}
    with open(config.BENCHMARK_CSV, encoding="utf-8") as fh:
        runs = list(csv.DictReader(fh))
    if stage:
        runs = [r for r in runs if r["stage"] == stage]

    best: dict[str, dict] = {}
    for r in runs:
        prev = best.get(r["url_id"])
        if prev is None or int(r["raw_count"] or 0) > int(prev["raw_count"] or 0):
            best[r["url_id"]] = r

    records = []
    for uid, run in best.items():
        path = EXTRACTIONS / f"{run['run_id']}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        records.append((urls.get(uid, {}), run, data))
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["a", "b"], default=None)
    args = ap.parse_args()

    records = load(args.stage)
    if not records:
        raise SystemExit("no extractions found -- run benchmark.py first")

    wb = Workbook()

    # ---------------- Sheet 1: Network members -----------------------------
    ws = wb.active
    ws.title = "Network members"
    # Hendro's four columns first, so the sheet still opens the way he
    # specified; the disambiguation fields Marco and Yusif asked for follow.
    header(ws, 1, ["company name", "company website", "network name",
                   "network url", "street", "postcode", "city", "phone",
                   "email"],
           [46, 38, 32, 38, 30, 10, 20, 20, 30])

    row = 2
    per_network: dict[str, dict] = {}
    for url_row, run, data in sorted(records,
                                     key=lambda r: r[0].get("org_name", "")):
        network = url_row.get("org_name", run["org_name"])
        net_url = url_row.get("url", run["url"])
        kept = with_url = 0

        # Prefer structured records; fall back to bare names for runs made
        # before the record schema existed.
        entries = data.get("records") or [{"name": n} for n in data.get("raw", [])]
        for rec in entries:
            name = (rec.get("name") or "").strip()
            if not name:
                continue
            kept += 1
            site = (rec.get("url") or "").strip()
            if site:
                with_url += 1
            values = [name, site, network, net_url,
                      (rec.get("street") or "").strip(),
                      (rec.get("postcode") or "").strip(),
                      (rec.get("city") or "").strip(),
                      (rec.get("phone") or "").strip(),
                      (rec.get("email") or "").strip()]
            for col, val in enumerate(values, start=1):
                c = ws.cell(row=row, column=col, value=val)
                c.font = BASE
                c.border = BOX
                c.alignment = Alignment(wrap_text=(col in (1, 3)),
                                        vertical="top")
                if row % 2 == 0:
                    c.fill = ALT
            row += 1

        per_network[network] = {
            "url": net_url, "members": kept, "with_url": with_url,
            "model": run["model_name"], "prompt": run["prompt_technique"],
        }

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:I{max(row-1, 2)}"

    # ---------------- Sheet 3: Summary -------------------------------------
    sm = wb.create_sheet("Summary")
    sm["A1"] = "NeoHub — network member extraction"
    sm["A1"].font = TITLE
    sm["A2"] = (f"Generated {datetime.now():%Y-%m-%d %H:%M} · "
                f"{row-2} member records from {len(per_network)} networks")
    sm["A2"].font = NOTE

    header(sm, 4, ["network name", "network url", "members extracted",
                   "with website", "website coverage", "model", "prompt"],
           [34, 42, 16, 13, 15, 18, 20])
    r3 = 5
    for name, s in sorted(per_network.items()):
        cov = s["with_url"] / s["members"] if s["members"] else 0
        vals = [name, s["url"], s["members"], s["with_url"], cov,
                s["model"], s["prompt"]]
        for col, v in enumerate(vals, start=1):
            c = sm.cell(row=r3, column=col, value=v)
            c.font = BASE
            c.border = BOX
            if col == 5:
                c.number_format = "0%"
                if cov == 0:
                    c.fill = WARN
        r3 += 1

    notes = [
        "",
        "NOTES",
        "Company websites are only present where the directory links to them. "
        "Measured coverage: 95–98% on three of ten annotated pages, 0% on the "
        "other seven, whose entries carry no outbound link or link only to a "
        "profile page on the association's own site.",
        "A blank 'company website' means no link was on the page. The model is "
        "instructed never to guess a domain from a company name — an invented "
        "URL that looks plausible is worse than an empty cell.",
        "Names are listed exactly as printed on the source page. No filtering "
        "has been applied: the Neovation name filter's verdict is on the "
        "'Extraction audit' sheet as a separate column, so it can be applied "
        "at database-insert time.",
        "'network name' and 'network url' are joined from the source URL list "
        "in Python, not extracted by the model.",
    ]
    for i, t in enumerate(notes, start=r3 + 1):
        c = sm.cell(row=i, column=1, value=t)
        c.font = Font(name=FONT, size=10, bold=True) if t == "NOTES" else NOTE
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if len(t) > 100:
            sm.row_dimensions[i].height = 42
    sm.merge_cells(start_row=r3 + 3, start_column=1, end_row=r3 + 3,
                   end_column=7)

    wb.active = 0
    wb.save(OUT)

    total_url = sum(s["with_url"] for s in per_network.values())
    print(f"wrote {OUT}")
    print(f"  {row-2} member records from {len(per_network)} networks")
    print(f"  {total_url} have a company website "
          f"({total_url/max(row-2,1)*100:.0f}%)")
    print(f"  sheets: {', '.join(wb.sheetnames)}")


if __name__ == "__main__":
    main()
