"""
Paired significance tests behind Table 5 of the thesis.

Reproduces the model comparison and the decomposition comparison from the raw
benchmark CSV, so the reported p-values have code behind them rather than a
note written months earlier.

Method
------
Each configuration yields one F1 per page (averaged over repetitions), so a
comparison between two configurations is paired by page. Under the null that
the configuration label carries no information, the sign of each per-page
difference is exchangeable. Reversing those signs at random and recomputing
the mean gives the distribution chance alone would produce.

    p (two-sided) = (#{|mean of flipped diffs| >= |observed mean|} + 1)
                    / (n_resamples + 1)

The +1 is the Phipson and Smyth correction: a permutation p-value of exactly
zero is not attainable, and reporting one overstates the evidence.

Intervals are paired bootstrap percentile intervals over the same per-page
differences.

Families of related comparisons are corrected by Holm's step-down procedure.
The decomposition comparison answers a separate question and is not pooled
into the model family, so it is reported uncorrected.

Aggregation
-----------
Row deduplication copies `make_report.py:dedupe` exactly. Resuming a grid
appends rather than rewriting, so the CSV holds both an original error row and
the retry that fixed it. One row survives per
(stage, model, prompt, json_mode, url_id, repetition): a clean answer always
beats an error row, and otherwise the later timestamp wins. A configuration
with no clean answer keeps its error row, because there the failure is the
result.

Usage
-----
    python significance.py [path/to/run_dir]

Default run dir is the 30-page names arm under Thesis_Final.
"""

from __future__ import annotations

import collections
import csv
import pathlib
import statistics
import sys

import numpy as np

SEED = 424242
N_RESAMPLES = 20_000
ALPHA = 0.05

DEFAULT_RUN_DIR = (
    pathlib.Path(__file__).resolve().parents[2]
    / "Thesis_Final/deliverables/01_research_30pages/runs/names_arm"
)

# Published values, for verification. Mean differences and F1 are deterministic
# and must match exactly. p-values and interval bounds depend on the random
# draw, so they are compared loosely.
PUBLISHED_F1 = {
    ("qwen3.5:9b", "zero_shot"): 0.9622,
    ("llama3.1:8b", "few_shot_schema"): 0.9466,
    ("qwen2.5-coder:7b", "zero_shot"): 0.9091,
}
PUBLISHED_DIFFS = {
    ("qwen3.5:9b", "qwen2.5-coder:7b"): 0.0530,
    ("llama3.1:8b", "qwen2.5-coder:7b"): 0.0375,
    ("qwen3.5:9b", "llama3.1:8b"): 0.0155,
}
PUBLISHED_P = {
    ("qwen3.5:9b", "qwen2.5-coder:7b"): 0.0128,
    ("llama3.1:8b", "qwen2.5-coder:7b"): 0.0369,
    ("qwen3.5:9b", "llama3.1:8b"): 0.1657,
}


# --------------------------------------------------------------------------
# loading, matching make_report.py
# --------------------------------------------------------------------------

def run_key(r: dict) -> tuple:
    return (r["stage"], r["model_name"], r["prompt_technique"],
            r["json_mode"], r["url_id"], r["repetition"])


def dedupe(rows: list[dict]) -> list[dict]:
    """One row per configuration. Copies make_report.py:dedupe."""
    def better(a: dict, b: dict) -> bool:
        if bool(a["error"]) != bool(b["error"]):
            return not a["error"]
        return a["timestamp"] >= b["timestamp"]

    best: dict = {}
    for r in rows:
        k = run_key(r)
        if k not in best or better(r, best[k]):
            best[k] = r
    return list(best.values())


def load(run_dir: pathlib.Path) -> list[dict]:
    path = run_dir / "benchmark_results.csv"
    if not path.exists():
        raise SystemExit(f"no results at {path}")
    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    before = len(rows)
    rows = dedupe(rows)
    print(f"  {before} rows -> {len(rows)} configurations "
          f"({before - len(rows)} superseded by retries)")
    return rows


def per_page_f1(rows: list[dict]) -> dict[tuple, dict[str, float]]:
    """{(model, prompt, json_mode): {url_id: mean F1 over repetitions}}"""
    acc: dict = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        cfg = (r["model_name"], r["prompt_technique"], r["json_mode"])
        acc[cfg][r["url_id"]].append(float(r["f1"]))
    return {cfg: {u: statistics.mean(v) for u, v in pages.items()}
            for cfg, pages in acc.items()}


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------

def paired_diffs(a: dict[str, float], b: dict[str, float]) -> np.ndarray:
    """Per-page differences a - b, over pages present in both."""
    shared = sorted(set(a) & set(b))
    return np.array([a[u] - b[u] for u in shared], dtype=float)


def permutation_p(diffs: np.ndarray, rng: np.random.Generator,
                  n: int = N_RESAMPLES) -> float:
    """Two-sided paired sign-flip permutation p-value."""
    observed = abs(diffs.mean())
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n, diffs.size))
    means = np.abs((signs * diffs).mean(axis=1))
    return (int(np.sum(means >= observed - 1e-12)) + 1) / (n + 1)


def exact_permutation_p(diffs: np.ndarray, max_bits: int = 20) -> float | None:
    """
    Exact two-sided paired sign-flip p-value by full enumeration.

    Pages whose difference is exactly zero are unaffected by a sign flip, so
    only the non-zero differences need enumerating. With 17 of them there are
    2^17 = 131,072 sign patterns, which is cheap to evaluate in full. The
    result carries no Monte Carlo error at all.

    Returns None when there are too many non-zero differences to enumerate.
    """
    nz = diffs[diffs != 0.0]
    n = nz.size
    if n == 0 or n > max_bits:
        return None
    total = 1 << n
    bits = ((np.arange(total, dtype=np.uint32)[:, None]
             >> np.arange(n, dtype=np.uint32)) & 1).astype(np.int8)
    sums = (1 - 2 * bits) @ nz           # 0 -> +1, 1 -> -1
    observed = abs(float(nz.sum()))
    return float(np.sum(np.abs(sums) >= observed - 1e-12) / total)


def bootstrap_ci(diffs: np.ndarray, rng: np.random.Generator,
                 n: int = N_RESAMPLES) -> tuple[float, float]:
    """Paired bootstrap percentile interval on the mean difference."""
    idx = rng.integers(0, diffs.size, size=(n, diffs.size))
    means = diffs[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def holm(pvals: list[float]) -> list[float]:
    """
    Holm step-down adjusted p-values, returned in the input order.

    Sort ascending, multiply the i-th smallest by (m - i), enforce a running
    maximum so the sequence never decreases, and cap at 1.
    """
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adjusted[i] = min(1.0, running)
    return adjusted


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def main() -> None:
    run_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RUN_DIR
    print(f"run dir: {run_dir}")
    rows = load(run_dir)
    f1 = per_page_f1(rows)

    print("\n=== F1 per network, all configurations ===")
    ranked = sorted(
        ((statistics.mean(p.values()), len(p), cfg) for cfg, p in f1.items()),
        reverse=True,
    )
    for mean, n, cfg in ranked:
        print(f"  {mean:.4f}  n={n:2d}  {cfg[0]:18s} {cfg[1]:20s} {cfg[2]}")

    # best configuration per model, by F1 per network
    best: dict[str, tuple] = {}
    for mean, _n, cfg in ranked:
        best.setdefault(cfg[0], (cfg, mean))

    print("\n=== best configuration per model ===")
    ok = True
    for model, (cfg, mean) in best.items():
        want = PUBLISHED_F1.get((model, cfg[1]))
        if want is None:
            mark = "  <-- prompt differs from the published best"
            ok = False
        elif abs(mean - want) < 5e-5:
            mark = f"  matches published {want}"
        else:
            mark = f"  MISMATCH, published {want}"
            ok = False
        print(f"  {model:18s} {cfg[1]:20s} {cfg[2]:12s} {mean:.4f}{mark}")

    rng = np.random.default_rng(SEED)

    # --- family of three pairwise model comparisons ------------------------
    order = [m for _mean, _n, (m, _p, _j) in ranked if m in best]
    seen, models = set(), []
    for m in order:
        if m not in seen:
            seen.add(m)
            models.append(m)

    pairs = [(models[0], models[2]), (models[1], models[2]), (models[0], models[1])]
    results = []
    for hi, lo in pairs:
        d = paired_diffs(f1[best[hi][0]], f1[best[lo][0]])
        results.append({
            "hi": hi, "lo": lo, "n": d.size, "diff": d.mean(),
            "ties": int(np.sum(d == 0.0)),
            "p": permutation_p(d, rng),
            "exact": exact_permutation_p(d),
            "ci": bootstrap_ci(d, rng),
        })

    for r, adj in zip(results, holm([r["p"] for r in results])):
        r["holm"] = adj
    if all(r["exact"] is not None for r in results):
        for r, adj in zip(results, holm([r["exact"] for r in results])):
            r["holm_exact"] = adj

    print(f"\n=== paired permutation tests, {N_RESAMPLES:,} sign flips, "
          f"seed {SEED} ===")
    hdr = f"  {'comparison':42s} {'diff':>9s} {'p':>8s} {'Holm p':>8s}  95% CI"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in results:
        lo_, hi_ = r["ci"]
        print(f"  {r['hi'] + ' vs ' + r['lo']:42s} "
              f"{r['diff']:+9.4f} {r['p']:8.4f} {r['holm']:8.4f}  "
              f"[{lo_:+.3f}, {hi_:+.3f}]")

    if all("holm_exact" in r for r in results):
        print(f"\n=== exact tests, full enumeration, no sampling error ===")
        hdr2 = (f"  {'comparison':42s} {'diff':>9s} {'exact p':>8s} "
                f"{'Holm p':>8s}  patterns")
        print(hdr2)
        print("  " + "-" * (len(hdr2) - 2))
        for r in results:
            nz = r["n"] - r["ties"]
            print(f"  {r['hi'] + ' vs ' + r['lo']:42s} "
                  f"{r['diff']:+9.4f} {r['exact']:8.4f} {r['holm_exact']:8.4f}"
                  f"  2^{nz} = {1 << nz:,}")

    print("\n  verification against the published table")
    for r in results:
        key = (r["hi"], r["lo"])
        wd, wp = PUBLISHED_DIFFS.get(key), PUBLISHED_P.get(key)
        if wd is None:
            print(f"    {r['hi']} vs {r['lo']}: not in the published table")
            ok = False
            continue
        dmark = "exact" if abs(r["diff"] - wd) < 5e-5 else f"MISMATCH vs {wd}"
        # The table reports exact p-values, so these must match to the digit.
        if r["exact"] is not None:
            pmark = ("exact" if abs(r["exact"] - wp) < 5e-5
                     else f"MISMATCH vs {wp}")
        else:
            se = (wp * (1 - wp) / N_RESAMPLES) ** 0.5
            pmark = ("within noise" if abs(r["p"] - wp) < 3 * se
                     else f"OUTSIDE noise vs {wp}")
        if "MISMATCH" in dmark or "MISMATCH" in pmark or "OUTSIDE" in pmark:
            ok = False
        print(f"    {r['hi']:18s} vs {r['lo']:18s}  "
              f"diff {dmark:18s}  p {pmark}")

    # --- decomposition, reported uncorrected -------------------------------
    print("\n=== decomposition, qwen3.5 zero-shot vs multi-stage ===")
    lead = models[0]
    zs = best[lead][0]
    ms_candidates = [cfg for cfg in f1
                     if cfg[0] == lead and cfg[1] == "generic_multi_stage"]
    if ms_candidates:
        ms = max(ms_candidates, key=lambda c: statistics.mean(f1[c].values()))
        d = paired_diffs(f1[zs], f1[ms])
        p = permutation_p(d, rng)
        ex = exact_permutation_p(d)
        lo_, hi_ = bootstrap_ci(d, rng)
        nz = int(np.sum(d != 0.0))
        print(f"  {zs[1]}/{zs[2]} vs {ms[1]}/{ms[2]}, n={d.size}, "
              f"{nz} untied")
        print(f"  mean difference {d.mean():+.4f}, p = {p:.4f}, "
              f"95% CI [{lo_:+.3f}, {hi_:+.3f}]")
        if ex is not None:
            print(f"  exact p = {ex:.4f} over 2^{nz} = {1 << nz:,} patterns")
        print(f"  published: +0.0595, exact p = 0.0038, [+0.010, +0.130]")
        print("  not Holm corrected: separate question from the model family")
    else:
        print("  no multi-stage configuration found")

    print("\n=== LaTeX rows for tab:sig ===")
    short = {"qwen3.5:9b": r"\texttt{qwen3.5}",
             "llama3.1:8b": r"\texttt{llama3.1}",
             "qwen2.5-coder:7b": r"\texttt{coder}"}
    for r in results:
        lo_, hi_ = r["ci"]
        p = r["exact"] if r["exact"] is not None else r["p"]
        hp = r.get("holm_exact", r["holm"])
        print(f"        {short.get(r['hi'], r['hi'])} vs "
              f"{short.get(r['lo'], r['lo'])} & ${r['diff']:+.4f}$ & "
              f"{p:.4f} & {hp:.4f} & "
              f"$[{lo_:+.3f}, {hi_:+.3f}]$ \\\\")

    ties = results[-1]["ties"]
    print(f"\nties in the top comparison: {ties} of {results[-1]['n']} pages "
          f"score identically, leaving {results[-1]['n'] - ties} informative "
          f"pairs")
    print("\nRESULT:", "reproduces the published table"
          if ok else "DOES NOT fully reproduce, see mismatches above")


if __name__ == "__main__":
    main()
