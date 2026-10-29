"""
Phase 4 -- the experiment runner.

This is the file that actually produces your thesis data. It takes the cached
pages, runs them through every combination of (model x prompt x JSON mode),
records how long each took and how accurate it was, and appends one row per
run to results/benchmark_results.csv.

--------------------------------------------------------------------------
THE TWO STAGES
--------------------------------------------------------------------------
Running every combination over all 73 pages would take 15-25 hours. Instead
we use the standard experimental pattern: ablate small, then scale the winner.

  STAGE A  "which setup is best?"
           Every combination, but only on the 10 hand-labelled pages.
           Because we know the right answers there, we can compute accuracy
           (precision / recall / F1), not just speed. Repeated 3x so the
           latency figure has a mean and a standard deviation behind it.
           ~300 runs, roughly 4 hours.

  STAGE B  "how does the winner do at scale?"
           Take the best configuration from Stage A and run it across every
           usable page. No accuracy here (no labels), but it produces the
           actual company list your team wants.
           ~100 runs, roughly 1.5 hours.

--------------------------------------------------------------------------
THREE THINGS IN HERE THAT ARE EASY TO GET WRONG
--------------------------------------------------------------------------
1. MODEL-OUTERMOST LOOPING.
   The three models are 4.7 GB, 4.9 GB and 7.6 GB and cannot sit in 16 GB of
   RAM together. If the loop switched models often, Ollama would evict and
   reload from disk every time -- and you would be timing disk I/O, not
   inference. So the outermost loop is the model: everything for one model
   finishes before the next is loaded.

2. RESUMABILITY.
   A four-hour run will get interrupted -- a closed lid, a Ctrl-C, a crash.
   Every completed run is appended to the CSV immediately and flushed to
   disk. On startup we read back what is already there and skip it. Stopping
   and restarting therefore costs you nothing.

3. EXTRACTION IS UNFILTERED.
   Every extracted name is reported as the model returned it. Neovation
   applies their company-name rulebook at database-insert time (Marco,
   2026-07-28), so filtering here would discard data the team expects to
   receive and would penalise the model for a downstream rule.

--------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------
    .venv/bin/python benchmark.py --stage a              # the ablation
    .venv/bin/python benchmark.py --stage a --dry-run    # just show the plan
    .venv/bin/python benchmark.py --stage b              # scale the winner
    .venv/bin/python benchmark.py --stage b --model gemma4:12b --only-best
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
import unicodedata
from datetime import datetime, timezone

import ollama

import check_completeness
import cleaner
import config
import extractor
import fetcher
import prompts

# One row of benchmark_results.csv. Kept explicit (rather than derived) so the
# column order in the thesis appendix is stable and readable.
CSV_FIELDS = [
    "run_id", "timestamp", "stage", "repetition",
    "url_id", "org_name", "url",
    "model_name", "prompt_technique", "json_mode",
    "est_input_tokens", "n_chunks", "page_completeness",
    "latency_seconds", "prompt_eval_count", "eval_count", "tokens_per_second",
    "json_parse_ok", "json_repair_used",
    "raw_count",
    "true_positives", "false_positives", "false_negatives",
    "precision", "recall", "f1",
    # URL arm only; blank for the name-only guideline strategies.
    "url_returned", "url_verified", "url_hallucinated",
    "url_coverage", "url_fidelity",
    "error",
]

# Where this run writes. --run puts both the CSV and the extraction files in
# results/runs/<name>/, so a grid never appends to an older study's file and a
# re-score always knows which runs produced which numbers. Without --run the
# old shared paths are used, so existing commands keep working.
RESULTS_CSV = config.BENCHMARK_CSV
EXTRACTIONS_DIR = config.RESULTS_DIR / "extractions"


def use_run_folder(name: str) -> None:
    """Point this process at results/runs/<name>/ for output."""
    global RESULTS_CSV, EXTRACTIONS_DIR
    folder = config.RESULTS_DIR / "runs" / name
    folder.mkdir(parents=True, exist_ok=True)
    RESULTS_CSV = folder / "benchmark_results.csv"
    EXTRACTIONS_DIR = folder / "extractions"
    EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# Name matching for accuracy scoring
# --------------------------------------------------------------------------

# Legal forms stripped before comparing names, longest first so
# "GmbH & Co. KG" wins over a bare "KG". This is a SCORING concern: the page
# may print "Siemens AG" where the model returns "Siemens", and that is not a
# mistake. Nothing here filters anything out.
LEGAL_SUFFIXES = [
    "Gesellschaft mit beschränkter Haftung",
    "GmbH & Co. KGaA", "GmbH & Co. KG", "GmbH & Co KG",
    "AG & Co. KG", "AG & Co KG", "SE & Co. KG", "SE & Co KG",
    "SE & Co. KGaA", "GmbH & Co. OHG", "& Co. KG", "& Co KG",
    "Unternehmensgesellschaft (haftungsbeschränkt)",
    "UG (haftungsbeschränkt)",
    "Aktiengesellschaft", "Gesellschaft mbH",
    "GmbH", "mbH", "AG", "KGaA", "KG", "UG", "OG", "SE", "e.K.",
]


def strip_legal_suffix(name: str) -> str:
    """Remove trailing legal forms so two spellings of one company match."""
    out = name.strip().rstrip(",;.")
    out = re.sub(r"(?i)\bCo\.\s*(KG|KGaA|OHG)\b", r"Co. \1", out)
    changed = True
    while changed:
        changed = False
        for suffix in LEGAL_SUFFIXES:
            # Short forms need a separator, or the trailing "ag" of "2mag AG"
            # is itself treated as a legal form and the name becomes "2m".
            sep = r"[\s,\-]+" if len(suffix) <= 3 else r"[\s,\-]*"
            new = re.sub(rf"{sep}{re.escape(suffix)}\.?\s*$", "", out,
                         flags=re.IGNORECASE)
            if new != out and new.strip():
                out = new.strip().rstrip(",;.-&")
                changed = True
                break
    return out.strip()


def match_key(name: str) -> str:
    """
    Reduce a company name to a form that can be compared fairly.

    The model may print "Siemens AG" where the page says "Siemens", or differ
    in punctuation and capitalisation. None of that is a real mistake, so we
    strip the legal suffix, drop accents and punctuation, and casefold before
    comparing. Without this the scores would measure formatting, not accuracy.
    """
    base = strip_legal_suffix(cleaner.strip_invisible(name))
    text = unicodedata.normalize("NFKD", base.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    # German directories print the same firm as "Spitzen & Stickereien",
    # "Spitzen und Stickereien" and "Kaelte- u. Klimatechnik", sometimes twice
    # on one page (KliWaTex, 2026-09-24). Scored literally, a model copying
    # the other spelling takes both a miss and a false alarm for one company.
    # The joining word carries no identity, so it is dropped on both sides.
    text = " ".join(w for w in text.split() if w not in ("und", "u", "and"))
    return re.sub(r"\s+", " ", text).strip()


def score(predicted: list[str], truth: list[str]) -> dict:
    """
    Compare what the model found against the hand-labelled answer key.

      true positive  -- a real member the model found
      false positive -- something the model returned that is not on the page
                        (this is where hallucination shows up)
      false negative -- a real member the model missed

      precision = TP / (TP + FP)   "of what it returned, how much was real?"
      recall    = TP / (TP + FN)   "of what was there, how much did it find?"
      F1        = harmonic mean, so a model must do BOTH to score well
    """
    pred = {match_key(p) for p in predicted if match_key(p)}
    gold = {match_key(t) for t in truth if match_key(t)}

    tp = len(pred & gold)
    fp = len(pred - gold)
    fn = len(gold - pred)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "true_positives": tp, "false_positives": fp, "false_negatives": fn,
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


# --------------------------------------------------------------------------
# URL scoring
# --------------------------------------------------------------------------

def _url_core(url: str) -> str:
    """
    Reduce a URL to the part worth comparing: host plus path, lowercased,
    without scheme, 'www.', trailing slash or query string.

    The model reformats what it copies -- 'http://www.2mag.de' comes back as
    'https://2mag.de' often enough that a literal string comparison would
    report hallucinations that are not hallucinations.
    """
    u = url.strip().lower()
    for prefix in ("https://", "http://", "//"):
        if u.startswith(prefix):
            u = u[len(prefix):]
            break
    u = u.split("?")[0].split("#")[0]
    if u.startswith("www."):
        u = u[4:]
    return u.rstrip("/")


def score_urls(records: list[dict], page_text: str) -> dict:
    """
    Check returned company websites against the page they came from.

    This needs no hand annotation, which is the reason the URL arm can run on
    the existing ten-page ground truth (§3.13b). Every URL the model can
    legitimately return was written into the page text by annotate_links(),
    so a URL that is not in that text was not read off the page -- the model
    constructed it from the company name. That is the failure mode that
    matters: a plausible-looking wrong domain enters the database silently,
    whereas a blank cell is visibly a job for the resolution pipeline.

      url_coverage  -- of the companies found, how many came back with a URL
      url_fidelity  -- of the URLs returned, how many are actually on the page

    Fidelity is the accuracy measure. Coverage is a property of the page as
    much as of the model, since a directory that prints no links caps it.
    """
    haystack = page_text.lower()
    returned = verified = 0

    for rec in records:
        url = (rec.get("url") or "").strip()
        if not url:
            continue
        returned += 1
        core = _url_core(url)
        # A bare domain is enough to confirm the model read it rather than
        # invented it; requiring the full path would fail on trailing-slash
        # and scheme differences that carry no meaning.
        host = core.split("/")[0]
        if host and host in haystack:
            verified += 1

    hallucinated = returned - verified
    return {
        "url_returned": returned,
        "url_verified": verified,
        "url_hallucinated": hallucinated,
        "url_coverage": round(returned / len(records), 4) if records else 0.0,
        "url_fidelity": round(verified / returned, 4) if returned else "",
    }


# --------------------------------------------------------------------------
# Loading inputs
# --------------------------------------------------------------------------

def load_pages(stage: str) -> list[dict]:
    """
    Return the pages this stage should run on, with their cleaned text.

    Stage A uses only the hand-labelled sample (we need answer keys).
    Stage B uses every page that downloaded successfully.
    """
    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}
    with open(config.FETCH_MANIFEST_CSV, encoding="utf-8") as fh:
        manifest = {r["id"]: r for r in csv.DictReader(fh)}

    if stage == "a":
        import make_ground_truth
        wanted = make_ground_truth.SAMPLE_IDS
    else:
        wanted = [i for i, m in manifest.items() if m["status"] == "ok"]

    pages = []
    for uid in wanted:
        row, man = urls[uid], manifest.get(uid, {})
        path = fetcher.cache_path(row["url"])
        if not path.exists():
            print(f"  ! no cached HTML for {uid} ({row['org_name'][:40]}) -- skipping")
            continue

        page = cleaner.process(path.read_text(encoding="utf-8", errors="ignore"),
                               row["url"])

        truth = None
        gt_file = config.GROUND_TRUTH_DIR / f"{uid}.json"
        if gt_file.exists():
            truth = json.loads(gt_file.read_text(encoding="utf-8"))["companies"]
        # A Stage A run on a page without an answer key produces rows with no
        # score, and the resume logic would then skip that run forever, even
        # after the page is labelled. Unlabelled pages are left out instead.
        if stage == "a" and truth is None:
            print(f"  ! no answer key yet for {uid} ({row['org_name'][:40]}) -- skipping")
            continue

        # Alphabet coverage of the member initials, computed once per page.
        # A complete directory spans most of the alphabet; a page showing only
        # the first slice of a paginated list clusters on a single letter.
        # Recorded per run so that a suspicious result can be traced back to a
        # truncated source page without re-deriving anything.
        raw_html = path.read_text(encoding="utf-8", errors="ignore")
        completeness = check_completeness.analyse(raw_html)["verdict"]

        pages.append({
            "id": uid, "org_name": row["org_name"], "url": row["url"],
            "page": page, "truth": truth,
            "est_tokens": man.get("est_tokens", page.est_tokens),
            "completeness": completeness,
        })

    return pages


def build_plan(stage: str, models: list[str], pages: list[dict],
               prompt_only: str | None = None,
               json_mode_only: str | None = None,
               arm: str = "guideline", reps_override: int | None = None,
               interleave: bool = False) -> list[dict]:
    """
    Enumerate every run to perform, ordered MODEL-OUTERMOST.

    All three guideline strategies (P1 zero-shot, P2 few-shot, P3 generic
    multi-stage) emit pure JSON, so every strategy runs under both JSON
    modes. The INCOMPATIBLE_WITH_CONSTRAINED skip is retained for any future
    strategy that emits prose alongside its JSON.
    """
    strategies = [prompt_only] if prompt_only else list(prompts.ARMS[arm])
    modes = [json_mode_only] if json_mode_only else config.JSON_MODES
    # Repetitions are NOT redundant, despite temperature 0 and a fixed seed.
    # 22 of the 180 configurations in the original GPU grid disagreed across
    # identical repetitions: GPU floating-point reductions are not bit-stable,
    # and a near-tied token occasionally flips. The rate rises with how close
    # a model runs to its context limit (qwen 3%, llama 10%, gemma4 23%).
    # The override exists for quick checks, not for production runs.
    reps = reps_override or (config.STAGE_A_REPETITIONS if stage == "a"
                             else config.STAGE_B_REPETITIONS)

    plan = []
    for model in models:                       # outermost: load each model once
        for strategy in strategies:
            for mode in modes:
                if (mode == "constrained"
                        and strategy in prompts.INCOMPATIBLE_WITH_CONSTRAINED):
                    continue
                for page in pages:
                    for rep in range(1, reps + 1):
                        plan.append({
                            "stage": stage, "model": model, "strategy": strategy,
                            "json_mode": mode, "page": page, "repetition": rep,
                        })
    if interleave and len(models) > 1:
        plan = _round_robin_by_model(plan, models)
    return plan


def _round_robin_by_model(plan: list[dict], models: list[str]) -> list[dict]:
    """
    Rotate between models instead of finishing one before starting the next.

    Only safe, and only useful, for hosted models. Locally the loop must stay
    model-outermost because three models do not fit in 16 GB at once, and
    swapping per run would time a reload as extraction.

    It matters because a hosted endpoint's latency moves with load. Measured
    on the first cloud grid: claude-haiku ran 31.8 s per run in the first half
    of its session and 53.2 s in the second, a 67% drift on one model in one
    afternoon. The two models were also benchmarked five days apart, so the
    latency comparison between them was confounded by whenever each happened
    to run. Interleaving puts every model under the same conditions.

    Resume is unaffected: completed runs are keyed on their fields, not on
    their position in the plan.
    """
    from itertools import zip_longest
    order = {m: i for i, m in enumerate(models)}
    buckets: list[list[dict]] = [[] for _ in models]
    for item in plan:
        buckets[order[item["model"]]].append(item)
    return [item for row in zip_longest(*buckets) for item in row
            if item is not None]


def _migrate_csv(old_header: list[str]) -> None:
    """
    Rewrite the results file so its header matches CSV_FIELDS.

    Columns are only ever added, never reordered or removed, so an old row can
    be brought forward by inserting an empty value wherever a new column sits.
    Nothing is discarded, and the previous file is kept alongside in case the
    migration itself is wrong.
    """
    backup = RESULTS_CSV.with_name(
        RESULTS_CSV.stem + "_premigration.csv")
    if not backup.exists():
        backup.write_bytes(RESULTS_CSV.read_bytes())

    with open(RESULTS_CSV, encoding="utf-8") as fh:
        rows = list(csv.reader(fh))[1:]

    added = [c for c in CSV_FIELDS if c not in old_header]
    migrated = []
    for row in rows:
        if len(row) == len(CSV_FIELDS):
            migrated.append(row)                      # already current
        elif len(row) == len(old_header):
            byname = dict(zip(old_header, row))
            migrated.append([byname.get(c, "") for c in CSV_FIELDS])
        # Anything else is a partial write from an interrupted run; dropping it
        # is correct, since the run will simply be repeated.

    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_FIELDS)
        writer.writerows(migrated)

    print(f"  ! added column(s): {', '.join(added) or 'none'}")
    print(f"  ! migrated {len(migrated)} rows, previous file kept as "
          f"{backup.name}\n")


def run_key(item: dict) -> str:
    """Stable identifier used to skip work already done on a previous run."""
    return "|".join([
        item["stage"], item["model"], item["strategy"], item["json_mode"],
        item["page"]["id"], str(item["repetition"]),
    ])


def load_completed() -> set[str]:
    """Read the results CSV so an interrupted run can pick up where it left off."""
    if not RESULTS_CSV.exists():
        return set()
    done = set()
    with open(RESULTS_CSV, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            # Only completed rows count; failures are retried.
            if row.get("error"):
                continue
            done.add("|".join([
                row["stage"], row["model_name"], row["prompt_technique"],
                row["json_mode"], row["url_id"], row["repetition"],
            ]))
    return done


# --------------------------------------------------------------------------
# Executing one run
# --------------------------------------------------------------------------

def execute(item: dict) -> dict:
    """Run one (page, model, prompt, json mode) combination and build its CSV row."""
    page_info = item["page"]
    page = page_info["page"]

    result = extractor.extract(
        chunks=page.chunks, model=item["model"],
        strategy=item["strategy"], json_mode=item["json_mode"],
    )

    row = {
        "run_id": f"{int(time.time() * 1000)}",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": item["stage"], "repetition": item["repetition"],
        "url_id": page_info["id"], "org_name": page_info["org_name"],
        "url": page_info["url"],
        "model_name": item["model"], "prompt_technique": item["strategy"],
        "json_mode": item["json_mode"],
        "est_input_tokens": page_info["est_tokens"],
        "n_chunks": page.n_chunks,
        "page_completeness": page_info["completeness"],
        "latency_seconds": result.latency_seconds,
        "prompt_eval_count": result.prompt_eval_count,
        "eval_count": result.eval_count,
        "tokens_per_second": result.tokens_per_second,
        "json_parse_ok": result.json_parse_ok,
        "json_repair_used": result.json_repair_used,
        "raw_count": len(result.companies),
        "true_positives": "", "false_positives": "", "false_negatives": "",
        "precision": "", "recall": "", "f1": "",
        "url_returned": "", "url_verified": "", "url_hallucinated": "",
        "url_coverage": "", "url_fidelity": "",
        "error": result.error,
    }

    if page_info["truth"] is not None:
        row.update(score(result.companies, page_info["truth"]))

    # Names are scored identically for every strategy, so the URL arm stays
    # directly comparable with the guideline arm on the metric RQ1 asks about.
    # The URL columns are additional, not a replacement.
    if item["strategy"] in prompts.RECORD_STRATEGIES:
        row.update(score_urls(result.records, page.text))

    # Keep the actual names so the run can be re-scored later without
    # spending another four hours of compute on it.
    (EXTRACTIONS_DIR / f"{row['run_id']}.json").write_text(json.dumps({
        "key": run_key(item),
        "raw": result.companies,
        # Structured records for the record-returning strategies; same order
        # as `raw`. Empty for name-only strategies.
        "records": result.records,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    return row


def preflight(models: list[str]) -> bool:
    """Fail fast on the obvious problems rather than four hours in."""
    import cloud_client
    cloud = [m for m in models if cloud_client.is_cloud(m)]
    local = [m for m in models if not cloud_client.is_cloud(m)]
    if cloud and cloud_client.missing_settings():
        print(f"  ERROR: {', '.join(cloud)} need the environment variable(s) "
              f"{', '.join(cloud_client.missing_settings())}")
        return False
    if not local:
        return True

    try:
        available = {m.model for m in ollama.list().models}
    except Exception as exc:
        print(f"  ERROR: cannot reach Ollama ({exc}).")
        print("  Start it with:  ollama serve")
        return False

    missing = [m for m in local if m not in available]
    if missing:
        print(f"  ERROR: model(s) not installed: {', '.join(missing)}")
        print(f"  Available: {', '.join(sorted(available))}")
        return False
    return True


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="NeoHub extraction benchmark")
    ap.add_argument("--stage", choices=["a", "b"], required=True)
    ap.add_argument("--models", nargs="+", default=config.MODELS)
    ap.add_argument("--prompt", default=None, help="restrict to one strategy")
    ap.add_argument("--arm", default="guideline", choices=list(prompts.ARMS),
                    help="guideline = P1/P2/P3, names only (default); "
                         "url = the name+website strategies; all = both")
    ap.add_argument("--json-mode", default=None, choices=config.JSON_MODES)
    ap.add_argument("--dry-run", action="store_true", help="show the plan only")
    ap.add_argument("--limit", type=int, default=None, help="stop after N runs")
    ap.add_argument("--pages", nargs="+", default=None,
                    help="restrict to these url_ids, e.g. --pages 043 050")
    ap.add_argument("--run", default=None,
                    help="write this grid to results/runs/<name>/ instead of "
                         "appending to the shared results file")
    ap.add_argument("--interleave", action="store_true",
                    help="rotate between models instead of finishing one "
                         "before the next. For HOSTED models only: it makes "
                         "the latency comparison fair when an endpoint's "
                         "speed drifts with load. Never use it with local "
                         "models, which would reload on every run.")
    ap.add_argument("--reps", type=int, default=None,
                    help="override repetitions. Note that output is NOT fully "
                         "deterministic even at temperature 0 (12%% of grid "
                         "cells varied), so 1 is for quick checks only")
    args = ap.parse_args()
    if args.run:
        use_run_folder(args.run)
    else:
        EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)

    if not preflight(args.models):
        sys.exit(1)

    pages = load_pages(args.stage)
    if args.pages:
        wanted = set(args.pages)
        pages = [p for p in pages if p["id"] in wanted]
        if not pages:
            print(f"  ERROR: none of {sorted(wanted)} are loadable pages.")
            return
    if not pages:
        print("  No pages to run. Did fetcher.py complete?")
        sys.exit(1)

    if args.stage == "a":
        unlabelled = [p["id"] for p in pages if p["truth"] is None]
        if unlabelled:
            print(f"  WARNING: no ground truth for {', '.join(unlabelled)}.")
            print("  Finish the worksheets and run:")
            print("      .venv/bin/python make_ground_truth.py --check")
            print("  Continuing, but those runs will have no accuracy scores.\n")

    plan = build_plan(args.stage, args.models, pages, args.prompt,
                      args.json_mode, args.arm, args.reps,
                      interleave=args.interleave)
    done = load_completed()
    todo = [i for i in plan if run_key(i) not in done]

    # Count what the CSV already covers BEFORE --limit trims the queue,
    # otherwise the summary claims everything is finished.
    already_done = len(plan) - len(todo)
    if args.limit:
        todo = todo[: args.limit]

    # 45 s/run is the measured warm average for the 7-8B models on this corpus.
    est_min = len(todo) * 45 / 60
    print(f"  stage:      {args.stage.upper()}")
    print(f"  models:     {', '.join(args.models)}")
    print(f"  pages:      {len(pages)}")
    print(f"  planned:    {len(plan)} runs")
    print(f"  already done: {already_done}")
    print(f"  to run:     {len(todo)}  (~{est_min/60:.1f} h at 45 s/run)")
    print()

    if args.dry_run or not todo:
        return

    # Appending to a file whose header predates a change to CSV_FIELDS writes
    # rows wider than the header, and every column after the insertion point
    # then reads back shifted by one. That happened when the five URL columns
    # were added, and it is silent: the run looks fine and the data is wrong.
    # Check the header on disk and migrate rather than trusting it.
    is_new = not RESULTS_CSV.exists()
    if not is_new:
        with open(RESULTS_CSV, encoding="utf-8") as check:
            existing = next(csv.reader(check), [])
        if existing and existing != CSV_FIELDS:
            print(f"  ! results header has {len(existing)} columns, code expects "
                  f"{len(CSV_FIELDS)}")
            print(f"  ! migrating {RESULTS_CSV.name} before appending")
            _migrate_csv(existing)

    fh = open(RESULTS_CSV, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
    if is_new:
        writer.writeheader()

    started = time.time()
    latencies: list[float] = []
    current_model = None

    try:
        for n, item in enumerate(todo, start=1):
            if item["model"] != current_model:
                current_model = item["model"]
                print(f"\n  === loading {current_model} ===")

            row = execute(item)
            writer.writerow(row)
            fh.flush()      # survive a crash: never lose completed work

            latencies.append(row["latency_seconds"])
            elapsed = time.time() - started
            remaining = (elapsed / n) * (len(todo) - n)

            f1 = f"F1={row['f1']}" if row["f1"] != "" else ""
            warn = " !" if row["error"] else ""
            print(f"  [{n:>4}/{len(todo)}] {item['strategy']:<16}"
                  f"{item['json_mode']:<13}{item['page']['id']} "
                  f"{row['latency_seconds']:>7.1f}s "
                  f"raw={row['raw_count']:<4} {f1:<10}"
                  f"eta {remaining/60:>5.0f}m{warn}")

    except KeyboardInterrupt:
        print("\n  Interrupted. Progress is saved -- re-run the same command "
              "to continue where you stopped.")
    finally:
        fh.close()

    if latencies:
        print(f"\n  {len(latencies)} runs in {(time.time()-started)/60:.1f} min")
        print(f"  latency mean {statistics.mean(latencies):.1f}s", end="")
        if len(latencies) > 1:
            print(f"  stdev {statistics.stdev(latencies):.1f}s", end="")
        print(f"\n  results -> {RESULTS_CSV}")
        print(f"  next:    .venv/bin/python evaluate.py")


if __name__ == "__main__":
    main()
