"""
Phase 5 -- turn benchmark_results.csv into thesis material.

benchmark.py produces one row per run. This file aggregates those rows into
the things you actually put in a document:

  1. A console summary ranking every configuration.
  2. Charts (PNG) -- latency by model, F1 by prompt technique.
  3. A LaTeX table you can paste straight into the thesis.
  4. extracted_companies.csv -- the clean deliverable for Neovation, shaped
     to match Rayen's UDB schema (COMPANIES / SOURCE / SOURCE_CAPTURE).

Nothing here re-runs a model. It reads the CSV and the saved extractions, so
it is instant and you can re-run it as often as you like.

USAGE
    .venv/bin/python evaluate.py                 # everything
    .venv/bin/python evaluate.py --stage a       # only the ablation
    .venv/bin/python evaluate.py --no-charts     # skip matplotlib
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict

import config

EXTRACTIONS_DIR = config.RESULTS_DIR / "extractions"
CHARTS_DIR = config.RESULTS_DIR / "charts"
LATEX_PATH = config.RESULTS_DIR / "results_tables.tex"


def load_rows(stage: str | None) -> list[dict]:
    if not config.BENCHMARK_CSV.exists():
        raise SystemExit(f"No results yet at {config.BENCHMARK_CSV}.\n"
                         "Run:  .venv/bin/python benchmark.py --stage a")
    with open(config.BENCHMARK_CSV, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if stage:
        rows = [r for r in rows if r["stage"] == stage]
    return rows


def _f(row: dict, key: str) -> float | None:
    """Read a numeric CSV cell, tolerating blanks (Stage B has no F1)."""
    val = row.get(key, "")
    if val in ("", None):
        return None
    try:
        return float(val)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# 1. Configuration ranking
# --------------------------------------------------------------------------

def summarise(rows: list[dict]) -> list[dict]:
    """
    Group runs by (model, prompt, json_mode) and average them.

    Repetitions collapse into a mean and a standard deviation, so the latency
    figure carries its own uncertainty instead of being a single sample.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (row["model_name"], row["prompt_technique"], row["json_mode"])
        groups[key].append(row)

    out = []
    for (model, prompt, mode), runs in groups.items():
        lat = [v for v in (_f(r, "latency_seconds") for r in runs) if v is not None]
        f1s = [v for v in (_f(r, "f1") for r in runs) if v is not None]
        precs = [v for v in (_f(r, "precision") for r in runs) if v is not None]
        recs = [v for v in (_f(r, "recall") for r in runs) if v is not None]
        tps = [v for v in (_f(r, "tokens_per_second") for r in runs) if v]
        raws = [v for v in (_f(r, "raw_count") for r in runs) if v is not None]

        out.append({
            "model": model, "prompt": prompt, "json_mode": mode,
            "n": len(runs),
            "latency_mean": statistics.mean(lat) if lat else 0.0,
            "latency_sd": statistics.stdev(lat) if len(lat) > 1 else 0.0,
            "tok_per_s": statistics.mean(tps) if tps else 0.0,
            # Average names returned per run -- makes over/under-extraction
            # visible at a glance (multi-stage returns roughly half the rest).
            "names_per_page": statistics.mean(raws) if raws else 0.0,
            "precision": statistics.mean(precs) if precs else None,
            "recall": statistics.mean(recs) if recs else None,
            "f1": statistics.mean(f1s) if f1s else None,
            # How often the model produced JSON that needed rescuing. This is
            # the robustness number that justifies constrained decoding.
            "repair_rate": sum(r["json_repair_used"] == "True" for r in runs) / len(runs),
            "parse_fail_rate": sum(r["json_parse_ok"] != "True" for r in runs) / len(runs),
        })

    # Best F1 first; where F1 is unavailable (Stage B) fall back to speed.
    out.sort(key=lambda d: (-(d["f1"] or -1), d["latency_mean"]))
    return out


def print_summary(summary: list[dict]) -> None:
    print("\n" + "=" * 100)
    print("  CONFIGURATION RANKING" + " " * 12 + "(best F1 first; F1 blank in Stage B)")
    print("=" * 100)
    print(f"  {'model':<20}{'prompt':<17}{'json':<13}{'n':>4}"
          f"{'latency':>12}{'tok/s':>8}{'prec':>7}{'rec':>7}{'F1':>7}{'repair':>8}")
    print("  " + "-" * 96)
    for s in summary:
        lat = f"{s['latency_mean']:.1f}±{s['latency_sd']:.0f}s"
        p = f"{s['precision']:.3f}" if s["precision"] is not None else "  -  "
        r = f"{s['recall']:.3f}" if s["recall"] is not None else "  -  "
        f1 = f"{s['f1']:.3f}" if s["f1"] is not None else "  -  "
        print(f"  {s['model']:<20}{s['prompt']:<17}{s['json_mode']:<13}{s['n']:>4}"
              f"{lat:>12}{s['tok_per_s']:>8.1f}{p:>7}{r:>7}{f1:>7}"
              f"{s['repair_rate']*100:>7.0f}%")

    best = next((s for s in summary if s["f1"] is not None), None)
    if best:
        print(f"\n  WINNER: {best['model']} / {best['prompt']} / {best['json_mode']}")
        print(f"          F1={best['f1']:.3f}  precision={best['precision']:.3f}  "
              f"recall={best['recall']:.3f}  {best['latency_mean']:.1f}s per page")
        print(f"\n  Run Stage B with:\n"
              f"      .venv/bin/python benchmark.py --stage b "
              f"--models {best['model']} --prompt {best['prompt']} "
              f"--json-mode {best['json_mode']}")


# --------------------------------------------------------------------------
# 2. Per-model view (the headline thesis comparison)
# --------------------------------------------------------------------------

def print_model_comparison(rows: list[dict]) -> None:
    by_model: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_model[row["model_name"]].append(row)

    print("\n" + "=" * 100)
    print("  PER-MODEL COMPARISON (averaged over all prompts and JSON modes)")
    print("=" * 100)
    for model, runs in sorted(by_model.items()):
        lat = [v for v in (_f(r, "latency_seconds") for r in runs) if v is not None]
        f1s = [v for v in (_f(r, "f1") for r in runs) if v is not None]
        raw = [v for v in (_f(r, "raw_count") for r in runs) if v is not None]
        errs = sum(1 for r in runs if r["error"])
        print(f"\n  {model}")
        print(f"    runs                {len(runs)}")
        print(f"    latency             {statistics.mean(lat):.1f}s "
              f"(sd {statistics.stdev(lat):.1f})" if len(lat) > 1 else "")
        if f1s:
            print(f"    F1                  {statistics.mean(f1s):.3f}")
        print(f"    companies per page  {statistics.mean(raw):.1f}" if raw else "")
        print(f"    runs with errors    {errs}")


# --------------------------------------------------------------------------
# 3. Charts
# --------------------------------------------------------------------------

def make_charts(summary: list[dict]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")           # no display needed
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n  matplotlib not available -- skipping charts")
        return

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    # Chart 1 -- latency by model, one bar per prompt technique.
    models = sorted({s["model"] for s in summary})
    prompts_ = sorted({s["prompt"] for s in summary})
    width = 0.8 / max(len(prompts_), 1)

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, prompt in enumerate(prompts_):
        xs, ys, errs = [], [], []
        for j, model in enumerate(models):
            match = [s for s in summary if s["model"] == model and s["prompt"] == prompt]
            if not match:
                continue
            xs.append(j + i * width)
            ys.append(statistics.mean(m["latency_mean"] for m in match))
            errs.append(statistics.mean(m["latency_sd"] for m in match))
        ax.bar(xs, ys, width, yerr=errs, capsize=3, label=prompt)

    ax.set_xticks([j + 0.4 - width / 2 for j in range(len(models))])
    ax.set_xticklabels(models, rotation=10)
    ax.set_ylabel("seconds per page")
    ax.set_title("Extraction latency by model and prompt technique")
    ax.legend(title="prompt")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "latency_by_model.png", dpi=150)
    plt.close(fig)

    # Chart 2 -- accuracy, only meaningful where ground truth exists.
    scored = [s for s in summary if s["f1"] is not None]
    if scored:
        fig, ax = plt.subplots(figsize=(9, 5))
        labels = [f"{s['model'].split(':')[0]}\n{s['prompt']}\n{s['json_mode']}"
                  for s in scored]
        x = range(len(scored))
        ax.bar([i - 0.22 for i in x], [s["precision"] for s in scored], 0.22,
               label="precision")
        ax.bar([i for i in x], [s["recall"] for s in scored], 0.22, label="recall")
        ax.bar([i + 0.22 for i in x], [s["f1"] for s in scored], 0.22, label="F1")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=7)
        ax.set_ylim(0, 1)
        ax.set_ylabel("score")
        ax.set_title("Extraction accuracy by configuration")
        ax.legend()
        fig.tight_layout()
        fig.savefig(CHARTS_DIR / "accuracy_by_config.png", dpi=150)
        plt.close(fig)

    print(f"\n  charts -> {CHARTS_DIR}")


# --------------------------------------------------------------------------
# 4. LaTeX table
# --------------------------------------------------------------------------

def write_summary_csv(summary: list[dict]) -> None:
    """
    One row per configuration, ranked best-first.

    This is the table to hand to the team or paste into a spreadsheet --
    benchmark_results.csv is the raw per-run log and is too granular to read.
    """
    path = config.RESULTS_DIR / "stage_a_summary.csv"
    fields = ["rank", "model", "prompt_strategy", "json_mode", "f1",
              "precision", "recall", "latency_mean_s", "latency_sd_s",
              "tokens_per_second", "names_per_page", "json_repair_rate_pct",
              "n_runs"]

    rows = []
    for i, s in enumerate(summary, start=1):
        rows.append({
            "rank": i,
            "model": s["model"],
            "prompt_strategy": s["prompt"],
            "json_mode": s["json_mode"],
            "f1": round(s["f1"], 4) if s["f1"] is not None else "",
            "precision": round(s["precision"], 4) if s["precision"] is not None else "",
            "recall": round(s["recall"], 4) if s["recall"] is not None else "",
            "latency_mean_s": round(s["latency_mean"], 1),
            "latency_sd_s": round(s["latency_sd"], 1),
            "tokens_per_second": round(s["tok_per_s"], 1),
            "names_per_page": round(s["names_per_page"], 1),
            "json_repair_rate_pct": round(s["repair_rate"] * 100),
            "n_runs": s["n"],
        })

    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  summary -> {path}")


def write_latex(summary: list[dict]) -> None:
    lines = [
        r"% Auto-generated by evaluate.py -- do not edit by hand.",
        r"\begin{table}[htbp]", r"\centering",
        r"\caption{Extraction performance by model, prompt technique and JSON mode.}",
        r"\label{tab:extraction-results}",
        r"\begin{tabular}{lllrrrr}", r"\toprule",
        r"Model & Prompt & JSON & Latency (s) & Precision & Recall & F1 \\",
        r"\midrule",
    ]
    for s in summary:
        p = f"{s['precision']:.3f}" if s["precision"] is not None else "--"
        r = f"{s['recall']:.3f}" if s["recall"] is not None else "--"
        f1 = f"{s['f1']:.3f}" if s["f1"] is not None else "--"
        model = s["model"].replace("_", r"\_")
        prompt = s["prompt"].replace("_", r"\_")
        mode = s["json_mode"].replace("_", r"\_")
        lines.append(f"{model} & {prompt} & {mode} & "
                     f"{s['latency_mean']:.1f} $\\pm$ {s['latency_sd']:.1f} & "
                     f"{p} & {r} & {f1} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]

    LATEX_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"  latex  -> {LATEX_PATH}")


# --------------------------------------------------------------------------
# 5. The deliverable for Neovation
# --------------------------------------------------------------------------

def write_companies(rows: list[dict]) -> None:
    """
    Emit the extracted company list, shaped for Rayen's UDB schema.

    IMPORTANT -- this ships EVERY extracted name, not the filtered subset.

    Per Marco (meeting 2026-07-28): "the scraping stage will take as much data
    as possible from the source, but then we will filter this data before
    storing them in the database." The Neovation filter is a load-time concern,
    not a scrape-time one, so removing names here would destroy data the team
    expects to receive.

    Instead the filter's verdict travels alongside each name as columns:
    passes_filter / blacklist_hit / has_legal_form / suspected_false_positive.
    Neovation can apply the rule at insert time with a single WHERE clause,
    and can audit what it would discard before committing to it.

    Columns map onto the ERD: company_name -> COMPANIES.name, source_url and
    source_association -> SOURCE, captured_at and content_hash ->
    SOURCE_CAPTURE.
    """
    import fetcher   # local import: only needed for the cache hash

    # Prefer Stage B (full corpus); fall back to Stage A if B has not run.
    stage_rows = [r for r in rows if r["stage"] == "b"] or rows
    if not stage_rows:
        return

    best_by_url: dict[str, dict] = {}
    for row in stage_rows:
        # If a URL was run more than once, keep the run that extracted the most.
        prev = best_by_url.get(row["url_id"])
        if prev is None or int(row["raw_count"] or 0) > int(prev["raw_count"] or 0):
            best_by_url[row["url_id"]] = row

    out_rows = []
    for row in best_by_url.values():
        path = EXTRACTIONS_DIR / f"{row['run_id']}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        cache = fetcher.cache_path(row["url"])
        content_hash = cache.stem if cache.exists() else ""

        # The audit log holds one entry per extracted name with the filter's
        # verdict already attached, so we can ship everything and annotate it.
        for d in data.get("audit", []):
            if d["reason"] == "duplicate":
                continue        # same name twice on one page is noise, not data
            out_rows.append({
                "company_name_raw": d["original"],
                "company_name_clean": d["cleaned"] or d["original"],
                "source_association": row["org_name"],
                "source_url": row["url"],
                "source_kind": "association_member_list",
                "captured_at": row["timestamp"],
                "content_hash": content_hash,
                "extracted_by_model": row["model_name"],
                "prompt_technique": row["prompt_technique"],
                # --- Neovation filter verdict, for use at DB-insert time ---
                "passes_filter": d["kept"],
                "blacklist_hit": d["blacklist_hit"],
                "has_legal_form": d["has_legal_form"],
                "suspected_false_positive": d["suspected_false_positive"],
            })

    fields = ["company_name_raw", "company_name_clean", "source_association",
              "source_url", "source_kind", "captured_at", "content_hash",
              "extracted_by_model", "prompt_technique", "passes_filter",
              "blacklist_hit", "has_legal_form", "suspected_false_positive"]
    with open(config.COMPANIES_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    unique = len({r["company_name_clean"].casefold() for r in out_rows})
    passing = sum(1 for r in out_rows if r["passes_filter"])
    print(f"\n  companies -> {config.COMPANIES_CSV}")
    print(f"              {len(out_rows)} rows (ALL extracted, unfiltered), "
          f"{unique} unique, {len(best_by_url)} sources")
    print(f"              {passing} would pass the Neovation filter "
          f"({len(out_rows)-passing} flagged for removal at insert time)")



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["a", "b"], default=None)
    ap.add_argument("--no-charts", action="store_true")
    args = ap.parse_args()

    rows = load_rows(args.stage)
    print(f"  loaded {len(rows)} runs from {config.BENCHMARK_CSV.name}")

    summary = summarise(rows)
    print_summary(summary)
    print_model_comparison(rows)

    if not args.no_charts:
        make_charts(summary)
    write_summary_csv(summary)
    write_latex(summary)
    write_companies(rows)
    print()


if __name__ == "__main__":
    main()
