"""
Build the deliverable workbook in the layout Hendro specified (2026-08-06).

Two sheets:

    Network members   company name | company website | website source |
                      network name | network url | street | postcode | city |
                      phone | email
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
import pathlib
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import config
import fetcher
from link_coverage import host_of, websites_on_page

OUT = config.RESULTS_DIR / "NeoHub_Network_Members.xlsx"
EXTRACTIONS = config.RESULTS_DIR / "extractions"
RESULTS_CSV = config.BENCHMARK_CSV


def use_run(results_csv: str) -> None:
    """Build the workbook from one grid rather than the shared file."""
    global EXTRACTIONS, RESULTS_CSV
    RESULTS_CSV = pathlib.Path(results_csv).resolve()
    folder = RESULTS_CSV.parent / "extractions"
    if folder.is_dir():
        EXTRACTIONS = folder

# The names-arm winner (section 3.13, F1 0.981). It is the better source of
# NAMES than the full-record run (F1 0.858), and on long pages much better:
# on automotive thüringen the full-record run returned 72 of 124 members in
# all three repetitions without raising any error, and on SPECTARIS it
# returned nothing usable, while this run found 123 and 295 respectively.
NAMES_CONFIG = ("llama3.1:8b", "zero_shot", "prompt_only")

# A full-record run that returns fewer companies than this share of the
# names-only run on the same page has stopped early. 80% leaves room for the
# two runs disagreeing on a handful of borderline entries, and is far above
# the 58% that went unnoticed on automotive thüringen.
INCOMPLETE_RATIO = 0.8


def run_rank(row: dict) -> tuple:
    """
    Which of two runs of the same page to keep: clean first, then fuller.

    An errored run is not worthless. A multi-chunk page whose last chunk
    failed to parse still returned every company from the chunks that
    worked, and discarding it drops the whole network from the deliverable
    rather than the part that failed.

    Measured on the production run: page p094, the eco Verband der
    Internetwirtschaft, returned 162 companies and then failed on one chunk.
    Excluding it gave 15,940 members instead of 16,102, and left that
    network absent from Neovation's sheet entirely.

    A clean run still wins over a partial one for the same page, however
    many more companies the partial one claims, because a run that failed
    mid-way may have stopped before the end of the page.
    """
    try:
        found = int(row.get("raw_count") or 0)
    except (TypeError, ValueError):
        found = 0
    return (not row.get("error"), found)

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


def load_searched() -> dict[str, tuple[str, str]]:
    """
    {company name -> (website, how it was found)} from stage 4.

    Only `verified` and `domain_match` are loaded. `page_only` results are
    excluded deliberately: the page names the company but the domain does not
    resemble it, which is the signature of a directory entry rather than the
    company's own site (section 3.13l). Loading those would put plausible
    wrong addresses into the database, which is the one failure this pipeline
    is built to avoid.
    """
    path = config.RESULTS_DIR / "searched_websites.csv"
    if not path.exists():
        return {}
    import benchmark
    out: dict[str, tuple[str, str]] = {}
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r["status"] in ("verified", "domain_match") and r["found_url"]:
                out[benchmark.match_key(r["company"])] = (r["found_url"],
                                                          f"search ({r['status']})")
    return out


def load_profiles() -> dict:
    """
    {company name -> record} from stage 3, the profile-page fetch.

    Richer than the other two sources: a profile page carries the street,
    postcode, city, phone and email as well as the website, and those are the
    fields the directory listings almost never print. Only websites verified
    against the fetched page are used, on the same rule as everywhere else.
    """
    path = config.RESULTS_DIR / "profile_records.csv"
    if not path.exists():
        return {}
    import benchmark
    out = {}
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r.get("error"):
                continue
            out[benchmark.match_key(r["company"])] = r
    return out


# Where a network came from. Neovation reports the publicly funded ZIM
# networks separately from the privately funded ones (Marco, 2026-09-24), so
# the split has to travel with every row rather than be rebuilt by hand.
FINALV1 = ("NEOHUB_final_merged_QA_reviewed (1)(Finalv1).csv")
SOURCE_LABELS = {
    "Private_funded_innovation_clubs_FINAL_200": "Private funded",
    "Deutsche_technische_Verbaende_erweitert": "Technical association",
}


def load_source_dataset() -> dict:
    """{host -> "ZIM network" | "Private funded"} from the Finalv1 sheet."""
    path = config.THESIS_WORK / FINALV1
    out: dict = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            dataset = (r.get("Source dataset") or "").strip()
            if not dataset:
                continue
            for column in ("Companies / members URL",
                           "Verified / corrected network URL",
                           "Network homepage / exact hosted page"):
                url = (r.get(column) or "").strip()
                if url.startswith("http"):
                    out.setdefault(host_of(url), dataset)
    return out


def dataset_for(net_url: str, source_file: str, lookup: dict) -> str:
    """The funding source of one network, blank never: "unknown" is a value."""
    return (lookup.get(host_of(net_url))
            or SOURCE_LABELS.get(source_file, "")
            or "unknown")


def merge_page(full: list[dict], names: list[str],
               page_sites: dict[str, str]) -> tuple[list[dict], dict]:
    """
    Combine one page's full-record run with its names-only run.

    The full-record run supplies the website and contact fields; the
    names-only run supplies the companies the full-record run never reached.
    Asking for seven fields per company makes the model stop partway down a
    long page, and it does so silently: automotive thüringen lost 53 of 124
    members in every repetition with no error raised anywhere.

    Websites, in order of evidence:
      1. the address the model returned with the record
      2. the address the page itself pairs with that name (`page_sites`),
         for records returned without one and for every added name
    An added name with no pairing on the page stays blank. No address is ever
    guessed from a name.

    Returns (entries, stats). Each entry is a record dict with its website in
    "url" and where that came from in "_source". stats["incomplete"] is the
    warning that was missing: True when the full-record run returned fewer
    than INCOMPLETE_RATIO of the companies the names-only run found.
    """
    import benchmark
    entries: list[dict] = []
    seen: set[str] = set()

    full_keys = set()
    for rec in full:
        name = (rec.get("name") or "").strip()
        key = benchmark.match_key(name)
        if not key:
            continue
        full_keys.add(key)
        if key in seen:
            continue
        seen.add(key)
        rec = dict(rec, name=name)
        site = (rec.get("url") or "").strip()
        source = "directory page" if site else ""
        if not site and page_sites.get(key):
            site, source = page_sites[key], "directory page (paired)"
        rec["url"], rec["_source"] = site, source
        entries.append(rec)

    names_keys = set()
    added = 0
    for name in names:
        name = (name or "").strip()
        key = benchmark.match_key(name)
        if not key:
            continue
        names_keys.add(key)
        if key in seen:
            continue
        seen.add(key)
        added += 1
        site = page_sites.get(key, "")
        entries.append({"name": name, "url": site,
                        "_source": "directory page (paired)" if site else ""})

    incomplete = bool(names_keys) and len(full_keys) < INCOMPLETE_RATIO * len(names_keys)
    return entries, {"full": len(full_keys), "names": len(names_keys),
                     "added": added, "incomplete": incomplete}


def load(stage: str | None, model: str | None = None,
         prompt: str | None = None, json_mode: str | None = None):
    """
    Return one run per URL, with its extracted records.

    Without a configuration filter this keeps whichever run returned the most
    rows per page, which is the wrong thing for a deliverable: volume is not
    accuracy, and the most prolific run on a page may come from a model that
    fabricates. The 960-run study settled which configuration to ship
    (llama3.1:8b + few_shot_full_record + prompt_only, section 3.13j), so the
    deliverable should be built from that one and say so.
    """
    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}
    with open(RESULTS_CSV, encoding="utf-8") as fh:
        runs = list(csv.DictReader(fh))
    if stage:
        runs = [r for r in runs if r["stage"] == stage]
    if model:
        runs = [r for r in runs if r["model_name"] == model]
    if prompt:
        runs = [r for r in runs if r["prompt_technique"] == prompt]
    if json_mode:
        runs = [r for r in runs if r["json_mode"] == json_mode]
    # A run that errored is NOT discarded outright. A multi-chunk page whose
    # last chunk failed to parse still returned every company from the chunks
    # that worked, and dropping it removes the whole network from the
    # deliverable rather than the part that failed.
    #
    # Measured on the production run: page p094 (eco Verband der
    # Internetwirtschaft) returned 162 companies and then failed on one
    # chunk. Excluding it cost 162 of 16,102 members, and more to the point
    # it meant one network appeared nowhere in Neovation's sheet.
    #
    # A clean run still wins over an errored one for the same page, and
    # between two of the same kind the one that found more companies wins.
    best: dict[str, dict] = {}
    for r in runs:
        if not int(r["raw_count"] or 0):
            continue                      # nothing to contribute
        prev = best.get(r["url_id"])
        if prev is None or run_rank(r) > run_rank(prev):
            best[r["url_id"]] = r
    partial = sum(1 for r in best.values() if r.get("error"))
    if partial:
        print(f"  {partial} page(s) contribute a partial extraction "
              f"(a chunk failed, the rest is kept)")

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
    ap.add_argument("--results", default=None,
                    help="results CSV of one run; its sibling extractions/ folder is used")
    ap.add_argument("--stage", choices=["a", "b"], default=None)
    ap.add_argument("--model", default="llama3.1:8b")
    ap.add_argument("--prompt", default="few_shot_full_record")
    ap.add_argument("--json-mode", default="prompt_only")
    ap.add_argument("--names-model", default=NAMES_CONFIG[0],
                    help="model of the names-only run, e.g. a cloud model")
    ap.add_argument("--any-config", action="store_true",
                    help="ignore the configuration filter and keep whichever "
                         "run returned most rows per page")
    args = ap.parse_args()
    if args.results:
        use_run(args.results)
    names_config = (args.names_model,) + NAMES_CONFIG[1:]

    if args.any_config:
        records = load(args.stage)
        chosen = "best-by-volume across all configurations"
        names_records = []
    else:
        records = load(args.stage, args.model, args.prompt, args.json_mode)
        chosen = f"{args.model} / {args.prompt} / {args.json_mode}"
        names_records = load(args.stage, *names_config)
    full_runs = {run["url_id"]: (u, run, d) for u, run, d in records}
    names_runs = {run["url_id"]: (u, run, d) for u, run, d in names_records}
    searched = load_searched()
    profiles = load_profiles()
    datasets = load_source_dataset()
    print(f"  full-record run: {chosen}")
    if names_runs:
        print(f"  names-only run:  {' / '.join(names_config)}")
    print(f"  pages: {len(set(full_runs) | set(names_runs))} "
          f"({len(full_runs)} with a usable full-record run)")
    print(f"  stage 3 profile records available: {len(profiles)}")
    print(f"  stage 4 websites available to merge: {len(searched)}")
    if not full_runs and not names_runs:
        raise SystemExit("no extractions found -- run benchmark.py first")

    import benchmark
    wb = Workbook()

    # ---------------- Sheet 1: Network members -----------------------------
    ws = wb.active
    ws.title = "Network members"
    # Hendro's four columns first, so the sheet still opens the way he
    # specified; the disambiguation fields Marco and Yusif asked for follow.
    # "website source" is not decoration. A website read off the directory
    # page and one found by a later web search carry different confidence, and
    # Neovation should be able to tell them apart before acting on a record.
    labels = ["company name", "company website", "website source",
              "network name", "network url", "source dataset", "street",
              "postcode", "city", "phone", "email"]
    header(ws, 1, labels, [46, 38, 22, 32, 38, 18, 30, 10, 20, 20, 30])

    pages = []
    for uid in set(full_runs) | set(names_runs):
        url_row, run, _ = full_runs.get(uid) or names_runs[uid]
        pages.append((url_row.get("org_name", run["org_name"]), uid))

    row = 2
    per_network: dict[str, dict] = {}
    for network, uid in sorted(pages):
        url_row, run, _ = full_runs.get(uid) or names_runs[uid]
        net_url = url_row.get("url", run["url"])
        dataset = dataset_for(net_url, url_row.get("source_file", ""), datasets)

        full = (full_runs[uid][2].get("records") or []) if uid in full_runs else []
        nd = names_runs[uid][2] if uid in names_runs else {}
        names = ([r.get("name", "") for r in nd.get("records") or []]
                 or list(nd.get("raw") or []))

        page_sites: dict[str, str] = {}
        cache = fetcher.cache_path(net_url)
        if cache.exists():
            html = cache.read_text(encoding="utf-8", errors="ignore")
            page_sites = websites_on_page(
                html, net_url, names + [r.get("name") or "" for r in full])

        entries, st = merge_page(full, names, page_sites)
        if st["incomplete"]:
            print(f"  WARN  {uid} {network[:38]}: the full-record run returned "
                  f"{st['full']} of the {st['names']} companies the names-only "
                  f"run found; {st['added']} added from the names-only run")

        kept = with_url = from_search = from_profile = 0
        for rec in entries:
            name = rec["name"]
            kept += 1
            key = benchmark.match_key(name)
            prof = profiles.get(key, {})
            site, source = rec["url"], rec["_source"]

            # Website: the directory page first, then the profile page, then
            # the search. Earlier sources are cheaper and better evidenced.
            if not site and prof.get("company_url") and prof.get("url_on_page") == "yes":
                site, source = prof["company_url"], "profile page"
                from_profile += 1
            if not site:
                hit = searched.get(key)
                if hit:
                    site, source = hit
                    from_search += 1
            if site:
                with_url += 1

            # Contact fields: whatever the directory gave, else the profile
            # page. A directory listing rarely prints an address; a profile
            # page carries one about 90% of the time.
            def field(k):
                return ((rec.get(k) or "").strip()
                        or (prof.get(k) or "").strip())

            values = [name, site, source, network, net_url, dataset,
                      field("street"), field("postcode"), field("city"),
                      field("phone"), field("email")]
            for col, val in enumerate(values, start=1):
                c = ws.cell(row=row, column=col, value=val)
                c.font = BASE
                c.border = BOX
                c.alignment = Alignment(wrap_text=(col in (1, 4)),
                                        vertical="top")
                if row % 2 == 0:
                    c.fill = ALT
            row += 1

        per_network[network] = {
            "url": net_url, "dataset": dataset, "members": kept, "with_url": with_url,
            "from_search": from_search, "from_profile": from_profile,
            "full": st["full"], "names": st["names"], "added": st["added"],
            "check": "full-record run incomplete" if st["incomplete"] else "ok",
        }

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(labels))}{max(row-1, 2)}"

    # ---------------- Sheet 2: Summary -------------------------------------
    sm = wb.create_sheet("Summary")
    sm["A1"] = "NeoHub, network member extraction"
    sm["A1"].font = TITLE
    runs_used = f"full-record run {chosen}"
    if names_runs:
        runs_used += f" · names-only run {' / '.join(names_config)}"
    sm["A2"] = (f"Generated {datetime.now():%Y-%m-%d %H:%M} · "
                f"{row-2} member records from {len(per_network)} networks · "
                f"{runs_used}")
    sm["A2"].font = NOTE

    header(sm, 4, ["network name", "network url", "source dataset", "members",
                   "with website", "website coverage", "full-record run found",
                   "names-only run found", "added from names-only run",
                   "check"],
           [34, 42, 18, 11, 13, 15, 15, 15, 17, 24])
    r3 = 5
    for name, s in sorted(per_network.items()):
        cov = s["with_url"] / s["members"] if s["members"] else 0
        vals = [name, s["url"], s["dataset"], s["members"], s["with_url"], cov,
                s["full"], s["names"], s["added"], s["check"]]
        for col, v in enumerate(vals, start=1):
            c = sm.cell(row=r3, column=col, value=v)
            c.font = BASE
            c.border = BOX
            if col == 6:
                c.number_format = "0%"
                if cov == 0:
                    c.fill = WARN
            if col == 10 and s["check"] != "ok":
                c.fill = WARN
        r3 += 1

    notes = [
        "",
        "NOTES",
        "Each page is read twice: once for full records (name, "
        "website, address, phone, email) and once for names only. On long "
        "pages the full-record read stops partway down the list without any "
        "error, so companies found only by the names-only read are added. "
        "'check' marks pages where the full-record read returned fewer than "
        f"{INCOMPLETE_RATIO:.0%} of the names-only read.",
        "'website source' says where each website came from: 'directory page' "
        "is the model reading the network's page; 'directory page (paired)' is "
        "the same page with the name matched to its link in code, without a "
        "model; 'profile page' is the member's page on the network's own site; "
        "'search' is a web search whose result was checked against the name.",
        "A blank 'company website' means none of these found one. No address "
        "is ever guessed from a company name: a plausible wrong address is "
        "worse than an empty cell.",
        "Names are listed exactly as printed on the source page. No filtering "
        "has been applied; Neovation's company-name rulebook is applied at "
        "database-insert time.",
        "'network name', 'network url' and 'source dataset' are joined from "
        "the source lists in Python, not extracted by the model. 'source "
        "dataset' separates the publicly funded ZIM networks from the "
        "privately funded ones and from the technical associations.",
    ]
    for i, t in enumerate(notes, start=r3 + 1):
        c = sm.cell(row=i, column=1, value=t)
        c.font = Font(name=FONT, size=10, bold=True) if t == "NOTES" else NOTE
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if len(t) > 100:
            sm.merge_cells(start_row=i, start_column=1, end_row=i, end_column=10)
            sm.row_dimensions[i].height = 44

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
