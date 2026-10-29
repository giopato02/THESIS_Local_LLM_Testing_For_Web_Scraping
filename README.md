# NeoHub: local-LLM extraction of company information from innovation networks

Bachelor thesis, Giorgi Pataridze (`gpataridze@constructor.university`)
Constructor University Bremen x Neovation GmbH, NeoHub, work package AP1.
Supervised by Prof. Hendro Wicaksono.

**Comparative Evaluation of Local LLM Models and Generic Prompt Strategies for
Extracting Company Information from Innovation Network Websites**

---

## 1. What this does

German industry associations and innovation networks publish lists of their
member companies. Those lists are a useful signal for NeoHub: a company that
joins a technical association is demonstrably engaged with its industry, which
makes it a plausible R&D partner.

This project extracts member company names, websites and contact details from
those directories using local language models instead of one hand-written
scraper per site. Every site is laid out differently, so a generic prompt-based
extractor is the thing being tested.

The study compares **three local models** and **three prompting strategies**,
scored against hand-labelled ground truth:

| Model | Size | Result |
|---|---|---|
| `llama3.1:8b` | 4.9 GB | Best overall, F1 0.981 |
| `qwen2.5-coder:7b` | 4.7 GB | Code-specialised; strong precision, weaker recall |
| `gemma4:12b` | 7.6 GB | Largest, and the negative result: failed 118 of 180 runs. **Retired on 2026-09-15** as too slow for the 30-page run; its 10-page results stay in the thesis |
| `qwen3.5:9b` | 6.6 GB | Replaces gemma4 from 2026-09-15. Same size class as the other two, thinking mode switched off. Results pending |

The research questions are about **which model and which prompt** do this job
best, and what that costs in time and reliability. Parameter count turned out
to predict neither speed nor quality: the 12B model placed last on every
strategy and was also the slowest.

Running locally matters: it is free, unlimited, reproducible, and no data
leaves the machine.

---

## 2. The pipeline

```
  1 FETCH           2 CLEAN             3 EXTRACT          4 EVALUATE
  download     ->   strip junk,    ->   ask the model  ->  score against
  + cache           keep links          for JSON           ground truth

  fetcher.py        cleaner.py          extractor.py       benchmark.py
  paginate.py                           prompts.py         evaluate.py
  browser_fetcher.py

  800 KB HTML       4,200 words         [{"name": "2mag    "llama3.1 zero-shot
                    with <url>           AG", "url":        F1 0.981, 26 s"
                    markers inline       "..."}]
```

Names are reported exactly as extracted. **No filtering is applied.** Neovation
applies their company-name rulebook at database-insert time (Marco, meeting
2026-07-28), so filtering here would discard data the team expects to receive
and would penalise the model for a downstream rule.

---

## 3. Prompt strategies

Selected with `benchmark.py --arm`:

| arm | strategies | returns |
|---|---|---|
| `guideline` | `zero_shot`, `few_shot_schema`, `generic_multi_stage` | names only |
| `url` | `zero_shot_full_record`, `few_shot_full_record`, `multi_stage_full_record` | name + website + street + postcode + city + phone + email |
| `url_ablation` | `few_shot_with_url` | name + website only |

The `guideline` arm is P1/P2/P3 from the supervisor's structure guideline and
answers RQ1 to RQ3. The `url` arm mirrors it one-for-one, so the two are
directly comparable and the question "does the ranking survive asking for a
website?" can be answered per strategy rather than only in aggregate.

Each strategy runs under two **JSON modes**:

- `prompt_only`: the prompt asks for JSON, and a repair layer fixes markdown
  fences or trailing prose. How often repair is needed is itself a result.
- `constrained`: the schema is handed to Ollama, which restricts sampling so
  only schema-valid output is possible.

---

## 4. Setup

Requires Python 3.9+ and [Ollama](https://ollama.com).

```bash
python3 -m venv .venv
.venv/bin/pip install requests beautifulsoup4 lxml ollama pandas \
    matplotlib openpyxl python-docx ddgs

ollama pull llama3.1:8b
ollama pull qwen2.5-coder:7b
ollama pull qwen3.5:9b          # ~16 GB for all three (gemma4:12b is retired)
```

`gpu_setup.sh` does all of this on a fresh GPU node and is safe to re-run:
completed runs are skipped, so an interrupted grid resumes where it stopped.

Two traps worth knowing:

- **`ddgs` needs Python 3.9+.** On an older interpreter the whole `pip install`
  line aborts and nothing gets installed. Drop it if the search route is not
  needed.
- **Verify Ollama is on the GPU before trusting any timing.** It falls back to
  CPU silently, which looks like a working run producing useless numbers.
  `ollama ps` must report `100% GPU`.

---

## 5. Running it

### Build the URL list and download the pages

```bash
.venv/bin/python build_urls.py      # -> data/urls_73.csv
.venv/bin/python fetcher.py         # -> results/html_cache/
```

Polite: 2.5 s between requests, honest User-Agent, retries with backoff.
Re-running is free; cached pages are skipped.

Paginated directories need more than one fetch:

```bash
.venv/bin/python paginate.py         # ?letter=A-Z, numbered pages, 0-50 ranges
.venv/bin/python browser_fetcher.py  # JavaScript-rendered lists
```

### Build the answer key

```bash
.venv/bin/python make_ground_truth.py          # writes worksheets
.venv/bin/python make_ground_truth.py --check  # validates -> .json answer keys
```

Each worksheet has Section A (likely members) and Section B (probable page
furniture). Delete wrong lines from A, rescue anything real from B, and add
members the guesses missed. **Accuracy cannot be scored until this is done.**

Current ground truth: **761 companies across 10 pages.**

### Run the benchmark

`config.MODELS` holds the three current models, so the default grid is
complete. Naming them explicitly does the same thing:

```bash
.venv/bin/python benchmark.py --stage a --arm guideline \
    --models llama3.1:8b qwen2.5-coder:7b qwen3.5:9b
```

Useful flags: `--dry-run` (show the plan), `--pages 043 050` (restrict pages),
`--prompt <name>` (one strategy), `--json-mode`, `--limit`.

Repetitions default to 3, and should stay there. Temperature 0 with a fixed
seed is **not** sufficient for reproducibility on GPU: 22 of the 180
configurations in the original grid returned different results across
identical repetitions (3% of qwen cells, 10% of llama, 23% of gemma4).
`--reps 1` exists for quick checks and costs you the ability to detect that.

Safe to interrupt. Progress is saved after every run and re-running the same
command resumes.

### Cloud models through the Constructor Model API

Any model name starting with `constructor/` is sent to the Constructor Model
API instead of Ollama (`cloud_client.py`). Prompts, cleaning, chunking and
scoring are unchanged, so cloud and local results compare directly. Nothing
runs on the local GPU, so this works from a laptop.

```bash
export CONSTRUCTOR_API_KEY=...          # Model > API Keys in Constructor Learn
.venv/bin/python constructor_setup.py km       # prints the knowledge model ID
export CONSTRUCTOR_KM_ID=...
.venv/bin/python constructor_setup.py models   # model names you can use
.venv/bin/python check_model.py constructor/gemini-3.6-flash
.venv/bin/python benchmark.py --stage a --arm guideline \
    --models constructor/gemini-3.6-flash --json-mode prompt_only
```

Measured quirks (2026-09-15): every answer arrives twice and the client
removes the exact copy; token counts are always 0; schema-constrained output
works for OpenAI models only, so use `--json-mode prompt_only` for the rest.
Never put the key in code or in git.

### Read the results

```bash
.venv/bin/python evaluate.py           # rankings, charts, LaTeX tables
.venv/bin/python dump_extractions.py   # raw per-company output, CSV + xlsx
.venv/bin/python export_deliverable.py # the workbook Neovation receives
```

---

## 6. What each file does

### The engine, used on every run

| File | Role |
|---|---|
| `config.py` | Every tunable setting: models, `num_ctx`, temperature, seed, chunking, JSON schemas, paths. Change behaviour here. |
| `cleaner.py` | HTML to plain text. Strips scripts and menus, and writes outbound link URLs inline as `Name <https://url>` so the model can return a website. |
| `prompts.py` | All prompt strategies, grouped into arms. |
| `extractor.py` | Talks to Ollama. Times calls, captures token counts, repairs malformed JSON, drives the multi-stage strategies. |
| `benchmark.py` | Runs the experiment grid, scores it, writes one CSV row per run. |

### Data acquisition

| File | Role |
|---|---|
| `build_urls.py` | Builds `data/urls_73.csv` from the team's spreadsheets. |
| `fetcher.py` | Downloads and caches pages. |
| `paginate.py` | Follows URL-based pagination so the whole member list is captured, not page one. |
| `browser_fetcher.py` | Headless-browser fetching for JavaScript-rendered lists. |
| `proxy_fetch.py` | Retries 403-blocked pages through rotating proxies. |
| `find_member_pages.py` | Turns a network homepage into a member-list URL. |
| `survey_finalv1.py` | Health-checks all 291 verified URLs in the Finalv1 sheet. |
| `url_health.py` | Shareable report of which collected URLs actually work. |

### Ground truth and inspection

| File | Role |
|---|---|
| `make_ground_truth.py` | Generates labelling worksheets; `--check` converts them to answer keys. |
| `tidy_worksheets.py` | Removes name+location duplicates from worksheets. |
| `check_completeness.py` | Detects truncated member lists via alphabet coverage. |
| `show_page.py` | Prints the cleaned text of a cached page, exactly what the model receives. |

### Output

| File | Role |
|---|---|
| `evaluate.py` | Aggregates results into rankings, charts and LaTeX tables. |
| `dump_extractions.py` | Flattens every run's raw output into one inspectable CSV and workbook. |
| `make_xlsx.py` | Formatted workbook of the Stage A run. |
| `export_deliverable.py` | The deliverable workbook in the layout Hendro specified. |
| `check_model.py` | One-request check of a model before a grid: GPU placement, thinking off, speed. |
| `cloud_client.py` | Sends `constructor/...` models to the Constructor Model API instead of Ollama. |
| `constructor_setup.py` | Lists the cloud models and finds or creates the knowledge model. |
| `make_documentation.py` | Work-package documentation in Neovation's template. |

---

## 7. Output files

| Path | Contents |
|---|---|
| `results/benchmark_results.csv` | **The thesis dataset.** One row per run: timing, token counts, precision/recall/F1, URL metrics. |
| `results/extractions/*.json` | The raw text every model returned, one file per run, so the grid can be re-scored without re-running it. |
| `results/extractions_long.csv` | Every extracted company as its own row, with which model, strategy and JSON mode produced it. |
| `results/extractions_review.xlsx` | The same data plus agreement and field-coverage sheets. |
| `results/html_cache/` | The exact pages the benchmark ran against. Tracked deliberately: these sites change, so without this snapshot the numbers cannot be reproduced. |
| `data/ground_truth/*.json` | Hand-labelled member lists, 761 companies across 10 pages. |
| `results/NeoHub_Network_Members.xlsx` | **The deliverable for Neovation.** |
| `results/stage_a_gpu.log` | Full log of the 540-run GPU grid. |

---

## 8. Design decisions worth knowing

**Fetching is separate from extraction, and pages are cached.**
Every model must see byte-identical input or the comparison is invalid. It also
keeps network time out of the latency measurement and avoids hammering real
organisations across hundreds of runs.

**`num_ctx` is set explicitly.**
Ollama defaults to a 4,096-token context and **silently discards anything
longer, it never raises an error**. One page here cleans to 53,000 tokens.
Without setting this the model reads the first fraction of a page, returns a
short list, and the benchmark measures a truncation bug. This affected 24 of
53 pages before it was found.

**Oversized pages are chunked, not truncated.**
Split at ~6,000 tokens on line boundaries with a small overlap; results are
merged and de-duplicated. Latency is summed, so a big page reports its true
cost.

**The benchmark loops model-outermost.**
The models cannot coexist in 16 GB of RAM. Switching frequently would time
disk loads instead of inference.

**Link markup is preserved before text extraction.**
`get_text()` discards `href` attributes, so without this the model cannot
return a website at all. Preserving links also improved *name* recall from
0.723 to 0.997 on a densely formatted page, because a trailing URL acts as a
record delimiter between otherwise identical-looking lines.

**Annotation runs before any tag is removed.**
`img` is stripped as junk, but logo-based directories put the company name in
the image's `alt` attribute and the website in the surrounding link. Stripping
first made that recovery branch unreachable and silently dropped every link on
such pages.

**Internal links are excluded from what the model sees.**
A link back to the association's own site is a member profile page, not a
company website. Those are recovered separately in Python, as a hostname
comparison, and become the fetch queue for the profile-page stage.

**Accuracy is scored on raw output.**
Ground truth is "what names appear on this page". Scoring normalises legal
suffixes and accents so `Siemens` matches `Siemens AG`, which is a scoring
concern, not filtering.

---

## 9. Known data-quality problems

From the health check over all 291 verified URLs in the Finalv1 sheet
(`survey_finalv1.py`):

| Category | Count | Share |
|---|---:|---:|
| `directory` (a member list is present in the HTML) | 153 | 52.6% |
| `sparse` (HTTP 200 but little text: JS-rendered, or a search form) | 85 | 29.2% |
| `thin` (HTTP 200 and almost nothing) | 41 | 14.1% |
| `http_error` (4xx / 5xx) | 7 | 2.4% |
| `unreachable` (DNS or connection failure) | 5 | 1.7% |

A human marking a URL "verified" means they opened it and saw a member page.
That is not the same question as "can the pipeline extract from it": a
JavaScript-rendered directory looks correct in a browser and arrives here as
an empty page.

Separately, of the 10 ground-truth pages only **4 carry outbound member
links**. Three publish member names as plain text with no link of any kind, so
their websites cannot be extracted in one pass at all and need the profile-page
or search route.

---

## 10. Troubleshooting

**`cannot reach Ollama`**: start it with `ollama serve`.

**Benchmark seems stuck**: a `qwen3.x` model that is slow is probably thinking
before it answers; run `check_model.py <model>`. The retired `gemma4:12b`
generated until the context window filled and could take 5+ minutes per page. `qwen2.5-coder` under `constrained`
mode on the largest page took 45 minutes on GPU and still failed. The 7-8B
models under `prompt_only` average 25-45 s.

**No accuracy scores**: the worksheets are not finished. Run
`make_ground_truth.py --check` and confirm it reports 10/10.

**Start the experiment over**: delete `results/benchmark_results.csv` and
`results/extractions/`. The HTML cache and ground truth are unaffected.

**Files arrive from macOS as unopenable binary twins**: archives made on macOS
carry metadata that Linux extracts as real files. Pack with
`COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata -czf out.tar.gz <dir>`.

---

## 11. Results and caveats

Headline findings are summarised in section 1. The full record of every
measured result, including the ones that did not work, is in
**`THESIS_NOTES.md`** (~2,500 lines). Primary results are section 3.13; read
the Status block at the top first.

The caveats in section 5 of that document are not optional reading. The most
important: the ten-page corpus is small enough that **one page moves an
aggregate F1 by about 0.03**, which is larger than most of the differences the
benchmark reports. Rankings at the top of the table are safe; differences under
about 0.05 are not resolvable at this corpus size.

### Known-stale results in this snapshot

`results/benchmark_results.csv` is the original 540-run grid. Two things about
it are superseded:

1. **`generic_multi_stage` (P3) is being re-run.** Its validation stage was
   receiving Python dict reprs instead of company names, so the reported
   "best precision, worst recall" result for P3 is not yet safe to cite.
2. **Page 043 changed.** The link-annotation ordering fix altered that page's
   cleaned text. The other nine pages are byte-identical, so the rest stands.

Zero-shot and few-shot results are unaffected by both.
