# Repository guide

Bachelor thesis, Constructor University Bremen, in the NeoHub project with
Neovation GmbH (work package AP1, company database).

**Comparative Evaluation of Local LLM Models and Generic Prompt Strategies for
Extracting Company Information from Innovation Network Websites**
Giorgi Pataridze, supervised by Prof. Hendro Wicaksono.

Local LLMs served through Ollama extract member company names, websites and
contact details from German innovation-network directories. Models and
prompting strategies are benchmarked against hand-labelled ground truth.

---

## Start here

| File | What it is |
|---|---|
| `THESIS_NOTES.md` | The running record of every measured finding, ~2,300 lines. Primary results are §3.13. Read the Status block at the top first. |
| `config.py` | Every setting: models, `num_ctx`, temperature, chunking, schemas. |
| `prompts.py` | All prompt strategies, grouped into arms. |
| `benchmark.py` | The experiment runner. |

## Pipeline, in order

```
fetcher.py / browser_fetcher.py / paginate.py   download pages -> results/html_cache/
cleaner.py                                       HTML -> text, preserving links
make_ground_truth.py                             build the hand-labelled answer key
benchmark.py                                     run the grid, score it
dump_extractions.py                              flatten raw output for inspection
evaluate.py / make_xlsx.py                       tables and charts
export_deliverable.py                            the workbook Neovation receives
```

## Prompt strategies

Three "arms", selected with `benchmark.py --arm`:

| arm | strategies | returns |
|---|---|---|
| `guideline` | `zero_shot`, `few_shot_schema`, `generic_multi_stage` | names only |
| `url` | `zero_shot_full_record`, `few_shot_full_record`, `multi_stage_full_record` | name + website + address + phone + email |
| `url_ablation` | `few_shot_with_url` | name + website only |

The guideline arm is P1/P2/P3 from the supervisor's structure guideline and
answers RQ1-RQ3. The URL arm mirrors it one-for-one so the two are directly
comparable.

## Results

| Path | Contents |
|---|---|
| `results/benchmark_results.csv` | One row per run: timing, token counts, precision/recall/F1, URL metrics. |
| `results/extractions/*.json` | The raw text every model returned, one file per run. Lets the grid be re-scored without re-running it. |
| `results/html_cache/` | The exact pages the benchmark ran against. Tracked deliberately: these sites change, so without this snapshot the numbers cannot be reproduced. |
| `data/ground_truth/*.json` | Hand-labelled member lists, 785 companies across 10 pages. |
| `results/stage_a_gpu.log` | Full log of the 540-run GPU grid. |

`NeoHub_Network_Members.xlsx` (2026-08-07) and
`NeoHub_Network_Members_gpu_20260826.xlsx` are two generations of the
deliverable, kept separately rather than one overwriting the other.

## Headline results (540 runs, A100)

Best configuration: **`llama3.1:8b` + zero-shot + prompt-only JSON, F1 0.981.**

- Parameter count predicted neither speed nor quality: `gemma4:12b` placed
  last on every strategy and was slowest, failing 118 of 180 runs by
  generating until the context window filled.
- Output is deterministic at temperature 0 with a fixed seed: F1 standard
  deviation was exactly 0.000 across three repetitions on all ten pages.
- Constrained decoding is nearly free for llama, catastrophic for qwen on
  large pages (68 s to 1826 s on the largest).
- Preserving link markup improved *name* recall from 0.723 to 0.997 on a
  densely formatted page, because the trailing URL acts as a record delimiter.

Caveats are in §5 of `THESIS_NOTES.md` and are not optional reading: the
ten-page corpus is small enough that one page moves an aggregate F1 by ~0.03.

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install requests beautifulsoup4 lxml ollama pandas \
    matplotlib openpyxl python-docx ddgs
ollama pull llama3.1:8b && ollama pull qwen2.5-coder:7b

.venv/bin/python benchmark.py --stage a --arm guideline --dry-run
```

`gpu_setup.sh` does all of this on a fresh GPU node, and is safe to re-run:
completed runs are skipped.

## Note on packaging

Archives made on macOS must disable metadata, or every file arrives on Linux
with an unopenable binary twin:

```bash
COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata -czf out.tar.gz <dir>
```
