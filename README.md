# NeoHub — LLM Member-Company Extraction Pipeline

Bachelor thesis, Giorgi Pataridze (`gpataridze@constructor.university`)
Constructor University Bremen × Neovation GmbH — NeoHub, work package AP1.

---

## 1. What this does, in one paragraph

German industry associations publish lists of their member companies. Those
lists are a useful signal for NeoHub: a company that joins a technical
association is demonstrably engaged with its industry, which makes it a
plausible R&D partner. This project takes 73 such association web pages and
extracts the member company names **using a local language model** instead of
73 hand-written scrapers. It then benchmarks two models — `llama3.1:8b` and
`qwen2.5-coder:7b` — on speed *and* accuracy, to answer whether a model small
enough to run on a laptop is good enough for the job.

Running locally matters: it is free, unlimited, and no company data leaves
the machine.

---

## 2. The pipeline

```
  1 FETCH          2 CLEAN            3 EXTRACT        4 FILTER        5 EVALUATE
  download    →    strip junk    →    ask the LLM  →   Neovation   →   score and
  + cache          from HTML          for names        rulebook        report

  fetcher.py       cleaner.py         extractor.py     neovation_      benchmark.py
                                      prompts.py       filter.py       evaluate.py

  800 KB HTML      3,000 words        ["Bosch GmbH",   ["Bosch",       "Qwen: 24s,
                   plain text          "Siemens AG"]    "Siemens"]      F1 0.91"
```

---

## 3. Setup

Requires Python 3 and [Ollama](https://ollama.com) running locally.

```bash
python3 -m venv .venv
.venv/bin/pip install requests beautifulsoup4 lxml ollama pandas matplotlib
ollama pull qwen2.5-coder:7b
ollama pull llama3.1:8b
```

Check Ollama is up:

```bash
curl -s http://localhost:11434/api/version
```

---

## 4. Running it, in order

### Step 1 — build the URL list *(done)*

```bash
.venv/bin/python build_urls.py
```

Merges the team's two spreadsheets into `data/urls_73.csv`:
59 member-list URLs (Diego) + 14 innovation-club homepages (Yusif) = 73.

### Step 2 — download the pages *(done)*

```bash
.venv/bin/python fetcher.py
```

Downloads all 73 and caches them in `results/html_cache/`. Polite: 2.5 s
between requests, honest User-Agent, retries with backoff, `robots.txt`
recorded. Writes `results/fetch_manifest.csv`.

Re-running is free — cached pages are skipped. Use `--refetch` to force.

### Step 3 — build the answer key *(needs you)*

```bash
.venv/bin/python make_ground_truth.py
```

Generates ten worksheets in `data/ground_truth/`. Each has **Section A**
(likely member companies) and **Section B** (probable page furniture,
ignored). Delete wrong lines from A, rescue anything real from B, and add
members the guesses missed by checking the live page.

When finished:

```bash
.venv/bin/python make_ground_truth.py --check
```

This validates the worksheets and writes the `.json` answer keys the scorer
reads. **Stage A cannot produce accuracy numbers until this is done.**

### Step 4 — Stage A, the ablation

```bash
.venv/bin/python benchmark.py --stage a
```

Every combination of 2 models × 3 prompts × 2 JSON modes, on the 10 labelled
pages, repeated 3×. About 300 runs, ~4 hours. Preview first with `--dry-run`.

Safe to interrupt — progress is saved after every run and re-running the same
command resumes.

### Step 5 — read the results

```bash
.venv/bin/python evaluate.py
```

Prints a ranking and tells you the winning configuration, plus the exact
command to run Stage B.

### Step 6 — Stage B, scale the winner

```bash
.venv/bin/python benchmark.py --stage b --models <winner> --prompt <winner> --json-mode <winner>
```

Runs the best setup across every page that downloaded successfully, producing
the actual company list for the team.

---

## 5. What each file does

### The engine — used on every run

| File | Role |
|---|---|
| `config.py` | Every tunable setting: models, `num_ctx`, the ~70 blacklist terms, timeouts, paths. **Change behaviour here, not in the other files.** |
| `cleaner.py` | HTML → plain text. Strips scripts, menus, cookie banners, images. Splits oversized pages into chunks. |
| `prompts.py` | The three prompt techniques being compared. |
| `extractor.py` | Talks to Ollama. Times the call, captures token counts, repairs malformed JSON. |
| `neovation_filter.py` | Applies the team's rulebook and logs every deletion with its cause. |

### One-time scripts

| File | Role |
|---|---|
| `build_urls.py` | Builds `data/urls_73.csv` from the two spreadsheets. |
| `fetcher.py` | Downloads and caches the 73 pages. |
| `make_ground_truth.py` | Generates labelling worksheets; `--check` converts them to answer keys. |

### The experiment

| File | Role |
|---|---|
| `benchmark.py` | Runs the experiment grid, writes one CSV row per run. |
| `evaluate.py` | Aggregates results into rankings, charts, LaTeX tables and the company list. |

---

## 6. Output files

| Path | Contents |
|---|---|
| `results/html_cache/` | Raw downloaded HTML, one file per URL (named by hash). |
| `results/fetch_manifest.csv` | Per-URL download outcome, size, token estimate, failure reason. |
| `results/benchmark_results.csv` | **The thesis dataset.** One row per run. |
| `results/extractions/*.json` | The actual names each run produced, so results can be re-scored without re-running. |
| `results/extracted_companies.csv` | **The deliverable for Neovation.** Mapped to the UDB schema. |
| `results/filter_impact.txt` | What the filter removed, and its suspected false positives. |
| `results/charts/*.png` | Latency and accuracy charts. |
| `results/results_tables.tex` | LaTeX table for the thesis. |

`extracted_companies.csv` maps onto Rayen's ERD: `company_name_clean` →
`COMPANIES.name`; `source_url` / `source_association` → `SOURCE`;
`captured_at` / `content_hash` → `SOURCE_CAPTURE`.

**It contains every extracted name, unfiltered.** Per Marco (meeting
2026-07-28), filtering happens at database-insert time, not during scraping:
*"the scraping stage will take as much data as possible from the source, but
then we will filter this data before storing them in the database."* The
filter's verdict rides along as columns — `passes_filter`, `blacklist_hit`,
`has_legal_form`, `suspected_false_positive` — so Neovation can apply the rule
with a single `WHERE passes_filter = True`, and can audit what that discards
before committing to it.

---

## 7. Design decisions worth knowing

**Fetching is separate from extraction, and pages are cached.**
Both models must see byte-identical input, or the comparison is invalid. It
also keeps network time out of the latency measurement and avoids hammering
73 real organisations across hundreds of runs.

**`num_ctx` is set explicitly.**
Ollama defaults to a 4,096-token context and **silently discards anything
longer — it never raises an error**. One page here cleans to 53,000 tokens.
Without setting this, the model would read the first fraction of a page,
return a short list, and the whole benchmark would measure a truncation bug.

**Oversized pages are chunked, not truncated.**
Split at ~6,000 tokens on line boundaries with a small overlap; results are
merged and de-duplicated. Latency is summed, so a big page reports its true
total cost.

**The benchmark loops model-outermost.**
The models are 4.7 GB and 4.9 GB and cannot coexist in 16 GB of RAM. Switching
frequently would mean timing disk loads instead of inference.

**Accuracy is scored *before* the filter.**
Ground truth is "what names appear on this page". The filter deliberately
removes valid companies (universities, associations), so scoring after it
would punish the model for the rulebook's choices.

**The legal-form whitelist is recorded but not enforced.**
The rulebook requires every name to contain GmbH/AG/KG/UG. Many directories
print bare brand names — EtherCAT lists thousands of members with almost no
legal forms — so enforcing it would delete entire member lists. The pipeline
records `has_legal_form` per name and reports what enforcement would cost.

**The blacklist uses naive substring matching, faithfully.**
That is what the rulebook specifies, and it has real false positives: `stadt`
removes anything in Darmstadt, `kasse` removes anything in Kassel. Rather than
silently deviating, every removal is logged with its triggering term and
flagged when it looks like a collision, so the error rate is *measured*.

---

## 8. Known data-quality problems

Found while running the fetcher over all 73 URLs:

- **6 dead links** (HTTP 404) in the associations spreadsheet.
- **6 bot-blocked** (HTTP 403).
- **8 JS-rendered shells** — the page returns 200 but the member list loads
  via JavaScript and is absent from the HTML.
- **Several wrong URLs** — pointing at homepages, news feeds, "about us"
  pages or product-category taxonomies rather than member lists. Confirmed
  so far: `014`, `028`, `035`, `044`, `047`, `049`.

Only about 23 of the 73 URLs are genuine member directories. This is worth
raising with the team: a substantial share of the collected links need
re-verification.

---

## 9. Troubleshooting

**`cannot reach Ollama`** — start it: `ollama serve`

**Benchmark seems stuck** — a 12B model on 16 GB swaps heavily and can take
5+ minutes per page. The 7–8B models average ~25–45 s.

**No accuracy scores in the results** — the worksheets are not finished. Run
`make_ground_truth.py --check` and confirm it reports 10/10.

**Want to start the experiment over** — delete `results/benchmark_results.csv`
and `results/extractions/`. The HTML cache and ground truth are unaffected.
