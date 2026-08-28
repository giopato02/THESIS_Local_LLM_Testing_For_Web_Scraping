# Thesis Writing Notes

Running log of findings worth putting in the thesis paper, organised by the
chapter they belong to. Every number here was measured, not estimated, the
command that produced it is noted so results can be regenerated.

Thesis: *Comparative Evaluation of Local LLM Models and Generic Prompt
Strategies for Extracting Company Information from Innovation Network Websites*
Giorgi Pataridze · Constructor University Bremen × Neovation GmbH (NeoHub AP1)

### Status (2026-08-28)

Full 540-run benchmark grid complete on GPU, plus a 60-run re-run of P3.
**Primary results are §3.13**; §3.7 and §3.8 are the earlier laptop run and
are superseded for accuracy, since link annotation (§3.11i) changed the input
between them. Best configuration: `llama3.1:8b` + zero-shot + prompt-only JSON,
F1 0.981.

**Multi-stage: use §3.13c-2, not the P3 rows in the §3.13 table.** A validator
bug was found and fixed, and P3 re-run on 2026-08-28. The finding held and grew
stronger; the corrected numbers live in §3.13c-2. The working dataset
`results/benchmark_results.csv` now carries 420 rows: 360 original zero-shot and
few-shot rows at 3 repetitions, plus 60 new P3 rows at 1 repetition. The
original grid is archived as `results/benchmark_results_540_p3bug.csv`.

gemma4:12b is closed as a negative finding (§3.13): it still fails 89 of 120
single-stage runs. Its multi-stage failure rate dropping to zero after the fix
is **unexplained** and must be diagnosed before it is written up (§3.13c-2).

Outstanding: the URL arm (§3.13b, 180 runs), the gemma4 anomaly above,
production extraction with `few_shot_full_record`, ground-truth expansion to
30-60 pages.

**Code sync.** The GPU node and this directory were reconciled on 2026-08-28;
both now carry the same patched `benchmark.py`, `prompts.py`, `cleaner.py`,
`extractor.py` and `gpu_setup.sh`. Neither syncs automatically: the GPU node's
git remote is cluster-internal and unreachable from the laptop, so code moves
by tarball, packed with `COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata`
or macOS metadata arrives as unopenable binary twins of every file.

### Project roles

Recorded because decisions in this document are attributed to individuals, and
because the annual grant report needs the split of work between the two
partners.

| Person | Organisation | Role in the project |
|---|---|---|
| Marco Sparovek | Neovation | Project lead; deliverable format; grant reporting |
| Rayen | Neovation | Data integration and backend; **owns the UDB schema**; author of `scraperng` and the company-name filter rulebook |
| Prof. Hendro Wicaksono | Constructor University Bremen | Thesis supervisor; author of the thesis structure guideline |
| Abdul Hafiz Kuliah | Constructor University Bremen | Parallel extraction track using **Gemini** (cloud), against this thesis's local models |
| Yusif | Constructor University Bremen | Merged the network lists; extending the schema with innovation-indicator attributes |
| Diego | Constructor University Bremen | Collected the technical-association member-list URLs |
| Giorgi Pataridze | Constructor University Bremen | This thesis: prompt engineering and local-LLM comparison |

---

## 1. Introduction: website heterogeneity

Hendro's guideline asks for concrete examples of how varied these sites are
(*"member lists may appear as cards, tables, logos, pagination, JavaScript
content, PDFs, or profile pages"*). These are real cases from the corpus:

| Layout | Example | Detail |
|---|---|---|
| Alphabetical index | BDEW | 26 letter pages, `?letter=A…Z`, ~1,600 members |
| JS numbered pages | Medical Valley EMN | 14 pages × 20, JetSmartFilters, no URL variant |
| JS pagination at scale | bwcon | **107** pagination pages |
| Single flat list | SPECTARIS | 285 members, A-W, one page |
| Bare brand names | EtherCAT | 7,700+ members, almost no legal forms |
| Category taxonomy | automotive BerlinBrandenburg | product categories, companies behind a search form |
| Cookie wall only | BIO Deutschland | 183 words, all of it consent text |

**Two distinct naming conventions** exist and this matters later: some
directories print full legal names (*Robert Bosch GmbH*), others print bare
brand names (*1MRobotics*, *3Dator*). Any rule requiring a legal form destroys
the second category entirely.

---

## 2. Method: pipeline design decisions

Each of these is a defensible choice with a reason; state the reason.

**Fetching is a separate phase from extraction, with HTML cached to disk.**
Both models must see byte-identical input or the comparison is not controlled.
It also keeps network latency out of the measurement and avoids re-requesting
73 real organisations' servers hundreds of times.

**`num_ctx` is set explicitly (8192).** Ollama defaults to 4,096 tokens and
**discards the overflow silently, it never raises an error**. One page in this
corpus cleans to 53,304 tokens. Left at the default, the model would read a
fraction of each page, return a short list, and every number in the thesis
would measure a truncation bug rather than model capability.

**Oversized pages are chunked, not truncated.** ~6,000-token chunks split on
line boundaries with a small overlap; results are unioned and deduplicated,
latency summed.

**The benchmark loops model-outermost.** The models are 4.7 GB and 4.9 GB and
cannot coexist in 16 GB with a KV cache. Alternating them would measure disk
loading rather than inference.

**No filtering is applied at any point.** Every extracted name is reported
exactly as the model returned it. Marco (meeting 2026-07-28): *"the scraping
stage will take as much data as possible from the source, but then we will
filter this data before storing them in the database."* Neovation applies their
company-name rulebook at database-insert time, so filtering here would both
discard data the team expects to receive and penalise the model for a
downstream rule. The filter implementation was removed from the pipeline on
2026-08-14; the analysis it produced is retained in section 4.

### Annotation rules for ground truth

State these explicitly, examiners ask for the annotation guideline.

1. **Ground truth describes the cached snapshot, not the live website.** Many
   directories paginate; labelling from the live site would include members the
   model never received, making recall meaningless.
2. **Names are recorded as a model could return them from the cleaned text.**
   Directories frequently print a town beside the company. Where the cleaned
   text puts name and location on **separate lines** (BDEW: `Amprion GmbH` /
   `Dortmund, Nordrhein-Westfalen`; InnoZent OWL: `AEU Tech GmbH,` /
   `Borchen`), only the name is annotated, a key containing the location
   would score a correct extraction as both a miss and a false positive, one
   error counted twice. Where the text puts them on **one line**
   (`Ostfalia Hochschule für angewandte Wissenschaften, Wolfenbüttel`), the
   line is annotated as printed, because that is what the model receives.

   Applied programmatically (`tidy_worksheets.py --strip-city`), which strips a
   trailing `, X` only when `X` also occurs as a standalone line in the cached
   page, so the page itself, not a guess, decides whether the town is a
   separate field. On InnoZent OWL this changed 76 of 79 entries and correctly
   left 3 untouched.
3. **Section headings, category labels and membership-tier names are excluded.**
   Only named legal entities are annotated. (Observed while labelling: tier
   headings cluster at the *end* of directories, after the main list.)
4. **Testimonial and quote attributions are excluded.** Organisations named in
   a "voices from our network" block are not member-list entries.
5. **Where a directory paginates, one page is the annotation unit**: the
   letter-A page for BDEW, page 1 for Medical Valley and BVMed. Labelling
   ~1,600 BDEW members was not feasible; the unit is documented per page.

### Prompt strategies (guideline §3.7)

| ID | Name | Implementation | Benchmarked |
|---|---|---|---|
| P1 | `zero_shot` | instruction only | yes |
| P2 | `few_shot_schema` | instruction + JSON schema + 2 worked examples | yes |
| P3 | `generic_multi_stage` | 3 calls: locate list → extract → validate | yes |
| - | `few_shot_with_url` | P2 plus the company website | no |
| - | `few_shot_full_record` | name, website, street, postcode, city, phone, email | no |

The last two exist for the deliverable, not the experiment. The grid stays at
P1-P3 so it answers RQ2 without adding a fourth arm; the record schema is
applied afterwards with whichever configuration wins. That leaves one
assumption to state in Limitations: **the winner is selected on member-name
extraction and applied unchanged to record extraction.** Closing that gap
would cost 20 runs, not a grid arm.

P3 measured at **63.5 s vs 26 s** for a single-call strategy on the same page
(2.4×), and its validation stage removed one entry. Whether that trade is
worth it is RQ2.

---

## 3. Results: data quality findings

*These are findings in their own right, not just obstacles.*

### 3.1 Only a minority of collected URLs are usable

Of 73 URLs (`results/fetch_manifest.csv`, `url_health.py`):

| Outcome | Count |
|---|---:|
| HTTP 200 | 53 |
| Dead link (404) | 7 |
| Bot-blocked (403) | 5 |
| Thin content / JS-rendered | 9 |
| Loads fine but is not a member list | ~5 |

**Roughly 23 of 73 are genuine member directories.** `200 OK` is not evidence
that a page contains data.

### 3.2 Silent truncation is the dominant hidden failure

The most important methodological finding of the project.

A paginated directory returns HTTP 200, plenty of text and plausible company
names. Nothing distinguishes *"this association has 20 members"* from *"this is
the first 20 of 400"*. **24 of 53 usable pages showed pagination markers.**

Measured recovery after implementing pagination handling:

| Site | Mechanism | Before | After | Gain |
|---|---|---:|---:|---:|
| BDEW | URL `?letter=A…Z` | 281 w | 13,255 w | **47×** |
| Medical Valley EMN | JS numbered 1-14 | 714 w | 10,894 w | **15×** |
| bwcon | JS numbered 1-107 | 279 w | 1,789 w | 6.4× |
| German Accelerator | JS | 997 w | 2,917 w | 2.9× |

Three pagination conventions were found and all three needed separate handling:
alphabetical index (`?letter=B`), page numbers (`?page=2`, or JS-only clicks),
and record ranges (`0-50`, `51-100`).

### 3.3 Automated completeness checks failed; manual inspection succeeded

Worth reporting honestly, it is a direct argument for human-validated ground
truth.

A keyword-based detector scanning HTML for pagination markers was wrong in
**both** directions:

- **BDEW scored 0** (missed), it paginates with plain URL links, not JavaScript.
- **SPECTARIS scored 61** (false alarm), the markers were CMS boilerplate; the
  page genuinely lists all 285 members.

Both errors were caught by eye during hand-labelling, the truncated file's
entries all began with "A".

The replacement heuristic, **alphabet coverage of member initials**, separates
the cases cleanly and needs no network access (`check_completeness.py`):

```
009 BDEW      A.........................   TRUNCATED (43 names, 100% "A")
050 SPECTARIS ABCDEFGHIJKLMNOP.RSTUVW...   complete (283 names, 22 letters)
```

### 3.4 The merged source file lost extraction depth

`NEOHUB_final_merged_QA_reviewed` holds 817 networks (617 ZIM + 200
private-funded), broader than the previous 73, but:

- **485 rows have no URL at all**
- of 332 URLs, only **14 have any path** beyond the domain
- **0 of 59** deep member-list URLs from the earlier sheet survived
  (`acod.de/mitglieder-und-partner/` → `acod.de`)
- only **30 of 59** organisations survive at all, the merge is not a superset

A homepage is not a member list, so a discovery step was required:
`find_member_pages.py` scores internal links for member-directory vocabulary
and reached a **67% hit rate** on first test, independently rediscovering deep
URLs the merge had dropped.

### 3.5 Hardware ceiling, not model capability

Same page, same prompt, `num_ctx=8192`:

| Model | Size | Latency | tok/s | Found |
|---|---:|---:|---:|---:|
| qwen2.5-coder:7b | 4.7 GB | 38.3 s | 16.4 | 52 |
| gemma4:12b | 7.6 GB | **444.8 s** | 5.6 | 51 |

**11.6× slower and one fewer company.** The 12B model does not fit in 16 GB
with an 8k KV cache, so the wall clock measures paging, not inference. Report
this as a deployment finding: *a 12B model is not merely slower but unusable on
consumer hardware at this context size.*

**Latency variance justifies repetition.** The same model on the same page
measured 20.9 s and 38.3 s in separate runs, hence 3 repetitions and
mean ± stdev rather than single-sample timings.

---

## 4. Discussion: analysis of Neovation's post-processing filter

*Retained as a measurement, not as pipeline behaviour. The filter was
implemented, measured, and then removed from the pipeline on 2026-08-14 once
Marco confirmed it is applied at database-insert time and is not the thesis's
concern. The figures below stand; the code no longer runs.*

The filter (`Filter for company names.pdf`) has two rules, and both are worth
analysing rather than merely applying.

**Rule 1, the legal-form whitelist** requires every name to contain
GmbH/AG/KG/UG. Measured on one page, 77% of extracted names carried a legal
form, so enforcement would discard 23% *there*, and approaching **100%** on a
bare-name directory such as EtherCAT's 7,700 members. Implemented as a recorded
flag (`has_legal_form`), never enforced, so the cost is measurable.

**Rule 2, the 69-term blacklist** uses naive case-insensitive substring
matching. Verified collisions with legitimate German company names:

| Term | Intended target | Also removes |
|---|---|---|
| `stadt` | Stadtwerke | Darm**stadt**, Ingol**stadt** |
| `kasse` | Sparkasse | **Kasse**l |
| `bank` | Deutsche Bank | Daten**bank**, Werk**bank** |
| `kreis` | Landkreis | **Kreis**laufwirtschaft |
| `post` | Deutsche Post | Kom**post** |
| `amt` | Amtsgericht | Ges**amt**-, S**amt**- |

*(Checked and rejected: "Diamant" does **not** contain "amt".)*

Every removal is logged with its triggering term and flagged when it matches a
known collision, so the false-positive rate is measured rather than assumed.

**The team independently shares this concern.** Meeting 2026-07-31: *"it's a
really basic filter… a very non-scientific way… maybe we have some there that
are useful, that are now false negatives."* Position the analysis as
quantifying a known risk, not as criticism.

---

## 3.6 Stage A execution: design and early observations

*Run started 2026-08-04. Numbers below are from the first block and must be
replaced with final figures from `evaluate.py` once the run completes.*

### Experimental design as executed

360 runs = 2 models × 3 prompt strategies × 2 JSON modes × 10 pages × 3
repetitions. Each (model, prompt, JSON mode) cell is a block of 30 runs.

**Execution order is model-outermost, and this is a hardware constraint rather
than a stylistic choice.** The three models occupy 4.7 GB, 4.9 GB and 7.6 GB
and cannot be resident together in 16 GB alongside an 8k KV cache. Alternating them would make
Ollama evict and reload weights from disk between runs, so the recorded latency
would measure disk I/O rather than inference. Pinning the model for its entire
180-run half removes that confound. A consequence worth anticipating when
reading the log: all runs of one prompt strategy complete before the next
begins, so the first 60 entries are zero-shot only.

Repetition count follows the guideline's *"repeat non-deterministic runs at
least three times"*. Decoding is deterministic (`temperature=0`, fixed seed),
so the repetitions capture **latency variance rather than output variance**, 
justified by measuring 20.9 s and 38.3 s for the same model on the same page in
separate runs (§3.5).

### Observed pace

Warm 7B model, single-call strategies: **~37 s per run**, matching the 45 s
planning estimate. The two `generic_multi_stage` blocks (runs 121-180 and
301-360) issue three model calls per page and should run roughly 2.5× slower;
the measured single-page comparison was 63.5 s vs 26 s (§2). That cost is a
result for RQ2, not a performance problem.

### Early accuracy: and what it says about the ground truth

First block (qwen2.5-coder:7b, zero-shot, constrained decoding), 26 runs:

| metric | value |
|---|---|
| mean F1 | 0.961 |
| min F1 | 0.750 |
| max F1 | 1.000 |

One page scored a perfect 1.000 (Life Science Nord, 52/52 companies, zero
false positives).

**These figures also serve as a validation of the annotation itself.** A
systematic ground-truth error, locations left attached to names, section
headings retained, or a truncated page annotated as complete, would depress F1
into the 0.3-0.5 range regardless of model quality, because every correct
extraction would register as both a miss and a false positive. Mean F1 near
0.96 is therefore evidence that the annotation rules in §2 were applied
consistently.

The spread (0.750 to 1.000) is the substantive finding to develop: it indicates
performance depends on page characteristics, which is exactly RQ3. Candidate
explanations to test against the final data, sparse pages with heavy
navigation furniture (BVMed, Medical Valley) and the one chunked page
(SPECTARIS, 296 names across 8 chunks).

---

## 3.7 Reading the experiment log (`results/stage_a_log.txt`)

One line per run:

```
  [   1/360] zero_shot       constrained  039    30.4s raw=52   F1=1.0    eta   182m
     │        │               │            │      │      │        │
     │        │               │            │      │      │        └ mean F1 for this run
     │        │               │            │      │      └ names extracted
     │        │               │            │      └ wall-clock latency
     │        │               │            └ page id
     │        │               └ JSON mode
     │        └ prompt strategy
     └ run number of 360
```

**Why the same page appears three times in a row.** Decoding is deterministic
(`temperature=0`, fixed seed), so the three repetitions return byte-identical
output, `raw` and `F1` are unchanged across them and only latency varies
(30.4 s, 21.6 s, 21.5 s on the first block; the first run pays a warm-up cost).
The repetitions measure timing variance, not answer variance.

**Why one prompt strategy runs for 60 consecutive runs.** Loop order is
model → prompt → JSON mode → page → repetition, and the model is outermost for
the memory reason in §3.6. Each (model, prompt, JSON mode) cell is a block of
30 runs; each prompt strategy therefore occupies 60 consecutive runs per model.
Few-shot begins at run 61, multi-stage at 121, and Llama at 181.

### JSON mode: what `constrained` versus `prompt_only` actually means

`prompt_only` asks the model to reply in JSON. `constrained` passes a JSON
schema to Ollama's `format` parameter, which restricts token sampling so that
no output violating the schema can be generated, the model is prevented from
producing invalid JSON rather than asked not to.

Both are run because the difference is measurable and non-obvious.

**Result (partial, first 54 runs, qwen2.5-coder:7b, zero-shot):**

| mode | n | latency | mean F1 | runs needing JSON repair | parse failures |
|---|---:|---:|---:|---:|---:|
| constrained | 30 | 41.0 s | 0.866 | 0 | 0 |
| prompt_only | 24 | 33.2 s | 0.988 | **24 (100%)** | 0 |

**Every prompt-only run required JSON repair.** The model never emitted a bare
JSON object when simply asked; it wrapped the payload in conversational text
each time. The bracket-balancing recovery layer succeeded in all 24 cases, so
parse failures are zero, but a pipeline without that layer would have failed
on every run. Reporting prompt-only results alone would therefore have
concealed a hard dependency on post-hoc repair.

Matched-pair comparison on identical page, prompt and repetition:

```
page 039   constrained 21.5 s  F1 1.0000  |  prompt_only 37.4 s  F1 1.0000
page 043   constrained 30.1 s  F1 0.9897  |  prompt_only 47.4 s  F1 1.0000
```

Constrained decoding is roughly **40% faster** and marginally less accurate, 
a clean speed/validity trade-off for RQ4. (The aggregate F1 column above is not
yet comparable: constrained has already processed page 050 and scored 0.0 three
times, which prompt-only has not yet reached.)

### Failure case worth reporting: page 050, F1 = 0.000

Zero-shot returned 54 names on SPECTARIS and **not one matched ground truth**
(TP = 0, FP = 54). JSON parsed cleanly and no error was raised.

The cause is the page's layout. Each member is a four-line block:

```
2mag AG                       <- company name
80992 München                 <- postcode + city
Konrad-Adenauer-Straße 15     <- street
Web                           <- link label
```

The model locked onto the **wrong line of the repeating block** and returned
city names, `Bremen`, `Duisburg`, `München`, `Zizers`, for all 54 entries. It
is a systematic misidentification of which field is the company name, not a
parsing or truncation fault, and it is invisible from the output alone: 54
plausible German proper nouns in valid JSON.

This is the strongest available argument for measuring against hand-labelled
ground truth. On raw count alone (`raw=54`) this run looks like a success.

Whether few-shot examples or the multi-stage locate/extract/validate strategy
recover this page is precisely RQ2, and the answer arrives in runs 61-180.

### Defect found and fixed during the run

`strip_legal_suffix()` stripped short legal forms without requiring a word
boundary, so the trailing "ag" of a name was treated as the legal form *AG*:

```
"2mag AG"      -> "2m"        (expected "2mag")
"Montag GmbH"  -> "Mont"      (expected "Montag")
"Beschlag AG"  -> "Beschl"    (expected "Beschlag")
```

Forms of ≤3 characters now require preceding whitespace or punctuation, and
compound forms (`SE & Co. KG`, `GmbH & Co.KG`) were added ahead of their parts.
Impact was limited for scoring, since prediction and ground truth pass through
the same normalisation and would mangle identically, but `company_name_clean`
in the deliverable would have been wrong, so Neovation would have received
"2m" for "2mag AG".

---

## 3.8 Stage A final results

Completed 2026-08-04. 360 runs: 2 models × 3 prompt strategies × 2 JSON modes
× 10 pages × 3 repetitions. **Total wall clock 16.6 h**, of which 16.5 h was
model inference (the pipeline itself adds almost no overhead, since pages are
served from the local HTML cache).

The 4.5 h planning estimate assumed 45 s per run. The overrun is entirely
attributable to `generic_multi_stage`, which averaged 88-715 s per run.

### Full configuration ranking

| Model | Prompt | JSON | Latency | tok/s | Precision | Recall | **F1** | Repair rate |
|---|---|---|---:|---:|---:|---:|---:|---:|
| llama3.1:8b | few_shot_schema | prompt_only | 56.1 ± 68 s | 14.5 | 0.971 | 0.945 | **0.957** | 0% |
| llama3.1:8b | few_shot_schema | constrained | 61.2 ± 71 s | 14.7 | 0.971 | 0.945 | **0.957** | 0% |
| qwen2.5-coder:7b | few_shot_schema | constrained | 53.0 ± 48 s | 15.4 | 0.982 | 0.909 | 0.937 | 0% |
| llama3.1:8b | zero_shot | prompt_only | 53.4 ± 74 s | 14.7 | 0.956 | 0.903 | 0.919 | 0% |
| llama3.1:8b | zero_shot | constrained | 58.5 ± 76 s | 14.9 | 0.956 | 0.903 | 0.919 | 0% |
| qwen2.5-coder:7b | zero_shot | prompt_only | 46.0 ± 42 s | 13.8 | 0.985 | 0.902 | 0.909 | **100%** |
| qwen2.5-coder:7b | generic_multi_stage | prompt_only | 88.2 ± 68 s | 15.5 | 0.982 | 0.840 | 0.874 | **100%** |
| qwen2.5-coder:7b | generic_multi_stage | constrained | 103.1 ± 80 s | 15.5 | 0.921 | 0.840 | 0.871 | 0% |
| qwen2.5-coder:7b | zero_shot | constrained | 41.0 ± 33 s | 16.1 | 0.884 | 0.852 | 0.866 | 0% |
| qwen2.5-coder:7b | few_shot_schema | prompt_only | 72.9 ± 105 s | 15.8 | 0.902 | 0.821 | 0.849 | 20% |
| llama3.1:8b | generic_multi_stage | prompt_only | **627.4 ± 1713 s** | 15.1 | 0.985 | 0.622 | 0.736 | 40% |
| llama3.1:8b | generic_multi_stage | constrained | **714.8 ± 1983 s** | 14.7 | 0.985 | 0.615 | 0.730 | 0% |

**Best configuration: `llama3.1:8b` + few-shot schema + prompt-only JSON,
F1 = 0.957 (P 0.971 / R 0.945) at 56.1 s per page.**

### By prompt strategy (RQ2)

| Strategy | llama3.1:8b | qwen2.5-coder:7b |
|---|---:|---:|
| zero_shot | 0.919 | 0.866 - 0.909 |
| few_shot_schema | **0.957** | **0.937** (constrained) |
| generic_multi_stage | 0.730 - 0.736 | 0.871 - 0.874 |

Few-shot beats zero-shot for both models. Multi-stage is worst for both, and
catastrophically so for llama.

### By JSON mode: a model-dependent effect (RQ3)

| Model | Prompt | constrained | prompt_only | Δ |
|---|---|---:|---:|---:|
| llama3.1:8b | few_shot_schema | 0.957 | 0.957 | 0.000 |
| llama3.1:8b | zero_shot | 0.919 | 0.919 | 0.000 |
| qwen2.5-coder:7b | few_shot_schema | 0.937 | 0.849 | **0.088** |
| qwen2.5-coder:7b | zero_shot | 0.866 | 0.909 | −0.043 |

**JSON mode has no measurable effect on llama and a large one on qwen.** The
repair-rate column explains why: llama required JSON recovery in 0% of runs and
emits a bare JSON object unprompted, whereas qwen required recovery in up to
100% of prompt-only runs, wrapping the payload in conversational text. This is
a genuine model × decoding-mode interaction and answers RQ3 directly.

It is also counterintuitive and worth foregrounding: `qwen2.5-**coder**` is the
code-specialised model, and it is the one that cannot reliably emit valid JSON.

### Why multi-stage fails: the mechanism

The failure is not random; it is the validation stage over-pruning.

| Model | Strategy | Precision | Recall | Names returned per page |
|---|---|---:|---:|---:|
| llama3.1:8b | few_shot_schema | 0.971 | 0.945 | 70 |
| llama3.1:8b | generic_multi_stage | 0.985 | **0.619** | **32** |
| qwen2.5-coder:7b | few_shot_schema | 0.942 | 0.865 | 61 |
| qwen2.5-coder:7b | generic_multi_stage | 0.951 | 0.840 | 50 |

Adding the third stage raises llama's precision marginally (0.971 → 0.985) and
halves its recall (0.945 → 0.619); the model returns 32 names where two-stage
extraction returned 70. **The validation step discards correct entries in order
to appear confident**, at roughly 11× the runtime. Decomposing the task into
locate → extract → validate does not benefit models at this scale.

### Per-page results, best configuration

| Page | Tokens | Chunks | P | R | F1 |
|---|---:|---:|---:|---:|---:|
| 039 Life Science Nord | 469 | 1 | 1.000 | 1.000 | **1.000** |
| 012 BVMed | 912 | 1 | 1.000 | 1.000 | **1.000** |
| 040 Medical Valley | 1 943 | 1 | 1.000 | 1.000 | **1.000** |
| 043 NMWP.NRW | 722 | 1 | 1.000 | 0.980 | 0.990 |
| 032 InnoZent OWL | 1 149 | 1 | 0.975 | 0.975 | 0.975 |
| 005 automotive thüringen | 4 873 | 1 | 0.976 | 0.968 | 0.972 |
| 004 Automotive Nordwest | 1 014 | 1 | 0.970 | 0.970 | 0.970 |
| 009 BDEW | 827 | 1 | 0.951 | 0.907 | 0.929 |
| 025 German Water Partnership | 2 872 | 1 | 0.929 | 0.929 | 0.929 |
| 050 SPECTARIS | 9 383 | 2 | 0.914 | 0.723 | 0.807 |

The only page below 0.9 is the one requiring chunking. Recall falls to 0.723
there (235 of 296 members found) while precision holds at 0.914, indicating
loss at chunk boundaries rather than hallucination.

### Error analysis

All 12 hard errors in the experiment (`unparseable JSON`) occurred on page 050,
the single chunked page, 3 for qwen zero-shot and 9 across both models'
multi-stage runs. Long generated lists combined with chunking are where JSON
integrity breaks down.

**Correction to an earlier observation.** Page 050's catastrophic zero-shot
result (§3.7, F1 = 0.000, 54 city names returned) is *not* robust across
strategies. Few-shot recovered it substantially, 235 correct companies,
F1 = 0.807. The address-block confusion is therefore a **zero-shot weakness
that worked examples correct**, which strengthens rather than weakens the RQ2
finding.

### Averaging artefact: a caution for the write-up

| Model | Mean F1 across all 6 configurations | Mean latency |
|---|---:|---:|
| qwen2.5-coder:7b | 0.884 | 67.4 s |
| llama3.1:8b | 0.870 | 261.9 s |

Averaged over configurations, qwen appears superior. This is an artefact: llama's
mean is depressed by its two catastrophic multi-stage cells. **Report the best
configuration per model, not the per-model mean**, averaging across a strategy
already shown to be defective is not a meaningful comparison.

### Precision/recall character, and which matters here

qwen is consistently the more conservative model (higher precision, lower
recall); llama is the more exhaustive one. For the NeoHub application **recall
is the more valuable property**: a member the pipeline never extracts is
invisible downstream, whereas a spurious entry is caught by Neovation's
rulebook at database-insert time. llama is therefore the better choice on
application grounds as well as on F1.

---

## 3.9 Scaling projection and remaining model

### What actually drives runtime

Correlation of latency with candidate predictors, best configuration:

| Predictor | r |
|---|---:|
| companies extracted | **0.990** |
| output tokens generated | 0.986 |
| input tokens (page size) | 0.919 |

Runtime is governed by **generation volume, not page size**: the model spends
its time writing the answer, not reading the page. Measured rate:

> **≈ 0.81 s per company extracted**, plus roughly 8-12 s fixed cost per page.

This is more useful than a per-page average, because it scales with what a
directory actually contains. It also explains the spread in the per-page table:
page 025 (14 members, 2 872 tokens) took 8.5 s while page 039 (52 members, 469
tokens) took 30.3 s, six times fewer input tokens, three times the runtime.

### Projection to ~300 pages

Corpus profile of the 53 currently usable pages: median 1 885 tokens,
30 pages < 2 k tokens, 11 at 2-6 k, 12 > 6 k.

| Assumption | Companies/page | Estimate |
|---|---:|---:|
| Optimistic (corpus skews to small directories) | ~30 | **≈ 3.0 h** |
| Central estimate | ~45 | **≈ 4.0 h** |
| Pessimistic (many large directories) | ~70 | **≈ 5.7 h** |

**Plan for roughly 4-6 hours for 300 pages** on the winning configuration,
single pass. This is an overnight job on the current laptop and needs no
special hardware. Two caveats: pagination expansion (§3.2) increases per-page
member counts and therefore runtime, and the estimate assumes the 300 pages are
genuine member directories rather than homepages requiring discovery first.

### Is gemma4:12b worth adding?

**Yes, but only on the winning configuration, not the full grid.**

Arguments for:

- Hendro's guideline specifies **3-4 instruction-tuned local models**; two have
  been evaluated, so the study is currently below the recommended range.
- Both models tested are 7-8B. gemma4:12b is a different size class, so it
  tests whether capability scales with parameter count on this task, a
  question neither current model can answer.
- **Accuracy measurement is hardware-independent.** Memory pressure inflates
  latency but does not change the generated text, so precision/recall/F1 from a
  swapping run remain valid. Only the timing column carries the caveat.

Cost, extrapolated from the measured 444.8 s vs 38.3 s comparison on page 039
(§3.5), a ratio of ≈14.7× against llama's per-page time:

| Scope | Runs | Estimated time |
|---|---:|---:|
| Full grid (as run for the other two) | 180 | ≈ 41 h, not feasible |
| Winning config, 10 pages, 3 repetitions | 30 | **≈ 6.9 h**: feasible overnight |
| Winning config, 10 pages, 1 repetition | 10 | **≈ 2.3 h** |

Recommended: run the winning configuration with 3 repetitions (~7 h,
unattended) and report gemma4 as a **scaling observation** rather than a full
factorial arm, accuracy compared directly against the other two models,
latency reported with an explicit note that it reflects memory pressure on
16 GB rather than model throughput. If CKL GPU access materialises, promote it
to a full arm.

Command:

```
.venv/bin/python benchmark.py --stage a --models gemma4:12b \
    --prompt few_shot_schema --json-mode prompt_only
```

---

## 3.10 Extending the schema to company websites: and a data-availability limit

Requested by Hendro (meeting 2026-08-06): the deliverable must carry each
member's own website alongside its name, in a **single** extraction pass. His
reasoning against two passes was cost and matching, running the model twice
doubles tokens and creates a name-to-URL alignment problem afterwards.

### The pipeline could not have returned a URL at all

`cleaner.py` converts HTML with `get_text()`, which discards every `href`
attribute. Measured on the annotated pages, the text presented to the model
contained **zero URLs**. No prompt could have produced a company website; the
information never reached the model. Text extraction now writes outbound link
targets inline beside their anchor text:

```
Robert Bosch GmbH        ->   Robert Bosch GmbH <https://www.bosch.de>
```

Only links leaving the association's own domain are annotated. Hostname
comparison uses shared name labels rather than the first label, because NMWP
serves its directory from `verein.nmwp.nrw` and its member profiles from
`portal.nmwp.de`, the same organisation on two domains, which a naive check
would have mistaken for member websites. Where an entry is a bare logo, the
company name is recovered from the image's `alt` attribute, which `get_text()`
would otherwise drop.

Cost: **+26% to +48% tokens** on pages that carry links, and nothing on pages
that do not.

### Company websites are available on a minority of pages

| Page | Members | URLs on page | Coverage |
|---|---:|---:|---:|
| 050 SPECTARIS | 296 | 290 | **98%** |
| 005 automotive thüringen | 125 | 120 | **96%** |
| 009 BDEW | 43 | 41 | **95%** |
| 025 German Water Partnership | 14 | 1 | 7% |
| 039, 043, 012, 004, 032, 040 | 283 | 0 | **0%** |

**Three of ten pages carry member websites.** On the remaining seven the data
is absent from the page, not merely hard to extract: entries either have no
outbound link, or link to a profile page hosted by the association itself
(NMWP: `portal.nmwp.de/enterprise/view?guid=2591`).

This qualifies the single-pass requirement. Where links exist, one pass is both
sufficient and cheapest, exactly as specified. Where they do not, no prompting
strategy can recover them, obtaining those URLs requires either a second fetch
per member (following the association's profile page) or name-to-URL resolution
through a search engine, which is the same technique already needed to fill the
empty homepage column in the merged database.

### Verified working

`llama3.1:8b` with the extended few-shot schema on BDEW: **42 companies
returned, 40 with correct company websites** (`A.T. Kearney GmbH` →
`https://www.de.kearney.com/`). Latency rose from ~25 s to **92 s** on the same
page, roughly 3.7×, because output length roughly doubles and runtime is
governed by generation volume (§3.9).

### Does Stage A need repeating?

No. Stage A measured which model and prompt strategy extract member *names*
best, and that comparison stands. RQ1-RQ3 concern model and prompt behaviour,
not the output schema. The URL field is an extension of the deliverable, and it
requires re-running only the **production** extraction, not the 360-run
ablation.

Two points do need measuring before the extended schema is used at scale:

1. Whether requesting a second field degrades name extraction. The 92 s vs 25 s
   latency change is established; the accuracy effect is not.
2. URL correctness, which needs **no manual annotation**: a returned URL either
   appears in the cached page or the model invented it, so field-level accuracy
   is verifiable automatically. This satisfies the guideline's "field-level
   accuracy/F1" requirement at no annotation cost.

### Deliverable format (as specified by Hendro)

`export_deliverable.py` writes `NeoHub_Network_Members.xlsx`:

| Sheet | Contents |
|---|---|
| Network members | `company name` · `company website` · `network name` · `network url` |
| Summary | per-network coverage, model and prompt used, and caveats |

Network name and URL are joined in Python from the source URL list rather than
requested from the model, the provenance is already known, so spending tokens
re-deriving it would only introduce error.

---

## 3.11 Resolving company URLs where the directory does not provide them

> **Superseded by 3.11d.** This section records the first assessment, made
> before profile-page coverage was measured against ground truth. Its
> "Location data availability" table describes what each page prints *as text*,
> which remains accurate, but its conclusion that seven pages offer no route to
> a URL was wrong: five of them link each member to a profile page. Kept for
> the record of how the assessment changed.

Decisions from meeting 2026-08-07 (Marco, Yusif, Hafiz; Hendro absent).

### The identity problem

Marco: a German company name is **not** legally unique, it is unique only
*within a city*. Neovation's own record matching therefore keys on **name +
physical address**, and a name-only match against their ~1M-record database
produces a non-trivial number of ambiguous hits.

This is why address extraction was raised, and it is a matching requirement
rather than an extraction one.

### Accepted scope reduction

Hafiz proposed, and Marco accepted, that addresses should **not** be collected
for every company. The pipeline splits into two phases:

1. **Data acquisition** (this thesis): extract member names, and websites where
   the page provides them.
2. **Data merging** (later): match names against the company database, and
   resolve an address **only for names that turn out to be ambiguous**.

Marco's formulation: *"if getting the address of the company makes it more
complicated or more hallucinating, then that's the second step that maybe we
don't need, if we have unique pairs through the names only."*

This materially reduces the extraction task, per-company address extraction is
conditional, not universal, and depends on a measurement (how many names are
ambiguous) that has not been made yet.

### Four resolution routes, in ascending cost

Evaluated against the finding that only 3 of 10 annotated pages carry member
websites (§3.10):

**1. Association profile pages, free, deterministic, verified.**
Directories such as NMWP link each member to a profile page on their own site.
Fetching `portal.nmwp.de/enterprise/view?guid=2591` returns exactly one external
link, `http://www.access-technology.de`, the company's website. One extra
request per member, no model involved, no ambiguity.

**2. Matching against the existing company database, free, instant.**
Neovation holds ~5.6M company records; the `public.company` table written by
`scraperng` carries a `domain` column, and the OpenCorporates import has now
been merged successfully. Resolving an extracted name (plus city where the page
provides one) is a local join rather than thousands of web requests.

**3. Impressum scraping, deterministic, no model needed.**
Marco's observation: German law requires an Impressum, so once a company URL is
known its address and email can be read directly without AI. Tested on three
extracted URLs: `ados.de/impressum` yielded `52078 Aachen` and `info@ados.de`;
the other two yielded partial or no data on a naive path-guessing attempt. The
approach is sound but needs a real implementation, following the page's own
"Impressum" link rather than guessing paths, and handling JS-rendered pages.

**4. Search engine, last resort, and the only one that costs money.**
Google's Custom Search JSON API allows 100 queries/day free and then bills per
thousand; Microsoft has retired the Bing Search API; DuckDuckGo publishes no
web-results API. Scraping results directly breaches terms and is blocked
quickly. At roughly 300 networks × ~50 members this is ~15,000 lookups, and a
top result is frequently LinkedIn or a directory listing rather than the
company's own site.

### Location data availability, measured

| Page | Company links | Postcode | City | Usable key |
|---|---:|---:|---:|---|
| 050 SPECTARIS | 290 | 288 | 83 | link present |
| 005 automotive thüringen | 120 | 146 | 21 | link present |
| 009 BDEW | 41 | 0 | 23 | link present |
| 032 InnoZent OWL | 0 | 0 | 60 | name + city |
| 043 NMWP.NRW | 0 | 0 | 10 | name + city |
| 004 Automotive Nordwest | 0 | 0 | 6 | name + city |
| 039, 012, 040, 025 | 0 | 0 | 0 | **name only** |

**Full postal addresses appear only on pages that already carry links**, that
is, exactly where they are not needed. Three further pages provide a city,
which is sufficient for the name+city uniqueness rule. Four provide nothing but
the name, and for those no extraction strategy can produce a disambiguating
key; they depend on route 1 or 2 above.

### Proximity as a matching signal (noted, not actioned)

Marco observed that geographic proximity may matter for partner *matching*
independently of the innovation score, a Bremen company may be likelier to
collaborate with a Bremen institution, particularly for hardware development.
Not part of this thesis, but it strengthens the case for capturing city where
it is cheaply available.

---

## 3.11b Options for obtaining company URLs: evaluated

> **Partly superseded by 3.11d**, which is the complete and current analysis.
> The measurements here (profile-page coverage, domain-construction hit rate)
> are current; the cost ranking is not, since `ddgs` later removed the case for
> a paid search API.

Marco's position (2026-08-07) is that company websites are a hard requirement,
not a nice-to-have. His proposed route was: extract the company's postal
address, then use address + name to resolve the website through a search
engine, on the grounds that a German company name is unique only within a city.

The uniqueness argument is correct. The obstacle is that **the address is not on
the pages that lack links** (§3.11), full addresses appear only on pages that
already carry company websites. So the proposed chain cannot start where it is
needed.

The requirement is nevertheless satisfiable, by other routes. Five were
evaluated.

### Route 1: Association member profile pages *(free, and near-universal)*

**Corrected twice. This is the primary route, not a special case.**

Two earlier assessments in this document were wrong, by two different faulty
methods, and the record is kept because the methodological lesson matters:

1. First assessment generalised from a single NMWP profile page and called this
   the strongest route without measuring coverage.
2. Second assessment tried to measure coverage by grouping internal links by
   URL *path shape* and counting distinct destinations. That collapsed unlike
   URLs into shared buckets and reported "1 distinct link" for pages that in
   fact have one per member. It concluded the route covered one directory of
   seven.

Both were structural measurements. The correct test is against the **ground
truth**: for each annotated company, does a link exist whose anchor text, logo
`alt` attribute, or enclosing container matches that company?

| Page | Members | Matched to a per-member link | Link carried by |
|---|---:|---:|---|
| 039 Life Science Nord | 52 | **52 (100%)** | company name |
| 004 Automotive Nordwest | 33 | **32 (97%)** | company name |
| 043 NMWP.NRW | 49 | **45 (92%)** | logo `alt` |
| 025 German Water Partnership | 14 | **12 (86%)** | company name |
| 012 BVMed | 50 | present | adjacent "Mehr lesen" link |
| 040 Medical Valley EMN | 20 | none found | - |

**Five of the six link-free directories expose a per-member profile page**,
covering roughly 204 of the 218 companies previously recorded as
name-only. The company website is not absent from these directories; it is one
hop away, behind the association's own profile page.

The reason the earlier counts failed is worth stating: **on 012 the link is not
on the company name at all**, it sits on a "Mehr lesen" element beside it, so
any method keyed on anchor text alone reports zero. Container-level matching is
required.

Correction to §3.11's "name only" classification: that table described what is
*printed as text* on the directory page, which remains accurate, but it should
not be read as "no route to a URL exists".

**Coverage measured after an initial over-estimate.** This route was first
assessed from a single NMWP profile page and described as the strongest option.
Counting *distinct* per-member links across all seven link-free pages shows it
is far narrower than that:

| Page | Members | Distinct per-member links | Usable |
|---|---:|---:|---|
| 043 NMWP.NRW | 49 | 20 | partial |
| 039 Life Science Nord | 52 | 6 | no |
| 012 BVMed | 50 | 3 | no |
| 040 Medical Valley | 20 | 2 | no |
| 004, 032, 025 | 126 | 1 each | no |

An earlier count appeared to show profile pages on several sites, but it
counted repeated navigation links rather than distinct destinations, the
pattern `/mitgliederliste/` occurring 77 times on a 33-member page is one link
in a template, not 77 profiles.

**One directory of seven, covering roughly 20 companies.** Worth implementing
eventually because the data it returns is complete and free, but it is a
special case, not the general solution. Routes 2 and 3 are the general answer.

The data it returns where it does apply:

Directories that show no outbound link often link each member to a profile page
on the association's own portal. Fetching one such page for NMWP
(`portal.nmwp.de/enterprise/view?guid=2591`) returns:

```
name      Access e.V.
street    Intzestr. 5
postcode  52072 Aachen
email     welcome@access-technology.de
website   http://www.access-technology.de
```

**Every field Marco asked for, from a single request, with no model involved.**
This is the strongest route: no cost, no API, no hallucination surface, and it
supplies the address for the disambiguation problem at the same time. Cost is
one extra HTTP request per member.

Applicable wherever a directory has per-member profile pages, the same
structure that made those pages look "link-free" in the first place.

### Route 2: Match against Neovation's existing company database

**Composition of the 5.6M figure** (from the kickoff deck p.6 and
`Collected data and status of sources.pdf`):

| Source | Raw | Post-processed |
|---|---:|---:|
| Offeneregister | 5,305,727 | 1,025,150 |
| Förderkatalog | 300,170 | 99,038 |
| Companies Data Cloud | 985,077 | not yet |
| Germany Business Giga Sheet | 429,577 | not yet |
| companydata.com | 305,832 | not yet |
| Europages + WLW | 239,846 | not yet |
| Bisnode | 228,212 | not yet |
| Gelbe Seiten | 48,443 | not yet |
| firmendatenbanken | 45,286 | not yet |

**The critical qualification, from Neovation's own document** (`Relevant_Links_v2`):

> *"we will probably also need URLs from the companies. These are not stored in
> the commercial registers and may need to be found via Google Maps or other
> search engines."*

Offeneregister is Handelsregister-derived and accounts for the large majority
of the database, so **the bulk of those records carry no website by design**.
The URL-bearing sources are the smaller B2B directories (Europages, Gelbe
Seiten, firmendatenbanken, and the `domain` column written by `scraperng`'s
firmenregister spider), and most are still marked "not yet post-processed".

Consequences:

- **For company websites this route is weaker than it first appears.** It should
  be tested rather than assumed, and the realistic coverage is unknown until
  someone queries the URL-bearing subset.
- **For addresses and for name disambiguation it is strong**, because that is
  exactly what a commercial register does contain. It is therefore the right
  instrument for the ambiguity question in §3.11, measuring how many extracted
  names match more than one record, even if it contributes few URLs.
- **Access is a blocker.** The database sits in Neovation's PostgreSQL; the
  student has no access and would need an export or a query endpoint from
  Rayen.

### Route 3: Domain construction and verification *(free, measured)*

Generate candidate domains from the company name, fetch each, and keep only one
whose page actually contains that name. DNS resolution alone proves nothing, 
parked domains and squatters resolve, so the verification step is what
separates this from guessing.

**Measured on a random sample of 25 companies drawn from the six link-free
pages: 18 resolved and verified (72%).** Umlauts are transliterated
(`Weidmüller` → `weidmueller`), legal forms stripped, and candidates generated
as concatenated, hyphenated, first-two-words and first-word variants across
`.de`, `.com`, `.net`.

Correct results include `mechOnics ag` → `mechonics.de`, `aap Implantate AG` →
`aap.de`, `APAGCoSyst Control Systems GmbH` → `apagcosyst.com`.

**Three of the 18 are wrong, and the failure mode is systematic:**

```
Fraunhofer IEM        -> fraunhofer.de   parent organisation, not the institute
Fraunhofer IOSB-INA   -> fraunhofer.de   same
Treuhand Weser-Ems    -> treuhand.de     generic first word
```

The verification threshold (half the name's tokens present on the page) is too
permissive when the leading token is a common noun or a parent brand, the
parent's site legitimately contains the child's name. **Realistic accuracy is
therefore about 60%, not 72%**, and the corrections needed are to weight
distinctive tokens above generic ones and to reject single-word candidates
whose page does not also match the remaining tokens.

Failures (7 of 25) are mostly organisations with no obvious domain form:
`Erfinderclub Paderborn e.V`, `Fraunhofer ITMP - ScreeningPort`,
`SIL System Integration Laboratory GmbH`.

Even at 60%, this is the highest-coverage free route measured so far, and it
reduces the volume a paid search API would need to handle by more than half.

### Route 4: Search API *(cheap, not free)*

**Correction to an earlier assessment in this document.** Search was previously
characterised as prohibitively expensive; that was wrong. Current options:

| Provider | Cost |
|---|---|
| Serper.dev | ~$1 per 1,000 queries |
| Brave Search API | 2,000/month free, then a few $ per 1,000 |
| Google Custom Search | 100/day free, then $5 per 1,000 |
| Bing Search API | retired by Microsoft |

At roughly 300 networks × ~50 members ≈ 15,000 lookups, that is **$15-75 in
total**, not a barrier. The real limitation is result quality, not price: a
top search result is frequently LinkedIn, Northdata, or a directory listing
rather than the company's own site, so results need the same
name-appears-on-page verification as Route 3.

Sensible as the fallback for whatever Routes 1-3 leave unresolved.

### Route 5: Impressum scraping *(for address and email, once a URL is known)*

German law requires an Impressum, so address and email can be read directly
from a company site without a model. Tested on three extracted URLs:
`ados.de/impressum` yielded `52078 Aachen` and `info@ados.de`; two others gave
partial or nothing under naive path-guessing. A real implementation follows the
page's own "Impressum" link rather than guessing paths.

This is the answer to the address requirement for companies whose URL is known
- which, after Routes 1-4, should be most of them.

### Recommended order

Revised after measuring profile-page coverage. The two general-purpose routes
come first; the special cases fill gaps behind them.

1. **Database match**: free, applies to any name present in Neovation's
   ~5.6M records, and measures the name-ambiguity rate as a by-product
2. **Domain construction + verification**: free, applies to any company name
   at all, ~5 of 6 in a first test
3. **Search API** for whatever remains, ~$15-75 for the whole corpus
4. **Profile pages** where a directory has them, free and complete, but
   measured at one directory of seven
5. **Impressum** on every resolved URL, for address and email

Every route ends with the same verification: fetch the candidate URL and
confirm the company's name appears on the page. That check is free, it is what
separates resolution from guessing, and it is what makes the resulting field
auditable rather than asserted.

**Sequencing matters more than any single route.** Each step is cheaper and
more reliable than the one after it, so the honest way to decide whether the
paid option is needed is to run the free ones first and measure the remainder, 
rather than estimating coverage in advance, which is exactly the error made in
the first assessment of Route 1.

Each step is cheaper and more reliable than the one after it, and every step
ends with the same verification: does the company's name actually appear on the
page the URL points to.

---

## 3.11c Does extracting URLs change the benchmark results?

Raised by Giorgi, and it is a genuine methodological risk rather than a detail.

The Stage A ranking (§3.8) measured extraction of **names only**. Adding a
second field changes the task in four ways:

1. **Input grows** by 26-48% on pages carrying links, so more of the context
   window is consumed and chunk boundaries shift.
2. **Output roughly doubles**, and runtime is governed by generation volume
   (r = 0.990, §3.9). Measured on BDEW: **92 s versus ~25 s**, a 3.7× increase.
3. **The task becomes relational.** The model must associate a URL with the
   correct company, not merely recognise a name. On pages where the link sits
   several lines below the name (`2mag AG` / `80992 München` / street / `Web
   <url>`), that association is a distinct skill from name recognition.
4. **Output is now structured objects** rather than a flat list of strings.

The consequence: **the winning configuration for names may not win for
name+URL.** There is a specific reason to expect movement in the ranking, 
`qwen2.5-coder` is the code-specialised model and lost on names, but multi-field
structured JSON is closer to what it was trained for. Its higher precision
(0.982-0.985 throughout) may also matter more when a wrong URL is worse than a
missing one.

Assuming the Stage A winner transfers would be an unmeasured assumption at the
centre of the results chapter. The grid should therefore be re-run with the
name+URL schema before a winner is declared for the deliverable, which is also
the plan for hardware reasons (§3.9).

**Ground truth does not need re-annotating.** Name annotations are unchanged,
and URL correctness is verifiable automatically: a returned URL either appears
in the cached page or the model invented it. This yields the field-level
accuracy the guideline asks for at zero annotation cost.

---

## 3.11d Company-URL acquisition: complete option analysis

Marco's requirement (2026-08-07, restated 2026-08-11) is that every extracted
company must carry its website. Below is every approach considered, what each
costs, and why the rejected ones fail. Measurements are from the ten annotated
pages unless stated.

**The problem in one line:** of 543 annotated companies, 459 sit on pages that
print no company URL in their visible text.

### Discovery methods

#### D1: Direct extraction from the directory page *(VIABLE, in use)*

The LLM reads the listing and returns `{name, url}` where the page shows a link.
Requires link annotation in the cleaner, since text extraction discards `href`
attributes (§3.10).

- **Coverage:** 3 of 10 pages (050, 005, 009) at 95-98% within those pages.
- **Cost:** +26-48% input tokens, ~3.7× latency (92 s vs 25 s on BDEW).
- **Verified:** 42 companies returned, 40 with correct websites.
- **Limit:** cannot produce what is not on the page. Seven pages return empty.

#### D2: Follow per-member profile pages *(VIABLE, highest value)*

Most directories that appear link-free actually link each member to a profile
page on the association's own site. That page carries the company's real
website, street, postcode, city and an email address.

| Page | Members | Matched to a profile link |
|---|---:|---:|
| 039 Life Science Nord | 52 | 52 (100%) |
| 004 Automotive Nordwest | 33 | 32 (97%) |
| 043 NMWP.NRW | 49 | 45 (92%) |
| 025 German Water Partnership | 14 | 12 (86%) |
| 012 BVMed | 50 | present (link on "Mehr lesen") |
| 040 Medical Valley EMN | 20 | none, genuine outlier |

- **Coverage:** ~204 of the 218 companies previously classed as name-only.
- **Cost:** one HTTP request per member; optionally one small model call
  (profile pages are ~600 tokens).
- **Verified:** `llama3.1:8b` returned all six fields correctly from an
  Automotive Nordwest profile in 13.5 s on the laptop, ~2 s expected on an A100.

The link is carried differently per site, on the company name, on the logo's
`alt` attribute, or on an adjacent "Mehr lesen" element, so discovery must
match **name → anchor text, image alt, or enclosing container**, not anchor
text alone.

#### D3: Meta-search with `ddgs` *(VIABLE, free)*

Python library querying DuckDuckGo and aggregating results. No API key, no
cost. Suggested by Neovation, who used it previously with a GPT-4-mini
container and report roughly 90% correct domains at 1,000-company scale.

Tested on five companies from link-free pages, top result only:

```
myconsult GmbH Salzkotten     -> myconsult.de           correct
Ajambow GmbH                  -> ajambow.com            correct
Akkodis Edge Germany GmbH     -> akkodis.com/de         correct (parent)
Erfinderclub Paderborn        -> erfinderclub-pb.de     correct
ATP Automotive Testing        -> de.wikipedia.org/...   wrong
```

- **Coverage:** 4 of 5 on the raw top result; higher with encyclopaedia and
  directory domains filtered, and higher again with D3b below.
- **Cost:** free. Rate-limited, and it scrapes rather than using an official
  API, so it is a grey area contractually.
- **Note:** it resolved `Erfinderclub Paderborn`, which domain construction
  (D4) failed on, the two methods fail on different inputs and therefore
  compose well.

#### D3b: `ddgs` results ranked by an LLM *(VIABLE, best for hard cases)*

Return the top 5-10 search results and let the model choose the company's own
site, using the network name and any description as context. This is
Neovation's existing pattern. It fixes exactly the D3 failure above, a model
recognises a Wikipedia article as not being the company's website.

- **Cost:** one small model call per unresolved company.
- **Risk:** hallucination is bounded, because the model *selects from a
  supplied list* rather than generating a URL.

#### D4: Domain construction from the company name *(VIABLE, cheap pre-pass)*

Generate candidate domains (concatenated, hyphenated, first-two-words,
first-word) with umlaut transliteration across `.de`, `.com`, `.net`, then
fetch each and keep one whose page contains the company name.

- **Measured:** 25 random companies from link-free pages → 18 resolved (72%),
  of which about 3 are wrong → **~60% correct**.
- **Failure mode is systematic:** the leading token being a parent brand or a
  common noun (`Fraunhofer IEM` → `fraunhofer.de`, `Treuhand Weser-Ems` →
  `treuhand.de`).
- **Cost:** free, no third-party service.

#### D5: Lookup in Neovation's company database *(VIABLE, blocked on access)*

Offered by Neovation on 2026-08-11: link extracted names against their records
locally and read the domain from whichever source has one.

- **Confirmed by them:** the ~5M OpenCorporates records carry **no domains**;
  other sources do, extent unknown.
- **Cost:** free, local join, no network.
- **Blocker:** the student has no database access; needs an export or endpoint.
- **Secondary value:** it is the only instrument that can *measure* how many
  extracted names are ambiguous, which decides whether per-company address
  extraction is needed at all.

#### D6: Google Maps / Places API *(VIABLE, paid)*

Listed in the project's own source review. Returns business websites reliably.
Requires a billing account and is subject to quota; not tested. Retained as a
fallback behind the free routes.

### Verification methods

None of the discovery methods is trustworthy without a check, and every check
below is free.

- **V1, Name on page.** Fetch the candidate URL and confirm the company name
  appears. Catches parked domains, squatters and wrong search hits. Weak when
  the leading token is generic; weight distinctive tokens higher.
- **V2, Site references the network.** Marco's suggestion (2026-08-11): a
  genuine member frequently mentions the association or displays its logo.
  Strong positive signal, and independent of V1.
- **V3, Email domain agreement.** Where a profile page yields
  `info@atp-papenburg.de`, the domain corroborates `atp-papenburg.de`. Free,
  and available exactly where D2 applies.

### Rejected approaches

#### R1: Extract the address first, then search on name + address

Marco's original proposal (2026-08-07). The reasoning is sound, a German
company name is unique only within a city, so name + city disambiguates.

**Rejected on measurement:** full postal addresses appear **only on the pages
that already carry company links**. Of the seven link-free pages, none has a
postcode or street; three carry a city, four carry nothing but the name. The
chain cannot start where it is needed.

#### R2: Feed raw HTML to the model instead of cleaned text

Would let the model see `href` attributes directly.

**Rejected:** raw pages in this corpus run to 800 KB against 1,500-13,000
tokens of cleaned text, a 10-40× increase that no 8k context can absorb, and
chunking it would multiply cost accordingly. It also does not solve the
problem: the href on a member entry is usually the *profile* URL, not the
company's website, so the model would confidently return association URLs.

#### R3: Single stage covering directory and profile pages together

Concatenate the directory page and every member profile into one prompt.

**Rejected:** ~204 profiles × ~600 tokens ≈ 122,000 tokens for a single
association, far beyond any context window in use and requiring ~20 chunks with
no accuracy benefit over handling profiles individually. It also destroys the
one-company-per-call property that makes profile extraction reliable.

#### R4: Hand-written parsers per association

Deterministic and exact for any site it covers.

**Rejected:** 300 networks would require 300 parsers, each breaking on redesign.
This is precisely the per-site engineering cost the thesis proposes to
eliminate, and adopting it would undercut the central claim. Generic
format-based extraction (postcode shape, outbound non-social link, email
pattern) achieves the same result without site-specific code.

#### R5: Paid search APIs as the primary route

Google Custom Search, Serper.dev, Brave.

**Rejected as primary, retained as last resort:** superseded by `ddgs`, which
is free. An earlier assessment in this document priced ~15,000 lookups at
$15-75 and treated cost as the deciding factor; with a free library available
the deciding factor is result quality, not price.

### Recommended pipeline

```
Stage 1  directory page   LLM       -> names, + URL where printed      (D1)
Stage 2  profile pages    LLM       -> website, address, email         (D2)  ~204 companies
Stage 3  domain construct heuristic -> website                         (D4)  ~60% of remainder
Stage 4  ddgs + LLM rank  free      -> website                         (D3b) most of the rest
Stage 5  database lookup  local     -> website                         (D5)  when access exists
         every stage ends with V1, plus V2/V3 where available
```

Ordered by cost and reliability, cheapest first, so the expensive routes only
ever see what the cheap ones could not resolve. The share resolved at each
stage is itself a reportable result, and it is the honest way to decide whether
a paid route is needed at all rather than estimating coverage in advance.

---

## 3.11e Extraction schema extended to the full company record

Agreed across the meetings of 2026-08-12 (Hafiz), 2026-08-12 (Hafiz + Yusif)
and 2026-08-13 (Hendro). Two independent requirements converge on one schema:

- **Hendro (06.08):** the deliverable needs each member's website beside its
  name, obtained in a single pass.
- **Marco (07.08), restated by Yusif (12.08):** a German company name is unique
  only within a city, so Neovation's record matching needs a disambiguating
  attribute. Yusif: *"in case you are able to get any extra information apart
  from the name, address, city, country"*, the later stage can resolve the URL
  from name plus that data.

The schema is therefore:

```json
{"name": "", "url": "", "street": "", "postcode": "",
 "city": "", "phone": "", "email": ""}
```

Only `name` is required. The prompt forbids inference explicitly: a fabricated
address is worse than a blank one, because it looks correct, will not be caught
by eye, and would corrupt exactly the field the record matching depends on.

### Measured behaviour

Two page types, one strategy (`few_shot_full_record`, `llama3.1:8b`):

| Page type | Result |
|---|---|
| Profile page (Automotive Nordwest, 598 tokens) | 1 record, **all seven fields correct**, 17.3 s |
| Directory listing (BDEW, 42 members) | 42 records, 40 with URL, 67 s |

The directory result is the more informative one. Field population across its
42 records:

```
name 42   url 40   street 2   postcode 0   city 2   phone 0   email 0
```

**BDEW's listing prints no addresses, and the model left those fields empty
rather than inventing plausible German ones.** This is the abstention behaviour
the "never infer" rule targets, and it is the failure mode that would be
invisible without checking, 42 fabricated postcodes would look entirely
reasonable in a spreadsheet.

### Implementation notes

- `ExtractionResult` now carries `records: list[dict]` beside the existing
  `companies: list[str]`. Names remain plain strings so **scoring and the
  scoring is unchanged**, and Stage A results stay comparable across all
  strategies.
- Three response shapes are accepted and normalised, bare string,
  `{name, url}`, and the full record, because the strategies are compared
  against each other and a parsing difference would surface as an apparent
  accuracy difference.
- Constrained decoding requires a **second JSON schema**: forcing the
  name-only schema on a record strategy would strip every field except the
  name. `config.COMPANY_RECORD_SCHEMA` is selected automatically for
  strategies listed in `prompts.RECORD_STRATEGIES`.
- Field aliases are tolerated (`website`/`web`/`homepage` → `url`,
  `plz`/`zip` → `postcode`, `ort` → `city`), since small models drift between
  English and German key names.

---

## 3.11f Division of work and remaining obstacles (meetings 12-13 Aug)

### The link problem became a data task, not a code task

Hendro (13.08) settled the approach: the merged file needs **a new column
holding the URL that opens the member list directly**, not the network
homepage, *"we need to put the link where it directly opens the list"*.

Yusif and Diego own that column, produced with an AI first draft followed by
manual verification. Yusif's framing: an LLM alone is not reliable enough for
links, *"so there is actually no other way rather than doing some manual
work"*.

This removes link acquisition from the thesis scope entirely. Stated
explicitly to Hafiz (12.08) and unchallenged: **the thesis is the model and
prompt comparison; obtaining the network URLs is upstream data preparation.**

Hendro added a durable requirement: the prompt used to find those links should
be reusable, so that networks added later can be resolved without repeating the
manual pass.

### Corpus will be smaller than 817, deliberately

Yusif, with Marco's prior agreement: networks that publish no member list are
skipped, because there is nothing to extract. He put the useful floor at
**50-100 networks**, not 800. Coverage is therefore a reporting figure, not a
target.

### Newly discovered obstacles

Hafiz's audit of the merged file's links found three failure classes beyond
those in §3.1:

1. **Links that cannot be opened at all**: dead or certificate-rejected.
2. **Links whose destination does not match the network name**: the row and
   the site disagree.
3. **Directories with no member link anywhere**: not in the anchor text, not
   in the logo. One page showed roughly 70 members with links on only a
   handful, the rest being plain images. These are true outliers with no route
   except search.

### Cloud models likely dropped

Hafiz reports Gemini Pro produces poor extraction with hallucinated links.
Notably he found **Claude's free tier outperformed Gemini Pro** on link
finding, and that supplying the URLs as plain strings in the prompt is cheaper
than attaching a spreadsheet, because the file must be read first. He also
moved to batches of 5-10 networks rather than one large run.

Decision pending with Marco. If cloud is dropped, the thesis's local-model
framing strengthens: the cloud comparison would then rest on Hafiz's
measurements rather than being an untested assumption.

### Downstream phase now defined

Hendro outlined what follows extraction: the **innovation index weights**,
derived with the **Best-Worst Method** from a survey of companies, following a
previous thesis whose R code and dataset he will share. Six dimensions, with
*digital innovation signal* likely to be cut as measuring digitalisation rather
than innovation. Not part of this thesis, but it fixes what the extracted data
is ultimately for.

### Blocker

CKL access was upgraded on 13.08 but the environment failed to start, 
*"Environment setup failed. Insufficient resources"*, placing the session in a
queue. GPU capacity is allocated, not reserved. Hendro and Hafiz additionally
need account upgrades before they can assist.

---

## 3.11g Pipeline simplifications (2026-08-14)

**The Neovation filter was removed entirely.** It had already been made
non-destructive, annotating rather than dropping names, but Marco's position
that filtering belongs at database-insert time makes it out of scope. Removing
it costs nothing measurable: precision, recall, F1, latency and JSON validity
were all scored on raw model output and are unaffected. The analysis it
produced is retained in section 4.

One function was kept and moved into `benchmark.py`: legal-suffix stripping.
That is **name normalisation for scoring**, not filtering. The page prints
`Siemens AG` where the model may return `Siemens`, and counting that as an
error would measure formatting rather than extraction.

**The results schema was trimmed from 33 to 27 columns.** Four filter columns
went with the filter. Three more were dropped as carrying no information:

| Removed | Reason |
|---|---|
| `url_type` | constant (`member_list`) across all ten pages |
| `num_ctx` | constant (8192); never varied |
| `was_chunked` | restates `n_chunks > 1` |

**One column was added: `page_completeness`.** It records the alphabet-coverage
verdict for the source page, so a result can be traced back to a truncated
page without re-deriving anything:

```
039 ok            18 initials, 43 names
009 TRUNCATED?     1 initial,  37 names   (BDEW, letter-A page)
012 TRUNCATED?     2 initials, 48 names   (BVMed, page 1 of N)
040 TRUNCATED?     1 initial,  17 names   (Medical Valley, page 1 of 14)
050 ok            22 initials, 283 names
```

It flags exactly the three pages independently established as single pages of
longer directories. Beyond debugging, it gives a clean split for RQ3:
**accuracy on complete versus truncated pages**, which is a genuine
performance-by-website-characteristic analysis at no extra cost.

---

## 3.11h Cloud comparison: usage ceilings as a finding (meeting 2026-08-14)

Hafiz's cloud attempts produced a result worth reporting in its own right.

Working through a chat interface, he processed networks in batches of one, two,
three and five. **Six networks completed.** A batch of six exhausted his token
allowance; the same happened across several trial accounts, and after buying a
Pro subscription. His conclusion: *"the best way is just to building the local
llm to get the links and the names of the company."*

Marco identified the cause as the harness rather than the model: *"have you
tried it through an API call… then you can loop everything"*, and *"the
complexity of the task is not that high if you only give one link and ask to
list the members of that link."* That is the design `benchmark.py` already
uses: one page per call, in a loop, resumable.

Two things follow.

**A reportable constraint.** The 540-run grid in this thesis is not merely
cheaper on local models, it is **infeasible on a consumer cloud subscription**.
Six networks exhausted a Pro plan. Usage ceilings are a deployment property
that separates local from hosted models independently of accuracy, and belongs
in the RQ4 trade-off discussion alongside runtime and hardware.

**A comparability requirement.** Marco: *"if you're comparing online LLMs and
offline LLMs you have to use the same prompt to be comparable."* All prompt
templates were therefore exported verbatim from `prompts.py` to
`results/PROMPTS_for_Hafiz.txt`, together with the decoding settings and a
description of the cleaned input format. Any cloud result measured this way is
directly comparable against the local runs, since the pages and the ground
truth are shared.

---

## 3.11i Link annotation improves name extraction (unintended, measured)

Link preservation was added so the model could return a company website
(3.10). It also improved extraction of the **names**, substantially, on
densely formatted pages.

Controlled comparison, same model, same prompt strategy, same cached page,
same annotations, temperature 0:

| | raw | precision | recall | F1 | chunks |
|---|---:|---:|---:|---:|---:|
| Without link annotation | 235 | 0.914 | 0.723 | 0.807 | 2 |
| With link annotation | 297 | 0.993 | **0.997** | **0.995** | 3 |

Ground truth is 296 companies. **Recall rose from 0.723 to 0.997.**

Note that the annotated page is *larger* (+30% tokens) and split into *more*
chunks (2 → 3), so this is not a chunking effect, the harder configuration
scored better.

### Mechanism

SPECTARIS prints each member as an undelimited four-line block:

```
2mag AG
80992 München
Konrad-Adenauer-Straße 15
Web <http://www.2mag.de>     <- record boundary
```

Before annotation the model had to infer where one entry ended and the next
began, from lines that all look alike. That is the same page where zero-shot
previously returned 54 city names and scored F1 = 0.000 (3.7). The trailing
URL acts as a per-record delimiter, and the ambiguity disappears.

The finding generalises beyond this corpus: **markup that a text-extraction
step discards can carry structural information the model needs**, independently
of whether that markup is itself wanted in the output.

### Consequence for the hardware comparison

The laptop and GPU runs used **different input**: the laptop run predates link
annotation. They are therefore not a controlled hardware comparison for
accuracy, and only weakly comparable for latency, since the annotated pages are
~30% larger.

What remains comparable:

- **tokens per second**, which normalises for input size and is the honest
  hardware measure.
- **Accuracy across models and prompts within the GPU run**, which is what
  RQ1-RQ3 actually ask.

The laptop results should be reported as a separate, earlier configuration,
not as the consumer-hardware arm of a matched pair. Claiming otherwise would
attribute an input change to hardware.

---

## 3.12 Project documentation requirement

NeoHub is grant-funded and must file an annual report describing what was done
and why. Marco will circulate a template; the expectation is a running record
updated every one to two months rather than reconstructed at year end, and he
explicitly asked that it include **approaches that did not work**.

This document already serves that purpose and contains the negative results:
the multi-stage prompting failure (§3.8), the pagination-detector that was
wrong in both directions (§3.3), the extraction pipeline that could not return
URLs (§3.10), and the address-availability limit above.

---

## 3.13 Full benchmark grid on GPU hardware (2026-08-25): primary results

The complete Stage A grid finished on the shared A100 slice. This is the
definitive result set for RQ1 to RQ3 and supersedes the laptop numbers in
§3.7 and §3.8, which were produced before link annotation was added (§3.11i)
and therefore ran on different input.

**Grid:** 3 models x 3 prompt strategies x 2 JSON modes x 10 pages x 3
repetitions = **540 runs**. Temperature 0, seed 42, `num_ctx` 8192,
`keep_alive` 10m, models looped outermost. Raw results in
`RESULTS-Final.csv` (27 columns).

### Ranking, all 18 configurations

| model | prompt | JSON | P | R | F1 | s/page | failed |
|---|---|---|---:|---:|---:|---:|---:|
| llama3.1:8b | zero_shot | prompt_only | 0.983 | 0.978 | **0.981** | 26 | 0/30 |
| llama3.1:8b | zero_shot | constrained | 0.982 | 0.978 | 0.980 | 26 | 0/30 |
| llama3.1:8b | few_shot_schema | constrained | 0.977 | 0.942 | 0.955 | 24 | 0/30 |
| llama3.1:8b | few_shot_schema | prompt_only | 0.977 | 0.933 | 0.950 | 23 | 0/30 |
| qwen2.5-coder:7b | zero_shot | prompt_only | 0.982 | 0.906 | 0.933 | 23 | 0/30 |
| qwen2.5-coder:7b | generic_multi_stage | prompt_only | 0.981 | 0.849 | 0.896 | 48 | 0/30 |
| qwen2.5-coder:7b | zero_shot | constrained | 0.979 | 0.850 | 0.882 | 287 | 3/30 |
| qwen2.5-coder:7b | generic_multi_stage | constrained | 0.984 | 0.822 | 0.870 | 307 | 3/30 |
| llama3.1:8b | generic_multi_stage | constrained | 0.987 | 0.765 | 0.845 | 53 | 0/30 |
| llama3.1:8b | generic_multi_stage | prompt_only | 0.987 | 0.764 | 0.845 | 54 | 0/30 |
| qwen2.5-coder:7b | few_shot_schema | constrained | 0.949 | 0.763 | 0.779 | 12 | 0/30 |
| qwen2.5-coder:7b | few_shot_schema | prompt_only | 0.948 | 0.763 | 0.779 | 11 | 0/30 |
| gemma4:12b | generic_multi_stage | constrained | 0.689 | 0.535 | 0.537 | 362 | 14/30 |
| gemma4:12b | generic_multi_stage | prompt_only | 0.660 | 0.502 | 0.506 | 357 | 15/30 |
| gemma4:12b | zero_shot | prompt_only | 0.432 | 0.271 | 0.277 | 246 | 22/30 |
| gemma4:12b | few_shot_schema | prompt_only | 0.408 | 0.270 | 0.275 | 276 | 22/30 |
| gemma4:12b | zero_shot | constrained | 0.430 | 0.270 | 0.275 | 255 | 22/30 |
| gemma4:12b | few_shot_schema | constrained | 0.398 | 0.238 | 0.244 | 269 | 23/30 |

Pooled by model:

| model | P | R | F1 | tok/s | failed |
|---|---:|---:|---:|---:|---:|
| llama3.1:8b | 0.982 | 0.893 | 0.926 | 30.8 | 0/180 |
| qwen2.5-coder:7b | 0.970 | 0.825 | 0.856 | 31.1 | 6/180 |
| gemma4:12b | 0.503 | 0.348 | 0.353 | 20.0 | 118/180 |

### RQ1: best configuration

**`llama3.1:8b` + `zero_shot` + `prompt_only`, F1 0.981** (P 0.983, R 0.978),
26 s/page, no failures in 30 runs. Per page:

| page | organisation | tokens | chunks | P | R | F1 | s |
|---|---|---:|---:|---:|---:|---:|---:|
| 004 | Automotive Nordwest | 1014 | 1 | 0.970 | 0.970 | 0.970 | 12 |
| 005 | automotive thüringen | 4873 | 2 | 1.000 | 0.992 | 0.996 | 46 |
| 009 | BDEW | 827 | 1 | 0.976 | 0.954 | 0.965 | 12 |
| 012 | BVMed | 912 | 1 | 1.000 | 1.000 | 1.000 | 14 |
| 025 | German Water Partnership | 2872 | 1 | 0.929 | 0.929 | 0.929 | 4 |
| 032 | InnoZent OWL | 1149 | 1 | 0.962 | 0.962 | 0.962 | 26 |
| 039 | Life Science Nord | 469 | 1 | 1.000 | 1.000 | 1.000 | 15 |
| 040 | Medical Valley EMN | 1943 | 1 | 1.000 | 1.000 | 1.000 | 6 |
| 043 | NMWP.NRW | 722 | 1 | 1.000 | 0.980 | 0.990 | 18 |
| 050 | SPECTARIS | 9383 | 3 | 0.993 | 0.997 | 0.995 | 100 |

**Determinism.** Standard deviation of F1 across the three repetitions is
exactly 0.000 on every one of the ten pages. At temperature 0 with a fixed
seed, Ollama reproduces output bit-for-bit. The three repetitions therefore
measure nothing about variance and only cost wall-clock time. Report this as
a reproducibility property, and note that repetitions would only become
informative at non-zero temperature.

### RQ2: prompting, and a caution about aggregate means

Pooled across the two working models:

| strategy | P | R | F1 | s/page |
|---|---:|---:|---:|---:|
| zero_shot | 0.982 | 0.928 | 0.944 | 90 |
| few_shot_schema | 0.963 | 0.850 | 0.866 | 18 |
| generic_multi_stage | 0.985 | 0.800 | 0.864 | 116 |

This **reverses the laptop result**, where few-shot beat zero-shot (0.957 vs
0.919). The reversal is real but its cause is narrower than the aggregate
suggests. Comparing the two strategies page by page for llama:

| page | tokens | zero_shot F1 | few_shot F1 | delta |
|---|---:|---:|---:|---:|
| 004 | 1014 | 0.970 | 0.970 | 0.000 |
| **005** | **4873** | **0.996** | **0.687** | **+0.309** |
| 009 | 827 | 0.965 | 0.965 | 0.000 |
| 012 | 912 | 1.000 | 1.000 | 0.000 |
| 025 | 2872 | 0.929 | 0.929 | 0.000 |
| 032 | 1149 | 0.962 | 0.962 | 0.000 |
| 039 | 469 | 1.000 | 1.000 | 0.000 |
| 040 | 1943 | 1.000 | 1.000 | 0.000 |
| 043 | 722 | 0.990 | 0.990 | 0.000 |
| 050 | 9383 | 0.995 | 0.995 | 0.000 |

**Nine of ten pages are identical.** The entire 0.031 aggregate gap comes from
page 005. With a ten-page corpus one page moves the mean by 0.03, which is
larger than most of the differences being compared. This is a direct argument
for the guideline's 30 to 60 page target and must be stated in the limitations
rather than buried.

The page-005 mechanism is nonetheless informative. Few-shot output there:

| | raw | TP | FP | FN | P | R |
|---|---:|---:|---:|---:|---:|---:|
| zero_shot | 124.2 | 122.8 | 0.3 | 1.2 | 0.997 | 0.991 |
| few_shot_schema | 78.3 | 73.3 | 4.2 | 50.7 | 0.946 | **0.591** |

Precision holds; recall collapses. The model stops after roughly the number of
items the worked example contains instead of exhausting the page. Few-shot
examples anchor **output length** as well as output format, and on a
multi-chunk page that anchoring truncates the answer. The effect is invisible
on single-chunk pages with short member lists, which is why the laptop run
(pre-annotation, different chunking) ranked the strategies the other way.

`generic_multi_stage` again loses on recall (0.800) at the highest cost
(116 s/page), confirming §3.8 on different hardware and different input. Its
precision is the best of the three (0.985), so the filtering stage does work.
It removes correct answers along with wrong ones.

### RQ3: constrained decoding is nearly free, except when it is not

For llama and gemma, constrained decoding costs nothing measurable in either
accuracy or latency. For **qwen it is catastrophic on large inputs**:

| model | page 039 (469 tok) | page 050 (9383 tok) |
|---|---|---|
| llama3.1:8b | 22s → 22s (x1.0) | 139s → 141s (x1.0) |
| gemma4:12b | 262s → 269s (x1.0) | 254s → 221s (x0.9) |
| qwen2.5-coder:7b | 23s → 30s (x1.3) | **68s → 1826s (x26.8)** |

All six qwen failures in the entire 540-run grid are the same case: page 050,
constrained mode, latency 2690 to 2769 seconds (about 45 minutes), and the
output is still unparseable. The grammar-constrained sampler degrades
super-linearly with the size of the partially-built JSON array, and page 050
is the only page large enough to expose it.

Practical reading: constrained decoding is the safer default because it
eliminates the repair layer (repair was invoked 66 times for qwen and 9 times
for llama in prompt-only mode), but it is not free and the cost is
model-specific. A production system should keep a latency ceiling and fall
back to prompt-only with repair.

### gemma4:12b: runaway generation, not a code fault

gemma4 failed **118 of 180 runs**. The diagnosis is unambiguous.

*It is not the code.* On the nine pages where gemma4 failed, llama3.1 failed
0 times in 162 runs, using the same cleaner, the same prompts, the same
schema, the same parser and the same cached HTML.

*The mechanism is failure to terminate.* Single-stage runs, mean tokens:

| page | input | gemma4 output | llama output | sum | gemma4 failures |
|---|---:|---:|---:|---:|---:|
| 004 | 2627 | 5015 | 368 | 7642 | 6/12 |
| 005 | 8819 | 836 | 1082 | 9655 | 12/12 |
| 009 | 1538 | 6277 | 375 | 7815 | 10/12 |
| 012 | 2264 | 1579 | 400 | 3842 | **0/12** |
| 025 | 2124 | 6068 | 118 | **8192** | 12/12 |
| 032 | 1398 | 6794 | 796 | **8192** | 12/12 |
| 039 | 2466 | 2165 | 454 | 4631 | **1/12** |
| 040 | 1512 | 6680 | 175 | **8192** | 12/12 |
| 043 | 798 | 7394 | 575 | **8192** | 12/12 |
| 050 | 14919 | 3450 | 2852 | 18368 | 12/12 |

On four pages the token sum is **exactly 8192**, the configured `num_ctx`.
The clearest case is page 043: input 798 tokens, gemma4 emits **7394** output
tokens where llama emits 575 for the same page at F1 0.990. The correct answer
fits in well under 600 tokens. gemma4 generates twelve times that and is cut
off mid-array, leaving unparseable JSON.

Where it does terminate it is accurate: page 012 F1 0.997, page 039 F1 0.944.
So the model can do the task. It usually does not stop doing it.

**Anticipated objection, and the decision taken.** The failures occur at the
configured context limit, so the obvious question is whether a larger
`num_ctx` fixes it. A 32k confirmation run was considered and **deliberately
not performed** (decision: Giorgi, 2026-08-26). The reasoning is in the page-043
numbers: the model was given 7,400 tokens of room for an answer that needs
under 600, and used all of them. The constraint that binds is not the size of
the window but the model's failure to stop filling it, and a larger window
moves that ceiling without changing the behaviour.

The claim must therefore be scoped precisely. What the data supports:

> Under the context budget that fits alongside three models on the target
> hardware (`num_ctx = 8192`, §3.4), gemma4:12b failed on 66% of runs by
> generating until the window was exhausted, while an 8B model on identical
> input failed on none. Where gemma4 did terminate it was accurate
> (F1 0.997 on page 012), so this is a control failure, not a capability
> failure.

What it does not support: "gemma4 cannot extract company names". Stating the
context setting alongside the result is what makes the finding defensible, and
it costs nothing, since 8192 was itself chosen for a documented hardware
reason rather than arbitrarily.

**The headline finding stands either way: parameter count did not predict
extraction quality.** The 12B model placed last on every strategy and both
JSON modes, behind two models roughly half its size, and was also the slowest
(20.0 tok/s against ~31). For a thesis comparing *local* models under
deployment constraints, that is the more useful result than a rescued score
would have been.

**Secondary observation.** `generic_multi_stage` is gemma4's *best* strategy
(F1 0.537, 14 failures) while it is the worst strategy for both other models.
Splitting the work into two smaller calls gives the runaway less room to
develop per call. This is consistent with the termination diagnosis and is not
evidence that multi-stage prompting is otherwise useful.

### Hardware note

Mean throughput: qwen 31.1 tok/s, llama 30.8 tok/s, gemma4 20.0 tok/s. Per
§3.11i the laptop and GPU runs used different input and are not a controlled
hardware comparison for accuracy. Tokens per second remains the defensible
cross-hardware measure.

---

## 3.13b Why the grid produced no company URLs, and what closing that costs

Hendro asked after the previous run that company websites be included
(2026-08-06). They are still absent from the exported spreadsheet. The reason
is a scope decision, not a bug, but the decision was wrong for the thesis and
is being reversed.

### What actually happened

Three separate things, and only the third is the problem.

1. **The URLs were in the model's input.** `PRESERVE_LINKS = True`, and
   `annotate_links()` writes every outbound href inline as `Name <https://url>`
   before `get_text()` (§3.11i). Every benchmarked run saw the links.
2. **The extraction code can return them.** `few_shot_with_url` and
   `few_shot_full_record` exist, are wired to `COMPANY_RECORD_SCHEMA` for
   constrained decoding, and were verified working (§3.11e): on BDEW,
   42 records with 40 URLs populated, and empty address fields left empty
   rather than invented. `export_deliverable.py` already writes the
   `company website` column from those records.
3. **The grid did not run them.** The benchmark loops only the three
   guideline strategies (P1/P2/P3, §3.7), all of which request a flat list of
   names. `ExtractionResult.records` is therefore empty for all 540 runs, and
   the exporter writes a blank column because it is given nothing to write.

So the model was shown the links, was capable of returning them, and was never
asked. **The spreadsheet is an accurate rendering of what was measured.**

### Why this has to be fixed rather than annotated around

The tempting shortcut is to leave the benchmark alone and run the URL strategy
only for the deliverable. That would be a methodological error, for the reason
already set out in §3.11c: adding a second field changes the task. Input grows
26-48%, output roughly doubles, chunk boundaries move, and the task becomes
**relational**: the model must bind a URL to the correct company rather than
merely recognise a name. On pages where the link sits three lines below the
name, that is a different skill.

The consequence is that **the §3.13 winner is the winner for name extraction
and cannot be assumed to be the winner for name+URL.** There is a concrete
reason to expect movement: `qwen2.5-coder` is the code-specialised model, lost
on names, and multi-field structured JSON is closer to its training. Shipping
a deliverable built on the untested assumption that the ranking transfers
would put an unmeasured claim at the centre of the results chapter.

### Scoring URLs needs no new ground truth

The ten hand-labelled pages contain names only, which is why the record
strategies were excluded in the first place. That exclusion was unnecessary:

- **Names** score exactly as they do now, against the existing ground truth.
  The comparison of interest is whether name F1 *degrades* when the model is
  also asked for a URL. That is measurable today, on the corpus as it stands,
  and it is the question Hendro's request actually raises.
- **URLs** are verifiable without annotation. A returned URL either appears in
  the cached HTML for that page or the model invented it. Hallucination rate
  and coverage rate are both computable automatically. This is the field-level
  accuracy the guideline asks for at zero annotation cost.

Precision on a URL is worth more than recall: a blank cell is a task for the
resolution pipeline (§3.11d), a wrong URL is a wrong record in Neovation's
database that nobody will catch.

### Cost

Two grid arms (`few_shot_with_url`, `few_shot_full_record`) x 2 JSON modes x
10 pages x 1 repetition x 2 working models = 80 runs. gemma4 is excluded on
the §3.13 result. Repetitions drop to 1 because temperature 0 with a fixed
seed was shown to be bit-for-bit deterministic. At the measured ~26 s/page for
llama and roughly double for record output, this is about two hours, not a
re-run of the full grid.

The three guideline strategies do **not** need re-running. Their numbers stand
and answer RQ1-RQ3 as posed. This is an additional arm answering a fourth
question: what does asking for the URL cost?

---

## 3.13c A silent bug in link preservation, found while building the URL arm

Building the URL arm exposed a defect that had been suppressing company links
for the entire project. It is worth reporting in full, because the failure was
invisible in every metric being tracked.

### Symptom

The first URL-arm run returned 52 company names at F1 1.000 and **zero URLs**.
Since the whole point of the arm is the URL, the obvious question was whether
the page had any. It did not. Neither did six others:

| page | organisation | outbound member links |
|---|---|---:|
| 004 | Automotive Nordwest | 0 |
| 005 | automotive thüringen | 129 |
| 009 | BDEW | 41 |
| 012 | BVMed | 0 |
| 025 | German Water Partnership | 1 (cookie policy, not a member) |
| 032 | InnoZent OWL | 0 |
| 039 | Life Science Nord | 0 |
| 040 | Medical Valley EMN | 0 |
| 043 | NMWP.NRW | **0, wrong, see below** |
| 050 | SPECTARIS | 298 |

Page 043 was the anomaly. Its raw HTML carries 53 outbound links, roughly 33
of them member domains (`effing-aachen.de`, `ctc-composites.com`,
`chemcologne.de`), yet the cleaner emitted none.

### Cause

`clean_html()` decomposed `config.STRIP_TAGS` **before** calling
`annotate_links()`, and `img` is in that list. NMWP lists its members as logo
links:

```html
<a href="https://effing-aachen.de"><img alt="Effing GmbH"></a>
```

With the image already gone, `a.get_text()` returns empty, the recovery branch
`img = a.find("img")` finds nothing, and the anchor is skipped by the
`if not text` guard. The branch written specifically to handle logo links
could never execute, because the images it depended on were removed one step
earlier. Measured: `nav` cost 2 links, `header` 1, and **`img` cost 27 of 29**.

This is the case Giorgi identified from the pages themselves early on
("the links are embedded in their logos"). The handling was implemented; the
ordering made it dead code.

### Why nothing caught it

Every metric in the benchmark was a name metric. Page 043 scored F1 0.990 on
names throughout the 540-run grid, because the member names are also present
as plain text elsewhere on the page. A page can therefore look like one of the
best results in the study while silently discarding every link on it. **The
absence of a signal is not measured by any of precision, recall or F1**, which
is the general lesson: a field nobody scores is a field nobody notices is
missing.

### Fix and blast radius

`annotate_links()` now runs before any tag removal. Anchors inside
`nav`/`header`/`footer` are still discarded, since decomposing those elements
removes the appended annotation with the rest of the subtree.

The correction is surgical. Re-cleaning all ten ground-truth pages and
comparing byte-for-byte against the old output:

| | pages |
|---|---|
| Identical output | 004, 005, 009, 012, 025, 032, 039, 040, 050 (**9 of 10**) |
| Changed | 043 only: 276 → 436 words, 0 → 27 links |

**The 540-run grid therefore remains valid on nine of ten pages.** Only page
043 was re-run.

### Cost of the fix, measured

Recovering the links also recovers the `alt` text as visible content, which is
not free. On page 043, llama3.1 + zero-shot + prompt-only:

| | words in | name F1 |
|---|---:|---:|
| Before fix | 276 | 0.990 |
| After fix | 436 | 0.959 |

A 0.031 drop in name F1 in exchange for 27 company URLs on a page that
previously yielded none. For the thesis this is a trade to report rather than
hide: **link preservation is not a pure gain.** §3.11i measured the other
direction, where annotation improved recall from 0.723 to 0.997 by acting as a
record delimiter. Both effects are real, and which dominates depends on
whether the page's markup uses links structurally or decoratively.

For the deliverable the trade is clearly worth taking, since a missing URL
cannot be recovered downstream without a fetch per company (§3.11b Route 1),
whereas a slightly noisier name list is still filtered at insert time.

### The larger limit this exposes

Even after the fix, **only 4 of 10 ground-truth pages carry any outbound
member links at all.** The other six link their members to *internal* profile
pages: 89 internal links on Automotive Nordwest, 133 on BVMed, 123 on
InnoZent OWL, 91 on Life Science Nord, 62 on Medical Valley. Those are
deliberately excluded by the same-organisation check in `annotate_links()`,
correctly, since a profile page is not a company website.

So single-pass URL extraction has a hard ceiling set by the corpus, not by the
model: on six of ten pages there is nothing on the page to extract, and any
model returning a URL there is fabricating it. This is what `url_fidelity`
measures, and it is why the metric matters more than `url_coverage`.
Full coverage requires the profile-page route (§3.11b Route 1), which is a
second fetch per company and a separate pipeline stage.

---

## 3.13c-2 The multi-stage validator was reading Python syntax, not names

Found while building the record-returning multi-stage variant. It affects a
headline result and the P3 numbers in §3.13 should be treated as provisional
until the strategy is re-run.

### The defect

`_run_multi_stage()` stage 2 returns **records** (`[{"name": "Robert Bosch
GmbH"}...]`), because `_salvage_json()` normalises every strategy's output
into record form. `multi_stage_validate()` then interpolated that list
directly:

```python
"\n".join(f"- {n}" for n in names)
```

So the validation stage, which the guideline specifically requires as the
distinguishing feature of P3, was shown:

```
- {'name': 'Robert Bosch GmbH'}
- {'name': 'Siemens AG'}
```

instead of the company names. It was asked to judge whether a Python dict
repr is a genuine member organisation.

### Why the effect is plausible but not yet quantified

Stage 3's output is intersected with stage 2 by name
(`v["name"].casefold() in allowed`). Three outcomes were possible:

- the model echoes the dict-shaped strings, nothing matches, `kept` is empty,
  and the code falls back to `kept or names` -- no harm;
- the model returns clean names, all match, and validation works despite the
  malformed input;
- the model returns clean names for *some* entries and drops others it could
  not parse, in which case `kept` is a **subset** and recall falls.

The third is consistent with what was measured: P3 has the best precision of
the three strategies (0.985) and by far the worst recall (0.800), and the
§3.8 laptop run recorded recall collapsing from 0.945 to 0.619 with 70 names
per page becoming 32. That was reported as "the validation step deletes
correct entries to appear confident". Part of it may instead be the validator
failing to recognise entries wrapped in dict syntax.

### Second defect in the same function

Stage 3 is asked for names only, and its records were being **returned in
place of** stage 2's. For the names-only strategy that is harmless, since both
carry only a name. For the record variant it would have silently discarded
every website and address stage 2 found. Fixed by filtering stage 2's records
by the validated names rather than returning the validator's own output.

### Re-run result (60 runs, 2026-08-28): the finding is confirmed and was understated

P3 was re-run for all three models under both JSON modes at 1 repetition,
against the archived buggy results in
`results/benchmark_results_540_p3bug.csv`.

| model | mode | precision | recall | F1 | failures |
|---|---|---|---|---|---|
| llama3.1:8b | constrained | 0.987 to 0.986 | 0.765 to **0.720** | 0.845 to 0.824 | 0 to 0 |
| llama3.1:8b | prompt_only | 0.987 to 0.986 | 0.764 to **0.701** | 0.845 to 0.810 | 0 to 0 |
| qwen2.5-coder:7b | constrained | 0.984 to 0.979 | 0.822 to **0.810** | 0.870 to 0.860 | 3 to 0 |
| qwen2.5-coder:7b | prompt_only | 0.981 to 0.975 | 0.849 to **0.839** | 0.896 to 0.891 | 0 to 0 |
| gemma4:12b | constrained | 0.689 to 0.755 | 0.535 to 0.601 | 0.537 to 0.603 | **14 to 0** |
| gemma4:12b | prompt_only | 0.660 to 0.755 | 0.502 to 0.601 | 0.506 to 0.603 | **15 to 0** |

For the two working models the pattern is uniform: **precision is unchanged
(0.98) and recall falls.** A validator that can finally read the names deletes
more of them, and what it deletes was mostly correct. The claim now rests on a
validation stage that receives well-formed input, which is the version that can
be defended.

**Write P3 up as confirmed, with the corrected numbers.** The earlier figures
understated the effect.

### Unexplained: gemma4's multi-stage failures went to zero

gemma4 failed 29 of 60 multi-stage runs before the fix and **0 of 20 after**.
That is not explained yet, and should not be written up until it is.

The obvious hypothesis was prompt size, since `{'name': 'Robert Bosch GmbH'}`
costs roughly twice the tokens of the bare name, and gemma4 fails by exhausting
its context. **The token counts do not support it:**

| | prompt | output | sum |
|---|---:|---:|---:|
| Before fix | 8,154 | 5,792 | 13,946 |
| After fix | 8,086 | 5,354 | 13,440 |

(Summed across the three multi-stage calls.) The prompt fell by 68 tokens,
under 1%. That cannot account for a failure rate going from 47% to zero.

Two other changes are candidates and neither is verified: the repetition count
dropped from 3 to 1, and page 043's cleaned text changed (§3.13c). Neither
should matter at temperature 0 with a fixed seed, where a deterministic failure
ought to reproduce. **Diagnosis needed before this appears in the thesis:**
read the `error` strings in the archived file to see which stage was failing.
If they are `stage2`, the validator fix cannot be the cause and something else
changed.

The same question applies to qwen's `constrained` failures going 3 to 0. Those
were recorded as stage-2 errors on page 050, and the fix only touched stage 3.

**What this does not change: gemma4 remains unsuitable.** Only 29 of its 118
failures were multi-stage. The other **89 were single-stage** (zero-shot and
few-shot), which this bug never touched, so its overall failure rate stays near
half of all runs. What the re-run does establish is that multi-stage is
unambiguously gemma4's best strategy: F1 0.603 with no failures, against ~0.27
for the single-stage strategies. That is consistent with the mechanism proposed
in §3.13, that splitting the work into smaller calls leaves the runaway less
room to develop per call.

zero-shot and few-shot were untouched by this bug and did not need re-running.

### A note on repetitions in the merged dataset

`results/benchmark_results.csv` now holds 3 repetitions for zero-shot and
few-shot and **1 for multi-stage**, because the buggy P3 rows were removed and
replaced. Defensible given the measured determinism (F1 standard deviation
exactly 0.000 across three repetitions on all ten pages), but it must be stated
in the methodology rather than left for a reader to notice.

---

## 3.13d Link taxonomy: what each directory actually publishes per member

Measured across every extracted record (`dump_extractions.py`, `link_status`
column). Each member falls into exactly one of four states:

| status | meaning | next step |
|---|---|---|
| `company_site` | the model returned a company website, and that domain is present in the cached page | none, done in one pass |
| `unverified` | a URL was returned that is **not** in the page text | reject; the model constructed it |
| `profile_only` | no company site in the listing, but the member is linked to a profile page on the association's own site | stage 2: one fetch per member |
| `none` | the member name is plain text with no link of any kind | search or Impressum (§3.11d routes 3-5) |

Across 459 extracted records:

| status | records | share |
|---|---:|---:|
| `none` | 220 | 47.9% |
| `company_site` | 137 | 29.8% |
| `profile_only` | 102 | 22.2% |
| `unverified` | **0** | **0.0%** |

**Zero fabricated URLs.** Every website returned across every run was present
in the source page. The "never infer a domain from a company name" rule in the
record prompts holds, and the abstention behaviour observed on address fields
(§3.11e) extends to URLs. This is the single most important property for the
deliverable: a blank cell is recoverable, a plausible wrong domain is not.

Per page:

| page | organisation | company_site | profile_only | none |
|---|---|---:|---:|---:|
| 004 | Automotive Nordwest | 0 | 33 | 0 |
| 005 | automotive thüringen | 70 | 0 | 2 |
| 009 | BDEW | 40 | 2 | 1 |
| 012 | BVMed | 0 | 0 | 50 |
| 025 | German Water Partnership | 0 | 12 | 0 |
| 032 | InnoZent OWL | 0 | 0 | 79 |
| 039 | Life Science Nord | 0 | 51 | 1 |
| 040 | Medical Valley EMN | 0 | 0 | 20 |
| 043 | NMWP.NRW | 27 | 4 | 67 |

Three distinct directory conventions, roughly equally represented:

1. **Outbound links** (005, 009, 043): the listing links straight to member
   websites. One pass, no further work.
2. **Profile pages** (004, 025, 039): members link to the association's own
   member pages, e.g. `/member/atp-automotive-testing-papenburg`. Verified by
   matching member names against internal anchors: **32 of 33** ground-truth
   names on Automotive Nordwest and **51 of 52** on Life Science Nord resolve
   to a profile URL.
3. **Plain text** (012, 032, 040): member names carry no link at all. Checked
   directly rather than assumed: BVMed has 92 internal anchors, InnoZent OWL
   128, Medical Valley 69, and **not one** has anchor text matching a
   ground-truth member name. Those are navigation. For these 149 companies no
   link exists on the page in any form.

### Consequence for the pipeline design

The three-way split is decided by the page, not the model, and it is decided
**deterministically**. Whether a link points at the association or at a
company is a hostname comparison, which Python does exactly and for free.
Asking a model to classify links would spend tokens to do worse.

So the LLM's job is narrower than it first appears: extract the member name,
and the company URL where the directory prints one. Everything else is
routing:

```
directory page
  |-- model      -> name + company_url        (company_site: 29.8%)
  |-- python     -> name + profile_url        (profile_only: 22.2%)  -> stage 2 fetch
  \-- python     -> name only                 (none:         47.9%)  -> search / Impressum
```

This also corrects a natural but wrong assumption about the current runs:
`annotate_links()` **removes internal links before the model sees the page**,
by design, since a profile page is not a company website. The model therefore
never sees a profile link and cannot be classifying anything. The
`profile_url` column in `extractions_long.csv` is recovered afterwards from
the cached HTML.

### Address, phone and email

These are requested only by `few_shot_full_record`, and only that strategy
populates them. Their emptiness is a property of the corpus: BDEW's listing
prints 42 members with **2 streets, 0 postcodes, 2 cities, 0 phones and 0
emails** (§3.11e). The `field coverage` sheet in `extractions_review.xlsx`
reports this per page and per strategy, so a blank column can be attributed
to the page rather than to the model. Contact details overwhelmingly live on
the profile page or the company's own Impressum, which is stage 2, not
stage 1.

---

## 4b. Relation to Neovation's existing scraper (`scraperng`)

The industry partner maintains a Scrapy-based scraper. Reviewing it supports
the thesis's central claim rather than undermining it.

**It is a single-site scraper.** Its one spider targets firmenregister.de with
hardcoded selectors, `//tr[@valign="top" and @bgcolor]`, fixed cell positions
(`cells[0]`→info, `cells[1]`→address), a fixed query-parameter dictionary and
ISO-8859-1 encoding. Re-targeting it to another site means writing a new spider.
That is exactly the per-site engineering cost this thesis proposes to replace
with a single generic LLM-based extractor. `middlewares.py` and `items.py` are
unmodified Scrapy templates.

**Convergent design, independent validation.** Their spider enumerates
16 Bundesländer × 26 letters to exhaust a paginated search:

```python
for bdl in self.bundeslaender:
    for ch in ascii_lowercase:
```

This is the same technique arrived at independently for BDEW's `?letter=A-Z`
index (§3.2). Their `MIN_EXPECTED_NUMBER_ROWS = 15` guard shares the instinct
behind the alphabet-coverage completeness check (§3.3). Two teams reaching the
same solutions is worth reporting as evidence the approach is sound rather than
ad hoc.

**Adopted from it.** Adaptive throttling, replacing a fixed 2.5 s delay: the
pause now follows measured response latency (1-30 s, doubling after a failure),
so slow hosts get more room and fast ones are not crawled needlessly. Their
`AUTOTHROTTLE` settings were the model.

**Available but not used for reported results.** `scrapy-rotating-proxies` with
a free proxifly list is their answer to 403 blocking. Implemented here as
`proxy_fetch.py`, default off. Any page recovered this way must be reported as
proxy-assisted, since it is not reproducible from a direct request. Rayen's
position (2026-07-31) is that this is in scope because the pages are public and
could be copied by hand.

**Ethics comparison.** Their production settings use `ROBOTSTXT_OBEY = False`,
`CONCURRENT_REQUESTS = 16`, `DOWNLOAD_DELAY = 0.3` and `USER_AGENT = "scraperng"`.
The pipeline reported here is more conservative on every axis: sequential
requests, ≥1 s adaptive delay, robots.txt parsed and logged, and a User-Agent
naming the researcher, institution and contact address.

**Database target.** `pipelines/pgsql.py` writes to `public.company (name,
fr_url, logo_url, jurisdiction_code, registered_address, postalcode,
registered_office, domain, keywords, mail, description, retrieved_at,
retrieved_from)`. Note this does **not** match the ERD circulated by the team, 
the diagram and the running code have diverged, which needs clarifying before
the output CSV is finalised.

---

## 4c. Approaches tried that did not work

Marco asked (2026-08-07) that the project documentation record approaches that
failed, not only those that shipped. They are also the more useful half of a
thesis: each one below was a reasonable idea, and the reason it failed is a
finding about the problem rather than about the attempt.

### Prompting

**Generic multi-stage extraction (locate → extract → validate).** Hendro's P3,
and the most expensive thing tried. It did not merely underperform: it was the
worst configuration in the study, at 11× the runtime of the best.

The mechanism is specific. Adding the validation stage raised llama's precision
from 0.971 to 0.985 and collapsed recall from 0.945 to 0.619, 70 names per
page became 32. **The validation step deletes correct entries to appear
confident.** At 7-8B scale the model cannot reliably distinguish "this looks
uncertain" from "this is wrong", so a second opinion destroys information
rather than refining it.

Reported as an answer to RQ2 rather than as a failed experiment.

Confirmed on the full GPU grid (§3.13) with different input: multi-stage again
has the best precision of the three strategies (0.985) and the worst recall
(0.800), at 116 s/page against 90 s for zero-shot. The one exception is
gemma4, for which multi-stage is the *best* strategy, because two smaller calls
give its runaway generation less room per call. That is a symptom of gemma4's
termination failure, not a defence of the strategy.

**Chain-of-thought as the third strategy.** An earlier draft used CoT for P3.
Replaced once Hendro clarified (2026-07-31) that "generic multi-stage" meant
staged retrieval, not narrated reasoning. Worth noting the incompatibility that
surfaced: CoT emits prose before its JSON, so constrained decoding would have
suppressed the reasoning and silently degraded it into a slower zero-shot, 
that grid cell would have produced a meaningless number that looked valid.

**Two-pass extraction (names, then URLs).** Rejected by Hendro on token cost and
on the name-matching problem a second pass creates. Correct where the page
carries links; see §3.10 for where it is not a choice at all.

### Detection and tooling

**Stripping tags before preserving links.** `clean_html()` removed
`config.STRIP_TAGS` and only then annotated anchors, which made the logo-link
recovery branch unreachable: `img` is in STRIP_TAGS, so the alt text that
carries the company name on logo-based directories was gone before anything
looked for it. Cost 27 of 29 member links on NMWP.NRW and was invisible for
the whole 540-run grid, because that page still scored F1 0.990 on names
(§3.13c). Ordering bug, one-line fix, and a reminder that a pipeline stage
which *removes* information must run after every stage that *reads* it.

**Keyword-based pagination detection.** Scanning HTML for pagination markers was
wrong in *both* directions: BDEW scored 0 (it paginates with plain `?letter=`
URLs, no JavaScript) while SPECTARIS scored 61 from CMS boilerplate despite
listing all 285 members on one page. Replaced by **alphabet coverage of member
initials**, which separates the cases cleanly and needs no network access. Both
original errors were caught by eye during hand-labelling.

**Headless-browser rendering as a universal fix.** Applied to 19 pages showing
pagination markers; it recovered content on 10 and returned *less* than the
static fetch on 7 (BioRN: 15,533 → 170 words), most likely consent walls or bot
detection responding differently to headless Chrome. A guard keeps the larger
document, so nothing was lost, but the assumption that a real browser always
sees more than `requests` is false.

**Candidate extraction from semantic tags only.** The ground-truth worksheet
generator inspected links, list items, table cells and headings, but not
`<span>` or `<div>`. SPECTARIS renders every member name in a bare `<span>`, so
146 of 287 names were missing from the worksheet. Discovered only because a
human noticed entries absent every other line. Fixed by including those tags
restricted to leaf elements.

**Naive legal-suffix stripping.** Short forms were stripped without a word
boundary, so `2mag AG` → `2m`, `Montag GmbH` → `Mont`. Scoring was largely
unaffected (prediction and ground truth mangle identically) but the delivered
`company_name_clean` would have been wrong.

### Data acquisition

**Extracting postal addresses to enable search-based URL resolution.** Marco's
suggestion (2026-08-07), and sound in principle: name + city is unique under
German company law where a bare name is not. Measurement killed it, 
**full addresses appear only on the pages that already carry company links**,
i.e. exactly where they are not needed. Three further pages provide a city;
four provide nothing but the name. See §3.11.

**Search-engine URL resolution.** No free API exists at this scale: Google's
Custom Search allows 100 queries/day before billing, Microsoft has retired the
Bing Search API, and DuckDuckGo publishes no web-results endpoint. Scraping
results directly breaches terms and is blocked quickly. At ~300 networks ×
~50 members this is ~15,000 lookups, and a top result is frequently LinkedIn or
a directory listing rather than the company's own site. Retained only as a last
resort behind three free alternatives.

**Assuming HTTP 200 means the page has data.** 53 of 73 URLs returned 200; only
about 23 were genuine member directories. The rest were news feeds, category
taxonomies, "about us" pages, and in one case (BIO Deutschland) 183 words
consisting entirely of cookie-consent text.

**Sampling the ground-truth set by page size alone.** The first stratified
sample of ten included three pages that were not member directories at all,
chosen because they fetched cleanly and had a plausible word count. Re-drawn
after scoring every page for directory-ness.

### Hardware

**gemma4:12b on 16 GB.** 444.8 s versus 38.3 s for qwen on identical input, 
11.6× slower **and one fewer company found**. The wall clock measures paging,
not inference. Excluded from the ablation grid; a full grid arm would take
40-80 hours. This is a deployment finding worth stating plainly: at this
context size a 12B model is not slower on consumer hardware, it is unusable.

**gemma4:12b on datacentre hardware.** Adding a GPU removed the paging problem
and did not rescue the model. It failed 118 of 180 runs by generating until the
context window was full (§3.13), including on a 798-token page where the
correct answer needs under 600 output tokens and it produced 7394. Two separate
reasons to exclude the same model, on two different machines, for two
unrelated causes. Worth stating together: **parameter count predicted neither
speed nor quality here.**

**Constrained decoding as a universal default.** Assumed safe because it
removes the JSON repair layer. True for llama (no measurable cost) and gemma4,
false for qwen2.5-coder, where the largest page went from 68 s to 1826 s, a
26.8× penalty, and the three-repetition zero-shot cell ran about 45 minutes per
run and still returned unparseable output (§3.13). All six qwen failures in the
540-run grid are this one case. The lesson is that grammar-constrained sampling
cost scales with the size of the structure being built and is implementation-
specific, so it needs a latency ceiling and a prompt-only fallback rather than
being switched on globally.

---

## 5. Limitations

- Ground truth covers 10 pages; the guideline recommends 30-60. This is now
  quantified rather than assumed: the entire zero-shot vs few-shot difference
  in §3.13 comes from **one page out of ten**, and nine pages are identical.
  A single page moves an aggregate F1 by roughly 0.03, which exceeds most of
  the gaps the benchmark reports. Rankings at the top of the table are safe;
  differences under about 0.05 are not resolvable at this corpus size.
- The three repetitions carry no information. Temperature 0 with a fixed seed
  produced F1 standard deviation of exactly 0.000 on all ten pages, so the
  grid measures determinism, not variance. Non-zero temperature would be
  needed to report confidence intervals.
- gemma4:12b was benchmarked only at `num_ctx = 8192`, and a 32k confirmation
  run was deliberately not performed (§3.13). Every gemma4 claim must name the
  context setting. The evidence that the window size is not the real constraint
  is strong but indirect.
- The benchmark grid measured **name extraction only**. Company websites were
  present in the model's input throughout (link annotation, §3.11i) but were
  not requested by any of the three guideline strategies, so no configuration
  in §3.13 was scored on URL extraction (§3.13b).
- Laptop and GPU results are not a matched hardware pair; link annotation was
  added between them (§3.11i). Only tokens/second compares cleanly.
- Three annotation units are single pages of longer directories (BDEW letter A,
  Medical Valley page 1, BVMed page 1).
- 5 sites block automated access (403). Rotating proxies exist in Neovation's
  `scraperng` repository but were not used for the reported results.
- Headless rendering returned *less* content than static fetching on 7 of 19
  pages (BioRN 15,533 → 170 words), most likely consent walls or bot detection.
  The static version was kept in each case.
- The ZIM portion of the merged file (617 networks) mostly lacks usable URLs.

---

## 6. Reproducibility package (guideline activity 11)

| Artefact | Path |
|---|---|
| Pipeline code | `Web_Scraping_Engine/*.py` |
| Prompt templates | `prompts.py` (5 strategies; 3 benchmarked) |
| Model/runtime settings | `config.py` |
| Website corpus snapshot | `results/html_cache/` |
| Fetch outcomes | `results/fetch_manifest.csv` |
| URL health classification | `results/url_health_report.csv` |
| Gold-standard annotations | `data/ground_truth/*.json` |
| Experiment output | `results/benchmark_results.csv` |
| Per-configuration summary | `results/stage_a_summary.csv` |
| Results workbook | `results/Stage_A_Results.xlsx` |
| Deliverable | `results/NeoHub_Network_Members.xlsx` |
| Work-package documentation | `results/NeoHub_Documentation_AP1_Extraction.docx` |
| Prompts shared for cloud comparison | `results/PROMPTS_for_Hafiz.txt` |
| GPU deployment script | `gpu_setup.sh` |

### Packaging the tree for a Linux node (macOS gotcha)

Worth recording because it cost time and looks like data corruption. macOS
`tar` stores extended attributes (`com.apple.provenance`, `com.apple.macl`,
`com.apple.FinderInfo`) as **pax extended headers**. Linux tooling that does
not interpret them extracts each one as a real file, so every `config.py`
arrives with a sibling `PaxHeader/config.py` containing a binary metadata blob.
Measured on this tree: **80 PaxHeader entries for 68 real files**, which
presents as "every file is duplicated" and "the file is not displayed because
it is either binary or uses an unsupported text encoding".

Nothing is wrong with the source files. The fix is at archive time:

```bash
COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata \
    --exclude='.venv' --exclude='__pycache__' --exclude='.DS_Store' \
    --exclude='html_cache*' -czf neohub.tar.gz Web_Scraping_Engine
```

Verify before uploading; the count must be zero:

```bash
gunzip -c neohub.tar.gz | strings | grep -c PaxHeader
```

---

## Labelling progress

- [x] 009 BDEW, 66 names (letter-A unit)
- [x] 004 Automotive Nordwest, 32
- [x] 005 automotive thüringen, 128 (~30 edits; section headings at the end)
- [x] 040 Medical Valley EMN, 22 (page-1 unit, 1 change)
- [x] 043 NMWP.NRW, 48
- [x] 025 German Water Partnership, 14 (member *landing* page, not a directory:
      only new members plus prose. Useful as a low-density precision test, 
      47 candidates reduced to 14. Noise sources on one page: schema.org
      microdata (`Employee`, `Administrator`), nav links (`Satzung`), and an
      unrendered CMS placeholder (`{title}`).)
- [x] 039 Life Science Nord, 51
- [x] 032 InnoZent OWL, 79 (76 entries had a trailing `, City` stripped)
- [x] 012 BVMed, 49 (page-1 unit; 113 candidates reduced to 49)
- [x] 050 SPECTARIS, 296

**Ground truth complete: 761 companies across 10 pages.**

(Counted from `data/ground_truth/*.json`, and it matches the per-page table
below. An earlier draft of this line said 785, which was an arithmetic slip:
the individual page counts were always right, only the total was wrong. Use
761 in the paper.)

Annotation effort worth reporting: the candidate extractor's recall varied
sharply by site markup. On SPECTARIS it found only 161 of 287 names because
member names sit in bare `<span>` elements, which the original tag list did not
inspect, 146 names, over half the directory, were absent until a human noticed
entries missing every other line. The extractor now includes `span`/`div`
restricted to leaf elements. This is a second instance of manual annotation
catching a systematic automated failure (see §3.3).

| page | annotated | note |
|---|---:|---|
| 009 BDEW | 43 | letter-A unit |
| 004 Automotive Nordwest | 33 | |
| 005 automotive thüringen | 125 | section headings at list end |
| 040 Medical Valley | 20 | page-1 unit of 14 |
| 043 NMWP.NRW | 49 | |
| 025 German Water Partnership | 14 | landing page, low density |
| 039 Life Science Nord | 52 | |
| 032 InnoZent OWL | 79 | trailing `, City` stripped on 76 |
| 012 BVMed | 50 | page-1 unit; 113 candidates → 50 |
| 050 SPECTARIS | 296 | testimonials block excluded (14 lines) |
