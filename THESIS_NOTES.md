# Thesis Writing Notes

Running log of findings worth putting in the thesis paper, organised by the
chapter they belong to. Every number here was measured, not estimated, the
command that produced it is noted so results can be regenerated.

Thesis: *Comparative Evaluation of Local LLM Models and Generic Prompt
Strategies for Extracting Company Information from Innovation Network Websites*
Giorgi Pataridze · Constructor University Bremen × Neovation GmbH (NeoHub AP1)

### Status (2026-09-15)

**Everything on the 10 ground-truth pages is complete.** 960 benchmark runs
(§3.13j) and all four pipeline stages, merged into
`results/NeoHub_Network_Members.xlsx`.

**The deliverable holds 752 of the 760 ground-truth companies** (recall 0.989,
precision 0.986), **684 of them with a website (90%)**. See §3.13n. These are
the companies on the saved pages: 4 of the 10 pages are only the first page of
a longer list (§3.14), so this is not those networks' full membership. Until
2026-09-15 it held only 401: the full-record run failed outright on SPECTARIS
and stopped silently at 72 of 124 members on automotive thüringen. The "82%
with a website" reported earlier in §3.13m was a share of the 409 companies in
the file at the time; as a share of all 760 it was 44%. Use §3.13n.

**Two winners, and the difference between them is a finding.** For names only,
`llama3.1:8b` + zero-shot + prompt-only, F1 0.981. For the full record,
`llama3.1:8b` + few-shot + prompt-only, name F1 0.858 and website F1 0.811
with zero fabricated addresses. See §3.13j. The deliverable now uses both
(§3.13n). **Primary results are §3.13**; §3.7 and §3.8 are the earlier laptop
run and are superseded for accuracy, since link annotation (§3.11i) changed
the input between them.

**Multi-stage: use §3.13c-2, not the P3 rows in the §3.13 table.** A validator
bug was found and fixed, and P3 re-run on 2026-08-28. The finding held and grew
stronger. The grid from before the fix is archived as
`results/benchmark_results_540_p3bug.csv`.

gemma4:12b is closed as a negative finding (§3.13): it fails 89 of 120
single-stage runs. Its multi-stage failure rate dropping to zero after the fix
remains **unexplained** and is to be reported as such (§3.13c-2). It is to be
replaced for the 30-page run (advised 2026-09-15: too slow).

**Code sync.** Changed on the laptop on 2026-09-15 and not yet on the GPU:
`link_coverage.py`, `export_deliverable.py`, `test_metrics.py`. The two
copies of `results/link_coverage.csv` still differ (laptop `32220aa7`, GPU
`583642bc`) although every per-page route count is identical; the cause is
not known, and the GPU copy is the reference from now on. Code moves by
tarball, packed with `COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata`,
or macOS metadata arrives as unopenable binary twins of every file.

### Next tasks, in order (2026-09-15)

**1. Copy the three changed files to the GPU** and run `test_metrics.py` there
(68 checks).

**2. DONE (2026-09-26): the ground truth is 30 pages and 2,638 companies.**
Selection method and checks in §3.14; frozen copy in
`data/ground_truth_frozen_2026-09-26/`. Next is the grid over all 30 pages.

**3. gemma4 replaced by `qwen3.5:9b` (decided 2026-09-15).** Next: pull it on
the GPU, run `check_model.py qwen3.5:9b`, a one-page test, then the grid on the
existing 10 pages. Candidates considered on Ollama (checked
2026-09-15): `qwen3.5:9b` (6.6 GB, same size class as the other two, the
fairest comparison) or `qwen3.6:35b-a3b` (23 GB, mixture of experts with about
3B parameters active per token). `qwen3.8:27b` is dense and likely slow.
Thinking mode must be switched off or the model reasons at length before
answering. Two of three models would then be Qwen: frame it as old versus new
generation.

**4. One GPU run over all 30 pages** with the new model, then stages 2 to 4
and the export. Hand-check more than the 14 stage 4 results checked so far.

**5. Production run over the 291 Finalv1 networks.**
HTML already cached at `results/html_cache_finalv1/`. `build_urls.py` still
targets the old 73-URL sheet and needs rewriting for Finalv1 first.

**6. Work-package documentation for Neovation (Marco's report).**
Requirements received 2026-09-22: **at most 10 pages**, general, **no code**
(no script names or file paths either). A summary, not a rigid structure of
timeframes and tasks. It may name the strategies used and their results, for
example: "In June I spent three weeks on X. It did not work because Y, so I
tried Z. The result was W." `make_documentation.py` still produces the older
per-task Goal/Method/Metrics layout (Marco's template of 2026-08-11), which
names a script in every Metrics section, so its output has to be rewritten
into this form before sending. Section 4c already holds the failed approaches
he asked to see.

**7. Cloud comparison (Hafiz).** API access confirmed on 2026-09-15 after
Andrei (Constructor Tech) pointed to the API keys page (§3.13o). The pipeline
now runs cloud models through `cloud_client.py`, and a new bundle for Hafiz
was built. Hafiz needs his own key. Still to ask Andrei: the doubled answers,
and usage limits.

**8. Separate Neovation job (Rayen, 2026-09-15).** Websites and emails for
766,598 UDB companies that have no domain; 5,606 have an email. Free, one to
two days. Plan: domains from existing emails, the Common Crawl domain list
(119.7 million domains), name-based guesses, each confirmed by finding the
company's postcode on its Impressum page. Not part of the thesis.

**Ground truth expansion, no longer deferred.** Deferred on 2026-09-01
(Giorgi); requested by Hendro on 2026-09-15, now task 2 above. Until it is
done every accuracy figure keeps the ten-page caveat in §5, and one page still
moves an aggregate F1 by about 0.03.

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

**Why the same page appears three times in a row.** Decoding was expected to be
deterministic (`temperature=0`, fixed seed), so the three repetitions should
return byte-identical output, with only latency varying (30.4 s, 21.6 s, 21.5 s
on the first block; the first run pays a warm-up cost).

That expectation is mostly right and not entirely: on the GPU grid, 22 of 180
configurations disagreed across identical repetitions (§3.13e). The repetitions
therefore measure both timing variance and, in a minority of cells, genuine
answer variance. They are not redundant.

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

**Determinism, for this configuration only.** Standard deviation of F1 across
the three repetitions is exactly 0.000 on every one of the ten pages *for
llama3.1 + zero-shot + prompt-only*.

**Do not generalise that to the grid.** Measured across all 180 configurations
of the original 540-run grid, 22 of them returned different results across
identical repetitions (§3.13e). Temperature 0 with a fixed seed is not
sufficient for reproducibility on this hardware. The winning configuration
happens to be stable; the grid as a whole is not.

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

## 3.22 ZIM networks versus privately funded networks (2026-10-20)

Marco asked in meeting #21 whether extraction behaves differently on publicly
funded ZIM networks than on privately funded ones, because the scoring work
downstream treats the two separately. The answer has two halves, and they
point in opposite directions.

**Composition of the production database.**

| | rows | distinct companies | networks |
|---|---:|---:|---:|
| ZIM network | 1,876 | 1,641 | 84 |
| Privately funded | 14,226 | 13,235 | 128 |
| **total** | **16,102** | **14,719** | **212** |

The distinct columns do not add up (1,641 + 13,235 = 14,876 against 14,719)
because **157 companies hold membership in both a ZIM and a privately funded
network** and are therefore counted in both groups. The clean partition is
1,484 ZIM only, 13,078 private only, 157 both.

**Extraction accuracy does not depend on funding type.** On the 30 labelled
pages, under the winning configuration:

| funding type | pages | companies | mean F1 |
|---|---:|---:|---:|
| Privately funded | 19 | 2,210 | 0.9763 |
| ZIM network | 7 | 143 | 0.9620 |
| Technical association | 4 | 285 | 0.8954 |

ZIM against all others is a difference of **-0.0002** with a permutation
p-value of **0.997** over 20,000 relabellings, and a 95% bootstrap interval on
the difference of [-0.052, +0.051]. Page size does not predict accuracy either
(r = -0.054 against log company count). This is a clean null result and it is
worth stating as one: the method is indifferent to who funds the network.

**Data availability does depend on it, and significantly.** Per network, over
the 208 production networks with at least three members:

| metric | ZIM | private | difference | permutation p |
|---|---:|---:|---:|---:|
| has a website | 94.4% | 87.2% | +7.1% | 0.001 |
| has a street address | 24.4% | 40.6% | -16.1% | 0.011 |
| has a phone number | 20.2% | 26.1% | -5.9% | 0.289 |
| website came from a profile page | 0.1% | 9.7% | -9.6% | <0.001 |

**Size was tested as a confound and only partly survives.** ZIM networks are
much smaller, a median of 14 members against 74, so an apparent funding effect
could be a size effect. Restricting to networks of 30 members or fewer:

* the website advantage **survives**: ZIM 94.7% against private 85.7%,
  p = 0.002, slightly larger than in the full sample;
* the street-address deficit **does not**: p rises from 0.011 to 0.117, so
  that difference is substantially explained by network size rather than by
  funding.

**One structural difference explains both.** ZIM network pages are small
partner lists that link straight to each member's own website. Privately
funded association directories are larger and link first to their own internal
profile pages, which is where 9.7% of their websites came from against 0.1%
for ZIM, and those profile pages are also where postal addresses live. So ZIM
hands you the website and withholds the address; the private directories do
the reverse.

**Consequence for the downstream scoring.** A score that rewards contact
completeness will systematically under-rate ZIM-sourced companies. That would
be measuring how a network chooses to publish its members, not anything about
the companies themselves, and it needs to be normalised per source or stated
as a known bias.

Analysis written to `Extraction_Results_2026_10/ZIM_vs_Private_Analysis.xlsx`.
Significance throughout is by permutation test rather than a t-test: n is 7
for ZIM at the page level, far too small to assume normality.

---

## 3.21 The production run: 230 networks, 16,102 companies (2026-10-02)

The benchmark answers "which model and prompt". This is the other thing: one
model, one prompt, one pass, to fill Neovation's database. No answer keys, no
grid, no comparison.

**Configuration**: qwen3.5:9b / few_shot_full_record / constrained, chosen by
the record arm (§3.19). Name F1 0.940, website precision 0.999, zero invented
addresses, 2.35 s per company.

**Scope**: the Finalv1 sheet holds 306 networks, 291 with a verified members
URL. `survey_finalv1.py` had already fetched all 291 and sorted them by what
the HTML contains, so the run covers every network whose page returns
content:

| category | networks | in the run |
|---|---:|---|
| directory | 153 | yes |
| sparse | 85 | yes |
| thin | 41 | yes |
| http_error / unreachable | 12 | cannot be fetched |

Including the thin pages was a late change and the right one: "sparse" alone
contributed **1,540 companies, 9.5% of the total**, which excluding it would
have silently lost. The thin pages contributed 25, which proves rather than
assumes that they hold nothing.

Re-fetched on 30 September rather than reusing the August cache, so the
pages are current. 230 of 279 returned usable content: **49 member pages went
down or empty in six weeks**, which is a drift figure for Neovation in its
own right.

### What each stage produced

| stage | | of 16,102 |
|---|---:|---:|
| 1, the model reads the member page | 16,102 names | 100% |
| 1, websites | 9,360 | 58.0% |
| 1, cities / postcodes / streets | 7,051 / 5,550 / 4,421 | 44 / 34 / 27% |
| 2, routing (Python, no model) | 4,769 / 2,881 / 8,452 | 30 / 18 / 52% |
| 3, profile pages, of those readable | 88% website, 88% street | |
| 4, web search, confirmed | 69.6% of those searched | |

**Final coverage: 14,241 of 16,102 companies have a website, 88%.** 865 more
have weak evidence that needs a human, and 949 have nothing.

Runtime 11.3 h wall for stage 1, **100% efficiency again**, 1 failure in 230.

### The production run validated the benchmark

31 of the production networks are also research pages and kept their ids, so
the shipped configuration could be scored against the hand-labelled keys on
the pages the two corpora share:

| | F1 |
|---|---:|
| benchmark, 30 pages, same configuration | 0.940 |
| **production, the 23 scorable pages** | **0.933** |

Seven tenths of a point. The benchmark predicted production almost exactly,
which is the answer to the obvious objection that a method tuned on 30
curated pages will not survive 230 real ones. Part of even that small gap is
likely the web rather than the model: production pages were fetched on 30
September, the answer keys were written against copies cached weeks earlier.

### The headline result: the model doubles what rules achieve

`link_coverage.py` paired **4,769** companies with a website. The model found
**9,360** on the same HTML. Of the model's extras, **3,682 of 3,683
hostnames are present in the page source**, a 0.03% invention rate.

The cause is visible in the markup. The heuristic pairs a link to a company
by matching the link's clickable text to the company name. Directories
routinely write something else:

```
5-HT Chemistry & Health   ->  href="https://www.5-ht.com/">read more
Bioneer A/S               ->  href="https://bioneer.dk/">read more
```

"read more" matches no company name, so a rule files that member as having
no link while the address sits in the same tag. The model reads the entry as
a reader would.

**This is the strongest argument in the thesis for using a language model at
all.** Everything else it does could be argued as convenience. This cannot:
careful rule-based extraction, with a base-href fix, a generic-label list and
a positional fallback, reaches 51% of what the model reaches on identical
input, and fails invisibly by reporting a smaller ceiling rather than an
error.

A consequence for the write-up: the "stage 1 ceiling, 30% have a website
printed on the page" line that `link_coverage.py` prints is false as stated.
It is 30% that *this heuristic can pair*. The wording needs fixing wherever
it appears.

### Three defects the research corpus never showed

All three were assumptions that held on 30 hand-picked pages and broke on 230
real ones.

**Fragment links read as profile pages.** The Leasingverband links all 134
members to `mitglieder.leasingverband.de/#m2`, `#m50`, `#m426`. Composites
United links its 582 to 582 distinct paths that all return the same page.
716 URLs, 3 distinct files. All were routed to the profile stage, skipped
there for exceeding its word limit, and never queued for search because
their route said "profile": **4.4% of the corpus served by nothing**.

A URL rule catches the first case and cannot catch the second. The fix that
works needs no prediction: **stage 4 now also queues anyone stage 3 was
routed to but did not produce a website for.** The general principle is worth
stating in the thesis: *a pipeline stage should not assume the previous stage
succeeded.*

**A listing page shared by many members.** The same check found 19 companies
in the research corpus pointing at one `netzwerkpartner` page. 0.7%, and the
same class of error.

**A whole network dropped for a partial failure.** The deliverable discarded
any run with an error. Page p094 returned 162 companies and then failed on
one chunk, so the eco Verband der Internetwirtschaft appeared nowhere in
Neovation's sheet. A partial extraction is now kept, with a clean run still
preferred over a partial one for the same page.

**And one reporting artefact.** `make_report.py` averaged F1 over all 230
production pages when only 31 have an answer key, printing "best
configuration F1 0.0933". That number described the share of the corpus that
was labelled, not the model. Accuracy is now computed over scorable pages
and the count is printed beside it.

## 3.20 Stage 4 on 30 pages, and the final coverage (2026-09-30)

1,022 companies with no link of any kind, searched and verified. No model:
a search returns candidates and Python decides whether any belongs to the
company.

| outcome | count | share |
|---|---:|---:|
| verified, two or more independent signals | 653 | 63.9% |
| name found on the page only | 170 | 16.6% |
| nothing usable | 70 | 6.8% |
| no result at all | 78 | 7.6% |
| domain resembles the name | 34 | 3.3% |
| **derived from the company's own email, no search** | **17** | 1.7% |
| confirmed | **704** | **68.9%** |

### Where all 2,638 companies end up

| source | companies | share |
|---|---:|---:|
| stage 1/2, website printed on the page | 1,134 | 43.0% |
| stage 3, read off a profile page | 411 | 15.6% |
| stage 4, found by search and confirmed | 704 | 26.7% |
| **total with a website** | **2,249** | **85.3%** |
| stage 4, weak evidence, needs a human | 170 | 6.4% |
| nothing found | 219 | 8.3% |

The projection made before stage 4 ran was 83% to 91%. The outcome is 85.3%,
inside it and near the lower half, which is the useful direction for a
projection to be wrong in.

**No single stage gets past 43%.** The result comes from three different
mechanisms, only one of which uses a model, and the argument for the pipeline
having four stages is this table rather than an assertion.

### The upgrade, and what it was worth

Stage 4 was rebuilt before this run (2026-09-29). It now weighs evidence
instead of accepting the first signal: a postcode is worth 2, a phone number
3, the company's own email 4, a name mention only 1, and 3 confirms. So a
name mention alone can never confirm a result, which is the directory case
this stage exists to refuse, while a phone number can confirm on its own.

Two supporting pieces: the company's own email address states its website
outright, which answered 17 companies with no search at all, and directory
brands are now matched on their registrable label so every country domain is
covered at once (`cylex.de` was blocked while `cylex.at` came back as the top
result for A. Höfer GmbH).

The 170 weak results are reported, not shipped. A directory naturally
mentions every company it lists, so "the page names the company" is satisfied
by exactly the results that are wrong.

### Where stage 4 has to run, and why it is not a preference

DuckDuckGo hard-blocks the GPU node: all three backends returned `202
Ratelimit` on the first query, while plain page requests still returned 200.
It is the datacenter IP. The same search from a residential connection worked
immediately and the full 1,022 completed at a 3-second delay with no
throttling. Stage 4 performs no model inference, so it is the one stage that
belongs on a laptop.

Also: the GPU node runs Python 3.8.10, where the `ddgs` package will not
install at all. `duckduckgo-search<6` does, and exposes the same interface.

## 3.19 The record arm on 30 pages: misattribution, not invention (2026-09-30)

540 runs, 3 models x 3 strategies x 2 JSON modes x 30 pages x 1 repetition,
asking for the full record (name, website, street, postcode, city, phone,
email) instead of a bare name. One repetition rather than three: the record
arm generates about 80 tokens per company against 9 for a name, measured, so
the full design would have been roughly 100 hours of GPU.

### Asking for seven fields costs name accuracy

Best name F1 falls from **0.962** in the names arm to **0.940** here, on the
same pages with the same answer key. §3.11c predicted this: adding fields
makes the task relational rather than one of recognition.

The model ranking survives, which is what the arm existed to test:

| | names arm | record arm |
|---|---:|---:|
| qwen3.5:9b | 0.893 | 0.908 |
| llama3.1:8b | 0.891 | 0.845 |
| qwen2.5-coder:7b | 0.803 | 0.789 |

qwen3.5 first in both, qwen2.5-coder last in both. llama degrades most when
the task gets harder.

### The weak check said 0.999 and the real one says 0.779

`score_urls` in `benchmark.py` asks only whether a returned host appears
**somewhere** in the page text. By that measure every model scored 0.996 to
1.000 and qwen3.5 was perfect.

The count refutes it before any scorer runs. Stage 2 established that
**1,134** companies have a website printed on their page. qwen3.5 returned
**1,405** addresses, every host present in the text. A page cannot supply
more correct answers than it contains, so the surplus must be real addresses
bound to the wrong companies, which the weak check passes perfectly.

Re-scored with `score_websites.py`, which compares each address against the
company `link_coverage.py` pairs it with:

| | count | share |
|---|---:|---:|
| correct | 16,506 | 77.9% |
| wrong company | **4,632** | **21.9%** |
| invented | 59 | 0.28% |

**Re-scored after the fix, these are the real figures:**

| | count | share of returned |
|---|---:|---:|
| correct | 16,506 | |
| wrong company | **16** | **0.08%** |
| invented | 43 | 0.20% |
| unscored, the pairing has no opinion | 4,632 | |

| model | precision | recall | website F1 |
|---|---:|---:|---:|
| qwen3.5:9b | **0.999** | 0.982 | **0.990** |
| qwen2.5-coder:7b | 0.995 | 0.871 | 0.929 |
| llama3.1:8b | 0.994 | 0.813 | 0.894 |
| total | 0.996 | 0.892 | |

Of 21,197 addresses returned, **16 went to the wrong company**. The first
reading put that at 4,632, an overstatement of roughly 290 times, entirely
caused by the missing category.

### Why 0.999 must not be reported as "website precision"

The corrected number is right arithmetic and a narrow claim, and the wording
matters more here than the figure.

**The denominator excludes the hard cases by construction.** Precision is
computed only where `link_coverage.py` has a pairing, and the companies it
pairs are the ones whose address sits beside their name in a layout a
positional heuristic can resolve. The ambiguous ones are exactly what it
leaves unpaired, and those become `unscored`. For qwen3.5 that is **1,704 of
8,388 addresses, 20% of its output, unmeasured.**

**It measures agreement, not correctness.** The model and the pairing read
the same cleaned text with the same links annotated into it, so they are not
independent witnesses. Where they agree it may be because both are right,
because the page is unambiguous, or because both made the same mistake.

**Recall inherits the same ceiling.** 0.982 is `correct / len(expected)`, so
it means "of the websites the pairing knows about", not "of the websites on
the page".

Defensible wording for the thesis:

> On the 78% of returned addresses where the structural pairing has an
> opinion, the model agrees with it in 99.9% of cases, and returns an address
> not present on the page in 0.2%. The remaining 20% of output cannot be
> scored by this method.

**The contrast with the names result is the point.** F1 0.962 for names is
measured against 2,638 companies labelled by hand, independently of any code
in this repository. That is the number to lead with. The website figures are
agreement with a structural baseline and should be presented as such.

**What would fix it:** hand-check a random sample of returned addresses,
drawn across all four categories rather than only the scorable ones, against
the live page. Fifty gives a usable confidence interval, a hundred a
comfortable one. That converts an agreement rate into an absolute accuracy.
Not done as of 2026-09-30.

**That reading is wrong, and the rest of this section corrects it.** The
first conclusion drawn from this table was "misattribution is 78 times more
common than invention, and it is the dangerous error". Both halves are false,
and the way the error was caught is the point (see "The yardstick was the
weaker party" below).

Per model, qwen3.5 leads on all three at once:

| model | precision | recall | invented |
|---|---:|---:|---:|
| qwen3.5:9b | 0.796 | 0.982 | 6 of 8,388 |
| llama3.1:8b | 0.778 | 0.813 | 31 of 6,728 |
| qwen2.5-coder:7b | 0.756 | 0.871 | 22 of 6,081 |

Best configuration overall: **qwen3.5 with few-shot**, name F1 0.940, website
F1 0.882, zero invented addresses. The top of the website table is a
five-way tie from 0.882 to 0.894, so name accuracy and invention count are
what separate them, not the website score.

### A published finding that did not reproduce

§3.13j reported multi-stage collapsing on websites at 0.217 to 0.328 recall,
and that was carried forward as established. On 30 pages it is false as a
general claim: qwen2.5-coder's multi-stage reaches **0.985 recall and the
best website F1 in the grid**. Only llama's multi-stage is poor, at 0.604.
The collapse was specific to one model on the 10-page corpus.

Worth reporting as such. A finding from a small corpus that survives into the
write-up unchallenged is how a wrong general claim gets published, and the
only reason this one was caught is that the larger corpus was run at all.

### The yardstick was the weaker party

The names in this project are hand-labelled; **the website pairings are not**.
The truth here is `link_coverage.py`'s positional inference about which
address sits with which company. That is a model measured against a
heuristic, so the heuristic was checked before the number was believed.

**Check one.** For every company the pairing DOES have a website for, compare
the model's answer to it. Across the whole winning configuration:
**0 disagreements.** Where the pairing knows the answer, the model gives the
same answer, every time.

So the 4,632 cannot be case (1). Reading the scorer confirms it:

```python
want = exp.get(match_key(rec.get("name", "")))
if want and host == want:   correct
elif host in real:          wrong        # <- anything else printed on the page
else:                       invented
```

`wrong` catches two unrelated situations, and the docstring's fourth
category, "unscored: the company has no website on the page", **has no branch
in the code**. Every company the pairing left unpaired therefore counts as a
misattribution the moment the model returns anything for it.

**Check two.** Of the 283 addresses the winning configuration returned for
unpaired companies, 194 (69%) have a hostname that resembles the company
name. Inspecting twenty at random, the ones the resemblance test missed are
right too, because it needs a four-letter token and these are acronyms:

```
UVR-FIA GmbH                      -> uvr-fia.de
Technologie Zentrum Dortmund GmbH -> tzdo.de
Deutsche Edelstahlwerke Services  -> dew-stahl.com
Fördergesellschaft IZB mbH        -> izb-online.de
Martin-Luther Universität Halle   -> pharmazie.uni-halle.de
```

**So the model is right and the pairing is incomplete.** Three consequences,
in increasing order of importance:

1. Website precision of 0.779 is a floor whose error is mostly the yardstick's.
   The true figure is above 0.95, and the thesis should report the measurement
   and its limit rather than the floor as a result.
2. **The route ceiling of 43% is understated.** Stage 2 counted 1,134
   companies with a website on the page; the model reads websites for
   companies stage 2 filed as "profile only" or "no link", which also means
   the stage 4 search queue of 1,022 is over-inclusive.
3. **The model beats the Python heuristic at the one task Python was assumed
   to do exactly.** §3.13f argues stages 2 and 4 need no model because
   "deciding whether a link points at the association or at a company is a
   hostname comparison, which Python does exactly and for free". That holds
   for CLASSIFYING a link. It does not hold for PAIRING a link to a company,
   and pairing is where the value is. The production pipeline should prefer
   the model's pairing over the positional one.

This is a design conclusion, not a number, and it was only reachable because
the metric disagreed with a count: a page offering 1,134 websites cannot
yield 1,405 correct ones, so something had to be wrong, and the first guess
about what was wrong was itself wrong.

### Runtime, measured per company rather than per page

Seconds per page is not comparable across a corpus where one page has 14
companies and another has 385. Per company:

| arm | model | prompt | s/page | s/company | F1 |
|---|---|---|---:|---:|---:|
| names | llama3.1:8b | few_shot | 18 | **0.36** | 0.948 |
| names | qwen3.5:9b | zero_shot | 26 | 0.50 | **0.962** |
| names | qwen3.5:9b | multi_stage | 46 | 1.00 | 0.930 |
| records | llama3.1:8b | few_shot | 81 | **1.89** | 0.918 |
| records | qwen3.5:9b | few_shot | 105 | 2.35 | **0.940** |
| records | llama3.1:8b | multi_stage | 106 | 3.32 | 0.811 |

Three results:

- **A full record costs about 5 times a name**, 2.35 against 0.50 seconds per
  company for the best configuration. That is the price of the fields
  Neovation asked for, stated in a unit that scales.
- **Multi-stage costs roughly double for worse accuracy**, in both arms and
  for all three models. It is dominated on both axes and should not be
  recommended.
- **The accuracy leader is not the speed leader.** llama's few-shot is 28%
  faster per company than qwen3.5's best and gives up 1.4 points of name F1.
  On a deadline that trade is worth stating rather than hiding behind a
  single ranking.

Scaling to the production target, 291 networks at roughly 88 companies each,
about 25,600 companies on one GPU:

| | best accuracy (qwen3.5 few-shot) | fastest (llama few-shot) |
|---|---:|---:|
| names only | ~3.6 h | ~2.6 h |
| full records | **~16.7 h** | ~13.4 h |

So the whole production database is under a day of compute either way, which
is the answer to "is this feasible at scale" and did not need to be guessed.

### Total runtime, and what the failure handling was worth

| grid | runs | model time | wall clock | lost to overhead |
|---|---:|---:|---:|---:|
| names, before the fixes | 1,800 | 25.2 h | 46.5 h | **21.3 h, 46%** |
| records, after the fixes | 540 | 30.1 h | 30.2 h | **0.1 h, 0.3%** |
| total | 2,340 | 55.3 h | 76.7 h | |

The record arm ran Monday 28 September 18:49 to Wednesday 30 September 01:03,
202 seconds per run, 13 failures in 540.

**The two rows differ only in when they ran.** The names grid predates the
streaming deadline (§3.15) and the token cap (§3.16); the record grid came
after. Same machine, same models, same kind of work. Turning a **46%
overhead into 0.3%** is therefore a measured result of that work, not an
impression of it, and it is the single largest efficiency figure in the
project. Nothing about the models changed.

The names row counts 1,800 rather than 1,620 because it includes the 180
retries, and its wall clock spans three separate launches.

A caution for anyone repeating this: 55.3 hours of model time is the research
cost of comparing 18 configurations twice over. The production cost of
running the winner once is about 17 hours. Conflating the two overstates what
this approach costs to operate by a factor of three.

## 3.18 Stage 3 on 30 pages, and a cleaning rule that deleted 183 pages (2026-09-28)

463 profile pages fetched and read. The first run looked like a collapse
against the 10-page study:

| field | 30 pages | 10 pages |
|---|---:|---:|
| company website | 49.2% | 84.8% |
| street | 53.4% | 91.1% |
| postcode | 53.2% | 90.2% |
| city | 53.4% | 91.1% |
| phone | 39.7% | 42.0% |
| email | 38.1% | 33.0% |

The shape of the drop is the clue. Website, street, postcode and city fall
together by about 38 points while phone and email do not move. A model that
had got worse would not spare two fields.

Per network, one page is responsible:

| page | pages | website found |
|---|---:|---:|
| 084 OSB Alliance | 183 | **1%** |
| 045 | 132 | 87% |
| 039 | 51 | 94% |
| 004 | 31 | 77% |
| 076 | 14 | 100% |

084 alone is 183 of 463. Excluding it the website rate is about 81%, in line
with the earlier study. So nothing had degraded; one network returned nothing.

### The cause

The pages fetched correctly: 98 KB each, real content, correct URLs. But
cleaning reduced them to **152 words** of navigation. Tracing the company's
own email address through the markup:

```
<a href="mailto:patricka@element.io">
  inside <p>
  inside <div class="entry-content">
  inside <header class="entry-content-header">   <- STRIPPED
  inside <article>
  inside <main>
```

`header` is in `STRIP_TAGS` to remove site banners. This WordPress theme puts
the article's own content header in a `<header>`, which is valid HTML5, and
the member record lives there. The cleaner therefore kept the menu and threw
away the page.

The model was not wrong either. Given 152 words of navigation it returned
`Factorial GmbH` and `Camptocamp Germany GmbH`, the only company names in the
text, from a sidebar of other members.

### The fix, and why it is not applied everywhere

`header`, `footer`, `aside` and `nav` are site chrome only when they sit
OUTSIDE the main content. Inside `<main>` or `<article>` they are part of the
article. `cleaner.process(..., keep_inner_sections=True)` applies that rule
and stage 3 uses it.

Listing pages deliberately do not, and this was measured rather than assumed.
Applying the same rule to the 30 ground-truth pages changes 7 of them, adding
between 1 and 63 words, and **0 of the added lines are companies in the answer
key**. What they add is "Themenfelder", "Energie- und Klimapolitik",
"Kontakt", "Mitglied werden". On a listing page that is precision the model
would lose, and it would invalidate 1,620 completed runs to gain nothing.

So the two page types are cleaned differently, for a stated reason: a listing
page keeps its content in `<main>` and everything else is chrome, while a
single-company page may keep the record in a `<header>` within the article.
Both directions are asserted in `test_metrics.py`.

### Stage 3 after the fix, and how the result was verified

| field | before | after |
|---|---:|---:|
| company website | 49.2% | 85.2% |
| street | 53.4% | 88.2% |
| postcode | 53.2% | 88.0% |
| phone | 39.7% | 71.7% |
| email | 38.1% | 72.1% |

084 went from 1% to 91%. Phone and email nearly doubled across the corpus,
so the same stripped `<header>` had been hiding contact details on other
networks too. The overall website rate, 85.2%, now matches the 10-page study's
84.8%, which is the independent check that nothing else was wrong.

"The model returned something" is not "the model returned the right thing", so
three checks, not one:

- **Every returned URL was verified present in the page text and not the
  association's own domain.** 85.2% returned, 85.2% verified, 0 rejected.
- **165 distinct hosts from 183 members** on page 084. Copying one URL or
  inventing from the name would show as a few hosts repeated.
- **A hand-checked sample**: Element Software to element.io, GONICUS to
  gonicus.de, Nextcloud to nextcloud.com.

Two small defects remain, both recorded rather than fixed. Pages 009 and 088
have a listing URL in the profile column, so `link_coverage.py` classified a
pagination link as a profile link: 2 of 463. And page 083's 16 pages carry the
web agency's address, `kontakt@evermind.de`, on 12 companies, which is the
footer-contamination problem described below.

### 36% of the email field was written backwards

Found by asking which email domains appear for more than one company, a check
meant to catch footer contamination. It returned domains that are not domains:

```
  76  ofni        6  selas        5  tcatnoc        3  tkatnok
```

Those are "info", "sales", "contact" and "kontakt" reversed. The pages store
the address backwards and flip it with CSS, which hides it from spam crawlers
and equally from us. Of 331 addresses: 211 valid, **119 written backwards**,
1 using "(at)", 1 unrecognisable.

```
ed.snorcim5@tkatnok   ->  kontakt@5microns.de
moc.puorgsidokka@anej ->  jena@akkodisgroup.com
hpi-info(at)hpi.de    ->  hpi-info@hpi.de
```

The model reported exactly what the page contained, so this is a page
convention to undo, not a model error. `_clean_email` in `extractor.py`
handles reversal, `(at)`/`(dot)` spelling and the two combined, and sits
beside `_clean_url` because it is the same kind of repair. A valid address is
returned untouched and an unrecognisable one is kept rather than blanked, both
asserted in `test_metrics.py`: over-correcting a field is how a repair becomes
the next bug.

### Still open: contact details shared between companies

`kontakt@evermind.de` on 12 companies is a web agency's address in a footer.
`+49 341 253966-0` appears on 10. A company's own contact details should be
close to unique to it, so anything shared across several companies is a
footer, an agency or the association. Not yet handled. It matters more than
its volume suggests, because a wrong-but-plausible phone number is the error
nobody catches, the same argument as for fabricated URLs in §3.13h.

### Worth carrying into the write-up

A preprocessing rule that is right on one page type can silently destroy
another, and it fails without any error: 183 pages returned a valid, parseable,
completely empty answer. It was found only because the per-network breakdown
was checked instead of the average. The average said 49%, which is a number
that describes nothing that exists.

The email discovery came the same way. Both were found by asking "which
groups does this average hide?" rather than by any test, and neither would
have been visible in a pooled figure.

## 3.17 Stage A complete on 30 pages: the model and prompt comparison (2026-09-28)

1,620 configurations: 3 models x 3 prompt strategies x 2 JSON modes x 30
pages x 3 repetitions, against 2,638 hand-labelled companies. 1,600 produced
a clean answer; the 20 that did not are model behaviour and are counted in
the numbers below rather than dropped (§3.16).

`F1/net` is the mean of per-page F1, which weights a 14-company page the same
as a 385-company one. `pooled` counts every company once. Both are given
because they answer different questions and they disagree in places.

| model | prompt | mode | F1/net | pooled | prec | rec | fail | sec |
|---|---|---|---:|---:|---:|---:|---:|---:|
| qwen3.5:9b | zero_shot | prompt_only | **0.962** | 0.958 | 0.927 | 0.991 | 0 | 25 |
| qwen3.5:9b | zero_shot | constrained | **0.962** | 0.958 | 0.927 | 0.990 | 0 | 26 |
| qwen3.5:9b | few_shot_schema | constrained | 0.958 | 0.955 | 0.921 | 0.991 | 0 | 24 |
| qwen3.5:9b | few_shot_schema | prompt_only | 0.958 | 0.955 | 0.921 | 0.991 | 0 | 21 |
| llama3.1:8b | few_shot_schema | constrained | 0.947 | 0.950 | 0.969 | 0.932 | 1 | 18 |
| llama3.1:8b | zero_shot | constrained | 0.939 | 0.957 | 0.961 | 0.954 | 0 | 16 |
| llama3.1:8b | zero_shot | prompt_only | 0.926 | 0.943 | 0.962 | 0.924 | 3 | 16 |
| llama3.1:8b | few_shot_schema | prompt_only | 0.926 | 0.934 | 0.967 | 0.903 | 3 | 18 |
| qwen2.5-coder:7b | zero_shot | prompt_only | 0.909 | 0.912 | 0.970 | 0.860 | 0 | 18 |
| qwen3.5:9b | generic_multi_stage | constrained | 0.903 | 0.932 | 0.954 | 0.911 | 3 | 46 |
| qwen3.5:9b | generic_multi_stage | prompt_only | 0.903 | 0.932 | 0.954 | 0.911 | 3 | 46 |
| qwen2.5-coder:7b | zero_shot | constrained | 0.901 | 0.927 | 0.973 | 0.886 | 0 | 18 |
| qwen2.5-coder:7b | generic_multi_stage | constrained | 0.879 | 0.930 | 0.975 | 0.890 | 0 | 38 |
| qwen2.5-coder:7b | generic_multi_stage | prompt_only | 0.866 | 0.901 | 0.974 | 0.839 | 3 | 39 |
| llama3.1:8b | generic_multi_stage | constrained | 0.836 | 0.865 | 0.958 | 0.788 | 1 | 40 |
| llama3.1:8b | generic_multi_stage | prompt_only | 0.818 | 0.848 | 0.957 | 0.760 | 3 | 40 |
| qwen2.5-coder:7b | few_shot_schema | constrained | 0.669 | 0.711 | 0.921 | 0.580 | 0 | 13 |
| qwen2.5-coder:7b | few_shot_schema | prompt_only | 0.647 | 0.614 | 0.906 | 0.464 | 0 | 12 |

### Five results

**1. The simplest prompt wins, and prompt engineering bought nothing.**
Zero-shot is the best or joint-best strategy for every model. Few-shot with a
schema example never beats it by more than noise and is catastrophic for one
model. The multi-stage strategy is worse than zero-shot for all three models
and takes two to three times as long. This is the answer to the thesis
question about generic prompt strategies, and it is negative: on this task,
elaboration does not help.

**2. Constrained decoding buys reliability, not accuracy.** On the winning
configuration the two modes are identical to three decimal places, 0.962 and
0.962. What changes is failures: llama zero-shot fails 0 times constrained
and 3 times free, few-shot 1 against 3, and qwen2.5-coder multi-stage 0
against 3. Grammar-forced output does not make a model more correct, it makes
it parseable. Reported as such rather than as an accuracy result.

**3. Prompt strategy interacts with the model, so a single ranking is wrong.**
Few-shot is qwen2.5-coder's worst strategy at 0.647, a 26-point drop from its
own zero-shot 0.909, while for qwen3.5 the same strategy costs 0.004. A study
that tested one model would have concluded few-shot is fine, or that it is
ruinous, depending on which model it picked.

**4. The models differ in the KIND of mistake, not just the amount.**

| | precision | recall | of 2,638 companies |
|---|---:|---:|---|
| qwen3.5:9b zero-shot | 0.927 | 0.991 | misses 24, returns 206 not in the key |
| llama3.1:8b few-shot constrained | 0.969 | 0.932 | misses 179, returns 79 not in the key |
| qwen2.5-coder:7b zero-shot | 0.973 | 0.860 | misses 369, returns 69 not in the key |

"Not in the key" is not the same as invented. Some of those 206 will be page
furniture and some will be real members the answer key missed, and the two
cannot be told apart from these numbers. That is precisely what the planned
consensus-disagreement audit is for: a name all three models return and the
key does not have is far more likely to be a gap in the key than a shared
hallucination. Until that audit runs, qwen3.5's precision is a lower bound.

qwen3.5 wins F1 by finding almost everything and being less careful about
what it returns. llama returns less and is more often right. **Which is
better is not a measurement, it is Neovation's decision**: a missing company
is a visible gap that a later stage can fill, while a false company is a
plausible-looking record nobody catches, which is the argument made about
fabricated URLs in §3.13h. If precision is what matters for the database,
llama with few-shot and constrained decoding is the honest recommendation
despite losing on F1.

**5. Multi-stage remains the worst idea in the study.** Worst or near-worst
for every model, and the slowest by a factor of two to three. §3.13c-2 found
why: the validation call deletes correct entries. Recall confirms it, at
0.760 to 0.911 against 0.86 to 0.99 for single-call strategies. It is also
where 14 of the 20 permanent failures sit.

### What this does not yet say

Names only. §3.13j established that name accuracy alone picks the wrong
model, because the website field behaves differently: multi-stage scores
acceptably on names and collapses to 0.217-0.328 recall on websites, since a
deleted record takes its website with it. The record arm has to run before
any of this becomes a production recommendation.

## 3.16 The context window, not the model: how a 4% tokenizer difference destroyed 102 runs (2026-09-28)

The most useful result of the 30-page names grid, and it is about the harness
rather than about any model. Worth the space because the conclusion it nearly
produced ("qwen3.5 is fragile on large pages") would have been wrong and
publishable.

### What it looked like

158 of 1,620 runs failed. Split by cause, they were two unrelated problems:

| model | hangs | unreadable JSON | of runs |
|---|---:|---:|---:|
| llama3.1:8b | 20 | 9 | 540 |
| qwen2.5-coder:7b | 33 | 3 | 540 |
| qwen3.5:9b | **0** | **84** | 540 |

The obvious reading is that qwen3.5 cannot produce valid JSON. It is also
wrong. The failures were not spread at random: on pages 005, 050, 079, 082
and 088 qwen3.5 failed **every** run, every strategy, every mode, every
repetition, while llama scored 297 of 296 on page 050. Determinism at
temperature 0 says that is structural, not unlucky.

### Ruling things out, including one of my own explanations

Truncation was checked first by dividing each run's token counts by its chunk
count. That gave about 5,400 per call against a limit of 8,192, which looked
like ample room, and truncation was set aside. **That step was wrong.** The
counts are summed over chunks, and the chunks are not equal: page 050's third
chunk is 27 output tokens. Dividing by three understated the real chunks
badly. A confounded average is exactly the kind of number this project has
been bitten by before (§3.13g, and the header of `test_metrics.py`).

The mistake was only caught because the raw reply was finally looked at, which
required re-running one call, because the benchmark stores parsed names and
not the model's text. Written up as `debug_one_call.py`.

### What the text showed

```
chunk 1: UNREADABLE  2269 chars, wrote 726 tokens
LAST 400: ... "FLAIR Modellbrillen Dr.
ends with '.'   balanced braces: False
```

Cut off mid name. Then the counts, per call this time:

| chunk | input | output | total | result |
|---|---:|---:|---:|---|
| 1 | 7,466 | 726 | **8,192** | cut off |
| 2 | 6,129 | 998 | 7,127 | 114 names |
| 3 | 558 | 27 | 585 | 3 names |

8,192 to the token. Re-running chunk 1 with a 16,384 window returned **198
complete names**, needing 1,760 output tokens.

### The actual cause

`CHUNK_TOKEN_BUDGET = 6000` is meant to leave room inside an 8,192 window. It
measures the page text only, at `CHARS_PER_TOKEN_ESTIMATE`, and excludes the
system prompt and instructions. Prefilling every chunk of all 30 pages with
the largest wrapper and reading the real count back:

| page | biggest chunk | room left at 8192 |
|---|---:|---:|
| 079 | 8,123 | **69** |
| 088 | 7,845 | 347 |
| 005 | 7,618 | 574 |
| 050 | 7,573 | 619 |
| 086 | 7,315 | 877 |

A 6,000-token budget produces a measured 8,123-token prompt: a **35%
underestimate**. On page 079 the model had 69 tokens in which to answer.

**Why qwen3.5 and not llama.** On page 050 llama read 13,557 tokens where
qwen3.5 read 14,153, a 4% difference in how the two tokenizers handle German
compound words. The window is a cliff rather than a slope, so a 4% difference
decided between a complete answer and a destroyed one. Nothing about model
quality is involved.

### What was checked before changing anything

Ollama truncates an over-long input silently and never raises, so a cut input
would finish normally, report no error, and merely score badly. Two checks:

- Of the 684 single-call runs, where the recorded input is one call's input,
  **0** had an input at or over 8,100 and **0** were at the total ceiling.
- Across all 30 pages, measured directly, **0 chunks exceed 8,192**. The
  largest is 8,123.

A truncated *reply* also cannot hide, because unbalanced braces leave
`_salvage_json` with no candidate and the run is recorded with an error. So
all of the damage is inside the 158 known failures, and none of it leaked
into the results that look fine.

### The fix, and why the window rather than the chunker

`NUM_CTX` 8192 -> **16384**. The chunker is left alone on purpose: changing
`CHUNK_TOKEN_BUDGET` re-chunks every page, which changes the input to every
call and invalidates all 1,462 completed runs. Raising the window changes
nothing for a run that never reached the limit, so those runs stay valid and
only the 158 are re-run. Guarded in `test_metrics.py` against the measured
worst case so the window cannot quietly drop back.

### What the re-run then exposed: two failures that are results, not bugs

Raising the window recovered 29 of the first 51 retries. The 22 that failed
again split into three kinds, and only one of them is the harness:

**Invalid JSON without a grammar, and only without a grammar.** Every repeat
failure on page 079 is `prompt_only`; none is `constrained`. Input 8,277 and
output 1,052 against a 16,384 window, so nothing was truncated. The model
simply wrote JSON that does not parse, most likely an unescaped quote inside
a German company name. **This is the measurement, not an obstacle to it**:
the constrained-versus-prompt-only comparison exists to find exactly this,
and page 079 is where it shows. It is reported as a failure of that
configuration, not repaired.

**Repetition loops.** On 077, 082 and 088 the model kept generating until a
clock stopped it. Under the old 8,192 window these looked like ordinary
truncation and ended quickly; with 16,384 the same loops ran for a full 30
minutes each. The behaviour did not change, only the time it took to notice.

The cost, measured over 51 retries spanning 7.71 hours:

| outcome | runs | seconds each | hours total |
|---|---:|---:|---:|
| worked | 28 | 94 | 0.73 |
| invalid JSON | 9 | 43 | 0.11 |
| runaway, stopped by the cap | 6 | 1,828 | 3.05 |
| timeout, also a runaway | 7 | 1,967 | 3.82 |

**6.9 of 7.7 hours went to 13 runs that failed anyway.**

A time limit is the wrong instrument here, for the same reason a single
deadline could not separate slow from stuck (§3.15). Tokens separate them
cleanly, because honest answers are nowhere near the limit: the largest real
reply measured is 1,760 tokens and the next 1,550, while a loop runs
unbounded. `NUM_PREDICT = 4096` catches a loop in about two minutes, leaves
better than twice the headroom over any honest reply, and still fits inside
the window alongside the largest chunk (8,123 + 4,096 = 12,219 of 16,384).
All three bounds are asserted in `test_metrics.py`, since each of them was
wrong at some point in this investigation.

### For the write-up

1. Reported accuracy was measured with the failures excluded, and the
   failures were the densest pages. Any figure computed before the re-run
   flatters every model, and flatters qwen3.5 most, since it lost five whole
   pages while llama kept them.
2. A fixed context window turns a small tokenizer difference into a total
   failure on exactly the inputs that matter most, the pages with the most
   companies. When comparing models on one machine, the window is a property
   of the harness that can masquerade as a property of the model.
3. Store the model's raw reply, not only the parsed result. Three hours went
   into inferring from token counts what one saved string would have shown
   immediately, and one of those inferences was wrong.

## 3.15 Half the run time went to hung requests, and the deadline that hid it (2026-09-27)

Found while watching the 30-page names grid, not by a test. Worth reporting
because it is a property of serving models locally, not a property of this
code, and anyone repeating the work on one GPU will meet it.

### What the numbers said

At 1,053 of 1,620 runs:

| | |
|---|---:|
| wall clock | 22.6 h = 81,360 s |
| model time recorded in the results file | 38,974 s = 10.8 h |
| unaccounted for | 42,386 s |
| 47 timed-out runs x the 900 s deadline | 42,300 s |

The two bottom figures agree to within 86 seconds. **More than half the run
was spent waiting on connections that were never going to answer.**

### Why it was invisible

`latency_seconds` is accumulated as `result.latency_seconds += elapsed`, which
only executes after a call returns. A call that hangs never returns, so its
900 seconds were never written anywhere. Page 077 reports 10.8 s for a run
that actually occupied over 15 minutes: chunks 1 and 2 finished normally, and
chunk 3 hung.

This is the same failure shape as the scoring bugs in §3.13g and the test
file's header. Nothing raised, nothing looked wrong, and the number that was
printed was confidently incorrect. The only reason it surfaced is that the
wall clock and the sum of the latencies disagreed, and the gap was checked.

A consequence for the results: failed runs are excluded from the accuracy
averages, and the failures concentrate on the largest pages (079, 086, 077,
082, 091, 050). Any accuracy figure computed before those gaps are filled is
therefore slightly flattering, because it silently drops the hardest cases.

### Why the obvious fix was wrong

The first instinct was to lower the deadline. The 30-page data supports it:
median call 12.5 s, 99th percentile 113 s, slowest 124 s. A 360 s deadline
looked like ample headroom.

Checking the archived 10-page study refuted this. A legitimate single call
there took **468 s**. A 360 s deadline would have killed real work, and
because the victims would be the biggest pages, it would have biased the
results toward easy pages while reporting nothing unusual.

The 2,769 s figure quoted in the old `config.py` comment was a whole
multi-stage run of six calls, not one call. Reading it as a per-call figure
was the error that made 360 s look safe.

### The fix: two deadlines instead of one

One deadline cannot separate **a call that is slow** from **a call that is
dead**. Any single value is either too tight for the first or too loose for
the second, which is exactly the trap above.

Reading the reply as it streams separates them, because the deadline then
applies to the gap between pieces of text rather than to the whole call:

- `STREAM_GAP_S = 180` a model that is working emits something every few
  seconds however long the total takes. A dead connection emits nothing and
  is caught in three minutes instead of fifteen. A slow call is never cut off,
  no matter how slow.
- `REQUEST_TIMEOUT_S = 1800` a total cap for the opposite failure, a model
  that never stops generating.
- One retry, on transport errors only. A hang is usually the connection dying
  rather than the work being hard, so a retry recovers the data point. The
  total cap is deliberately **not** retried: a model still generating after
  half an hour would just spend another half hour failing the same way.

Streaming does not change what the model generates. Temperature, seed,
`num_ctx` and the prompts are untouched, so rows produced before and after
this change stay comparable. The retry clock starts fresh on the second
attempt, because `latency_seconds` is meant to be the cost of the model's
work, and a dead connection is not that.

Covered by `test_streaming_calls` in `test_metrics.py`: the pair that matters
is that a slow reply survives and a stuck one raises. A silent empty string
would be worse than an error, because it would score as "the model found
nothing" and enter the results as a real answer.

### For the write-up

Two points, both measured rather than asserted:

1. Throughput on a single local GPU is governed by failure handling at least
   as much as by model speed. Halving the wasted waiting is a larger win here
   than any difference between the three models.
2. A timing metric that only records successes will understate the true cost
   of a strategy, and will understate it most on exactly the inputs that are
   hardest. Wall clock and the sum of recorded latencies should be reconciled
   as a matter of course.

## 3.14 Ground-truth expansion to 30 pages: how the 20 new pages were chosen (2026-09-22)

Hendro asked for 20 more ground-truth pages, chosen to be representative:
"unique and different", not 20 of the same kind. The selection is purposive
and stratified. Every step is recorded so it can be repeated or challenged.

### Step 1: which pages can be labelled at all

The Finalv1 sheet (Yusif and Diego) lists 291 networks. Their saved member
pages (`results/html_cache_finalv1/`, survey of 2026-08-21) contain a member
list in the HTML for **153**. The rest are rendered by JavaScript (85), nearly
empty (41) or unreachable or erroring (12). Only the 153 can be labelled from
the page the model actually reads. Removed from those:

- **6 already in the ground truth:** BDEW, BVMed, German Water Partnership,
  Life Science Nord, Medical Valley EMN, SPECTARIS.
- **14 where legal forms appear only in running text**, not as list entries.
  This is the entries-versus-prose test round 1 already used: at least 10
  short lines carrying a legal form.

### Step 2: describe every page without a model

Measured from the HTML for each remaining page (`results/finalv1_page_features.csv`):

| property | how it was measured |
|---|---|
| layout | the dominant kind of entry: name linked to the company site, name linked to a profile page, name plus a separate "Web" link, logo whose image text holds the name, table, or plain text |
| size | number of short lines carrying a legal form |
| long page | split into two or more chunks for the model |
| network type | ZIM or privately funded |
| look-alike websites | pages whose CSS class vocabularies overlap by 60% or more are grouped: 5 groups covering 27 pages, the largest 11 EurA-managed ZIM sites |
| manager | the consultancy running a ZIM network |

Layouts across the 153 pages: company site 87, profile page 27, plain text
20, separate "Web" link 10, logo grid 5, table 4.

### Step 3: choose

Rules: cover every layout; mix small, medium and large lists; include long
pages; include ZIM networks, of which the first 10 pages have none; at most
one page per look-alike group and per manager; spread sectors. A seeded,
rule-based draft came first. Sample lines from every candidate were then read,
which rejected four: **BVDM** (its members are regional associations),
**WSM** (associations), **VDMA** (only the first 10 of thousands of members
load) and **INPREC-TEC** (the link points to another association's list of
about 430 companies). The final 20 were picked by hand from the checked pool,
each with a recorded reason.

### Step 4: pagination check

The saved HTML was scanned for page links, "next" and "load more" buttons,
pager elements, A-to-Z tabs that load separate pages, and stated member
totals. Two of the 20 held only their first page and were replaced:

- **PROFIBUS**: 27 of "over 500" members, with a "load more" button, replaced
  by **Wirtschaftsvereinigung Stahl**.
- **DSAG**: 137 of "over 4,000" companies, pages 1 to 27 and more, replaced by
  **Deutscher Schraubenverband**.

Six more were flagged and judged complete: the stated total matched the page,
or the flag belonged to another part of the page. **BVIZ** shows one member
category ("ordentliche Mitglieder"), a sub-list rather than pagination. The
scan sees only the saved HTML, and a list that loads more on scrolling can
leave no trace, so every page is also checked in a browser before labelling.

### Step 5: are the pages still online (2026-09-24)

Five weeks after the snapshot, each of the 20 addresses was requested again:

- **18 answer normally.**
- **LocaSenZ no longer exists**: its domain does not resolve (NXDOMAIN). It was
  replaced by **MAGNA BIO**, from the same look-alike template family, same
  layout, 16 companies, also split into two chunks. **SCAS**, another page in
  that family, is dead as well.
- **PlasticsEurope returns 403 to a script** but opens normally in a browser,
  so it stays. It has to be opened in a browser when labelling.

Labelling always uses the saved copy, so a dead page is not an obstacle; the
swap was made because a page that can still be opened is easier to label
against. **The disappearance itself is a result worth reporting**: 1 of 20
member pages vanished within five weeks, and both dead pages belong to ZIM
networks, which end when their funding ends. A company database built from
these sources needs a refresh schedule, and the ZIM half of the corpus is the
perishable part.

### The 20 pages

| id | network | type | layout | ~entries | why it is in the sample |
|---|---|---|---|---:|---|
| 074 | MAGNA BIO | ZIM | company site | 16 | the most common ZIM template: 11 near-identical EurA sites (replaces LocaSenZ, whose site went offline) |
| 075 | KliWaTex | ZIM | company site | 31 | the textile ZIM template: 6 near-identical sites |
| 076 | SmartFactory5G+ | ZIM | company site | 18 | the embeteco ZIM template: 4 sites |
| 077 | Mikroalgen | ZIM | company site | 16 | the T+I ZIM template, split into 3 chunks |
| 078 | AgrarCycle | ZIM | company site | 17 | ZIM network run by a university, not a consultancy |
| 079 | VDGH | private | company site | 104 | large and split into chunks; some names have no link |
| 080 | en2x | private | company site | 32 | clean medium list, energy sector |
| 081 | Wirtschaftsvereinigung Stahl | private | company site | 44 | replaces PROFIBUS, whose page holds 27 of 500+ members; clean medium list, steel |
| 082 | VOICE | private | company site | 328 | the largest page in the sample, 2 chunks |
| 083 | BIM | ZIM | profile page | 11 | the only ZIM page that links names to profile pages |
| 084 | Open Source Business Alliance e.V. | private | profile page | 40 | profile pages, IT sector |
| 045 | OptoNet | private | profile page | 115 | names broken by invisible hyphens (Tech-no-lo-gie) |
| 085 | PlasticsEurope Deutschland e.V. | private | plain text | 55 | name and city on one line |
| 086 | Industrieverband Klebstoffe e.V. | private | plain text | 144 | long plain-text list, 3 chunks |
| 087 | Verband deutscher Pfandbriefbanken e.V. | private | separate 'Web' link | 33 | separate 'Web' link; banks, not manufacturers |
| 088 | BVIZ | private | separate 'Web' link | 116 | separate 'Web' link, 3 chunks; innovation centres |
| 089 | Verband Schmierstoff-Industrie e.V. | private | logo grid | 84 | the only logo grid left in the pool |
| 090 | SprayCloth | ZIM | table | 12 | the only ZIM table, with broken name fragments |
| 091 | DGM | private | table | 112 | a table inside an annual report page |
| 092 | Deutscher Schraubenverband e.V. | private | table | 122 | replaces DSAG, whose page is 1 of 27+; a table with no pagination signs |

Registered as ids 074 to 092 in `data/urls_73.csv`, plus 045 (OptoNet), which
was already in the list. VDGH was already present as 055, but that saved page
is empty, so round 2 uses the Finalv1 address as 079. Full record:
`results/ground_truth_expansion_20.csv`.

### The 30-page sample against the corpus

| layout | first 10 | new 20 | 30 pages | share of the 30 | share of the 153 |
|---|---:|---:|---:|---:|---:|
| company site | 1 | 9 | 10 | 33% | 57% |
| profile page | 3 | 3 | 6 | 20% | 18% |
| plain text | 3 | 2 | 5 | 17% | 13% |
| separate "Web" link | 2 | 2 | 4 | 13% | 7% |
| logo grid | 1 | 1 | 2 | 7% | 3% |
| table | 0 | 3 | 3 | 10% | 3% |

Also: 7 of 30 pages are ZIM networks (23%, against 28% of the 153), and 10 of
30 are long pages (2 in round 1, 8 in round 2).

**Rare layouts are over-represented on purpose**, because that is where
extraction is most likely to fail. Results should therefore be reported per
layout as well as pooled, so the over-representation does not distort the
headline figure.

### The labelling rule, and what it revealed about round 1

Ground truth records **exactly what the saved page shows**, as in round 1: the
model and the answer key read the same document.

The pagination check also found that **4 of the first 10 pages are only the
first page of a longer list**: BVMed (page 1 of at least 3, "1-50, 51-100,
101-150"), Life Science Nord (page 1 of 7), Medical Valley EMN (a "Weiter"
button) and BDEW (letter A, already known). Their scores remain valid as a
measure of extraction, since model and answer key saw the same page. But the
deliverable's coverage ("752 of 760", §3.13n) describes the saved pages, not
those networks' full membership.

Across the 153 pages with a member list, 23 show clear pagination signs.
`paginate.py` already follows URL-based pagination (`?page=2`, `?letter=B`);
a JavaScript "load more" needs the browser fetcher. For the production run
over all networks, pagination has to be handled at download time.

### Labelling setup, and a silent failure it exposed

The 20 worksheets (`data/ground_truth/<id>_<name>.txt`) are pre-filled by
`make_ground_truth.py`, rules only, never a model. The first pre-fill left two
pages empty: VSI (a logo wall, whose names exist only as image alt text) and
vdp (a list printed as plain lines). Two rule-based sources were added for
round 2: image alt texts, and lines of the cleaned page text carrying a legal
form. VSI went from 0 to 90 candidates, vdp from 0 to 33, Klebstoffe from 27
to 142. Each worksheet now also names the saved copy of the page, the exact
file the model reads.

**Silent failure.** Running `make_ground_truth.py --check` right after
generating the worksheets turned all 20 **unedited** worksheets into answer
keys and printed "30/30 worksheets complete. Ground truth ready". The check
treated any existing worksheet as finished. Any benchmark run after that would
have been scored against the unedited guesses, one of which listed 452
"companies" and another "Zum Inhalt springen". It was caught by reading the
output, and fixed three ways:

- Worksheets carry a `# STATUS: TODO` line. `--check` turns only `DONE`
  worksheets into answer keys, and removes any key left over for a `TODO` one.
  Round-1 worksheets predate the line and count as done.
- `benchmark.py` skips Stage A pages that have no answer key. Otherwise the
  resume logic would treat an unscored run as finished and never repeat it.
- Known-answer tests for the status line and worksheet parsing (93 checks).

The 10 round-1 answer keys were compared with the copies made on 2026-09-15:
all 761 names are identical, so nothing from round 1 was changed.

### The finished ground truth (2026-09-26)

**30 pages, 2,638 companies**, 760 from round 1 and 1,878 from the 20 new
pages. Labelled by hand from the saved copies, never from a model.

| route | companies | share | who can supply the website |
|---|---:|---:|---|
| website printed on the page | 1,134 | 43% | stage 1, the model |
| profile page only | 482 | 18% | stage 3, one fetch each |
| no link at all | 1,022 | 39% | stage 4, web search |

The ten-page corpus gave 63 / 15 / 22; the thirty-page corpus is harder,
because the new pages were chosen for variety rather than convenience. That
shift is itself a result: **the share of companies whose website is simply
printed next to them falls from 63% to 43%** once the sample stops being
dominated by three generous directories.

**Checks run before freezing**, all 30 answer keys: duplicates, contact
details, filter entries, addresses left on a line, and whether every entry
appears in the text the model receives. 22 pages were clean. The corrections:

- **8 entries removed** that exist on the live sites but not in the saved
  copies. They were typed while labelling from the browser. Left in, every
  model would take a guaranteed miss. Recorded here because the originals are
  not kept as files: 079 VDGH "Applyo Jena GmbH", "mevida Diagnostika GmbH";
  082 VOICE "KAMAX Holding GmbH & Co. KG", "KKH Kaufmännische Krankenkasse",
  "Kuraray Europe GmbH", "Oventrop GmbH & Co. KG"; 088 BVIZ "Artprojekt Nature
  & Nutrition GmbH", "Augsburger Innovationspark GmbH". Checked against the
  live sites on 2026-09-26: four are still there (the two VDGH ones, Kuraray,
  Augsburger Innovationspark); for the other four the live page needs a
  browser, so it cannot be told either way. Giorgi decided to keep the keys
  describing the snapshot (2026-09-26).
- **2 paste typos fixed** on DGM ("EurofinsQualitech AG", "TEGnologyApS").
- **One bug in the checker itself**: the address stripper turned "Laser 2000
  GmbH" into "Laser" and "BSK 1818 AG" into "BSK", because a four-digit number
  followed by a word looks like a postcode and a city. A tail carrying a legal
  form is now never treated as an address.
- Flagged and deliberately kept: names that differ from the page only in
  spacing or punctuation ("ChemCologne e. V." in a logo's alt text, "( Pty )",
  "GLOCK Ges.m.b.H ."), since scoring ignores both.

The answer keys and worksheets are frozen in
`data/ground_truth_frozen_2026-09-26/`, so any later correction stays
traceable.

### Predictions to check after the 30-page run, written before it

Recording these now, while labelling, so they are predictions rather than
explanations after the fact. Report per layout, not only pooled.

- **074 MAGNA BIO (noticed by Giorgi while labelling).** Every member is
  printed as a name, then an address block, then a paragraph of prose about
  the company. 3,141 words for 23 members, two chunks. The pre-fill offered 45
  candidates for 23 real members, most of the surplus being sentence
  fragments. Expect low precision here: the model has to pick one name line
  out of a page that is mostly prose, and the prose repeats company and
  institute names. Several of the EurA-template ZIM pages are built this way.
- **078 AgrarCycle (predicted by Giorgi while labelling).** Each member is
  printed as a name, then a line "Branche: <what the company does>", then
  prose. 19 such lines. He expects models to return the trade description as
  a company name. Evidence that the trap is real: one of those 19 lines ended
  up in the hand-written answer key itself before it was caught.
- **080 en2x.** Two members share one line, the first ending in a comma
  ("Gunvor Raffinerie Ingolstadt GmbH," / "Gunvor Deutschland GmbH"). Expect
  both models and humans to return them as one company.
- **089 VSI, the logo grid.** Names exist only as image alt text. Whether a
  model sees them at all depends entirely on the cleaner, not on the model.
- **091 DGM and 092 Schraubenverband, tables.** Rows carry extra columns
  (products, locations); expect names returned with the extra cell text
  attached.
- **085 PlasticsEurope.** Every line is "Name, City". Expect the city to be
  returned as part of the name, which the scorer counts as wrong.
- **045 OptoNet.** Names contained soft hyphens, invisible in the browser but
  present in the text the model reads. The cleaner now removes them (below),
  so this page is no longer expected to be hard for that reason.

Also noted while labelling: many members on 074 are institutes and
universities with no legal form in their name, so the legal-form estimate used
for selection (16) understated the real count (23). The estimates in the table
above are lower bounds for pages of that kind.

### Invisible characters, and a page decoded with the wrong character set (2026-09-24)

Giorgi reported "weird characters mixed into every word" while opening the
OptoNet worksheet. Two separate faults sat behind it.

**1. The page uses soft hyphens.** OptoNet puts U+00AD inside almost every
word so the browser can break lines: "Tech<SHY>no<SHY>lo<SHY>gies". They are
invisible on screen but sit in the text a model reads, and scored literally
they split one company into fragments. Seven of the 30 sample pages carry such
characters (soft hyphens, zero-width spaces, zero-width joiners).

**2. One saved copy was decoded with the wrong character set.** The copy of
OptoNet fetched on 2026-08-03 had every soft hyphen turned into the two
letters "ôÙ", 457 times on one page. `fetcher.py` set the encoding from
chardet's guess *before* looking at what the page declares, and OptoNet
declares UTF-8 correctly. The copy taken by the Finalv1 survey on 2026-08-21
is clean and is now the one in use. **Only this one page of the 30 was
affected**, but the same fault would have corrupted names silently anywhere in
the 291-network production run, and a browser shows nothing wrong.

Fixes, with known-answer tests (111 checks):

- `fetcher.pick_encoding` trusts the HTTP header first, then the page's own
  `<meta charset>`, and only then chardet's guess.
- `cleaner.strip_invisible` removes soft hyphens and zero-width characters
  from the text the model reads, so the model never sees them.
- The worksheet builder and `match_key` strip them as well, so an answer key
  and a model answer cannot differ by an invisible character.

The three affected worksheets (045, 079, 086) were rebuilt; none had been
labelled yet.

### The same company listed twice (2026-09-25)

Industrieverband Klebstoffe lists Evonik Industries AG twice, once for
Darmstadt and once for Marl, each with its own address and phone number; six
names on that page repeat this way, 157 lines for 151 distinct companies.
Across the labelled pages so far: 1,978 lines, 1,972 distinct companies.

**The rule:** the answer key records the page as printed, repeats included,
and **scoring counts distinct companies**. `score()` compares sets of
normalised names, so a model that returns Evonik once scores 1.0 precision and
1.0 recall against a key holding it twice, and one that returns it twice is
not rewarded either. Network-level completeness counts distinct companies too.

**Where this will need more care:** the record arm returns a name *with* an
address, so Evonik Darmstadt and Evonik Marl are two different records there.
Scoring records by name alone would merge them. If the record arm is scored
per record rather than per company, the key has to become name plus postcode.
Noted as a limitation rather than solved, since the deliverable's own
uniqueness rule (Marco, 2026-08-07) is name plus city.

### A scoring change the labelling exposed (2026-09-24)

KliWaTex prints every member twice, once as a heading and once above its
address, and the two printings do not always use the same spelling:

| one printing | the other | scored before the fix |
|---|---|---|
| Wilfried Keßler Erdbau- **und** Abbruch GmbH | Wilfried Keßler Erdbau **&** Abbruch GmbH | two different firms |
| Plauener Spitzen **&** Stickereien GmbH | Plauener Spitzen **und** Stickereien GmbH | two different firms |
| A. Richter Kälte- **u.** Klimatechnik | A. Richter Kälte- **und** Klimatechnik | two different firms |

A model copying the other spelling therefore took a miss and a false alarm for
one company. `match_key` now drops the joining words `und`, `u` and `and`
along with the legal suffix. Known-answer tests cover both directions: the
spellings above must match, and "Siemens" must still not match "Siemens
Energy", "Müller und Sohn" not "Müller und Tochter" (101 checks).

Two consequences:

- **Scores in `results/benchmark_results.csv` were computed with the old
  matcher.** They stay as the record of the ten-page study; the 30-page run
  recomputes everything with the new one. Do not mix the two in one table.
- **The check surfaced a duplicate in round 1**: page 005 (automotive
  thüringen) lists "SUR-TECH Surface Technology GmbH" and "Sur-Tech
  Surface-Technology GmbH", one company under two spellings. Its answer key
  holds 125 lines but 124 distinct companies, which is why the deliverable
  audit in §3.13n counted 124 there. Worth deleting one line before the rerun.

### Effort

About 1,450 entries by the legal-form count, roughly twice round 1; VOICE
alone has about 328. Real counts will differ, because names without a legal
form are not in the estimate.

### Limits of the method

- The final choice involves judgement. It is purposive, not random; the
  reason for every page is recorded.
- The layout classification is heuristic.
- Pagination detection sees the saved HTML only.

---

## 3.13o Cloud models through the Constructor Model API (2026-09-15)

Constructor Learn's "Model" section has an API. A key is created under
Model > API Keys and is shown **once**; requests go through a "knowledge
model" the account owns (created private, via the API).

**What the key reaches.** `GET /language_models` returned 92 entries from
OpenAI, Google, Anthropic, xAI, Together AI and Constructor itself. Two of
them match the local study's models:

| cloud entry | hosted by | local counterpart |
|---|---|---|
| `llama3.1:8b-instruct-q4_K_M` | Constructor | `llama3.1:8b`, same quantisation as Ollama's default |
| `Qwen/Qwen3.5-9B` | Together AI | `qwen3.5:9b` (quantisation of the hosted copy not known) |

That allows a comparison the thesis does not otherwise have: **the same
model run locally and hosted**, so any difference is attributable to the
hosting rather than the model.

**Measured on a two-company test request:**

| check | result |
|---|---|
| knowledge model settings | no system message; nothing is added to our prompts |
| latency | 4.6 to 6.4 s (`gpt-4.1-mini`), 15.3 s (`gemini-3.6-flash`) |
| temperature 0 | accepted; whether it is applied is not yet verified |
| token counts | always 0: cloud runs can report time, not tokens |
| answer | **returned twice, concatenated**, for every model tried, with `stream` sent as the string "false" and as a real `false` |
| `response_format` `json_object` | rejected: only `text` or `json_schema` are allowed |
| `json_schema` | accepted for `gpt-4.1-mini`; rejected for `claude-haiku-4-5` ("not supported with this model"); accepted for `gemini-3.6-flash`, whose answer still came in a markdown fence, so not enforced |

**Consequences for the comparison.** Cloud runs use `prompt_only`, the mode
the local winners used, since constrained output is available for one
provider only. Speed is compared on wall-clock time only.

**The doubled answer, and why it is removed in code.** The pipeline's JSON
repair would recover the first copy anyway, but it would flag every cloud
answer as repaired and so misreport the cloud models' JSON reliability.
`cloud_client.undouble` removes an exact second copy only; two different
answers are left for the repair step (known-answer tests in
`test_metrics.py`). This is a property of the platform and belongs in the
limitations, not in the model comparison.

---

## 3.13n The full-record run fails silently on long pages, and the deliverable fix (2026-09-15)

Counting the deliverable against the ground truth, instead of scoring each
stage on its own, showed that the file from §3.13m held **401 of the 760**
ground-truth companies.

| network | members on page | in the file before the fix |
|---|---:|---:|
| SPECTARIS | 296 | 0 |
| automotive thüringen | 124 | 71 |
| the other eight | 340 | 330 |
| **total** | **760** | **401** |

SPECTARIS was known (§3.13k). automotive thüringen was not. No
`llama3.1:8b` full-record run on that page, across all 18 (three strategies,
two JSON modes, three repetitions), found more than 71 of its 124 members,
and 15 of the 18 finished without any error. The chosen configuration returned
exactly 72 records in all three repetitions, which looks like a complete,
stable result. The names-only winner found 123 of 124 on the same page and 295
of 296 on SPECTARIS, identically in all three repetitions.

**Why it went unnoticed.** Every per-stage number was correct. Website F1 is
computed per run against the page, stages 3 and 4 against their own queues,
and each looked healthy. The loss existed only at the level of the merged
file, and nothing checked that level. It belongs with silent context
truncation and the cleaner dropping links (§3.13c): a component reporting
success on incomplete output.

The two affected pages are the two longest member lists in the corpus (296
and 124; the next is 79). Asking for seven fields per company multiplies the
output per member. Whether the run hits an output limit or the model ends the
list early was not isolated, and should not be stated as a cause.

### The fix

`export_deliverable.py`, function `merge_page`:

1. **Names from both runs.** The full-record run's records, plus every company
   the names-only run found that the full-record run did not.
2. **Websites in order of evidence.** The address the model returned; else the
   address the page itself pairs with that name, using the same code as the
   stage 2 ceiling (`link_coverage.websites_on_page`); else the profile page;
   else a verified search result. No address is guessed from a name.
3. **A warning that was missing.** When the full-record run returns fewer than
   80% of the companies the names-only run found, the export prints a warning
   and marks the page in the Summary sheet. It fired on exactly the two
   affected pages and on none of the other eight.

`test_metrics.py` gained 12 known-answer checks for the merge, including cases
where the warning must stay silent (68 checks, all pass). Moving the pairing
code into a shared function left stage 2 unchanged: `link_coverage.csv` has
the same SHA-256 hash before and after.

### Result

| | before | after |
|---|---:|---:|
| rows in the file | 409 | 763 |
| ground-truth companies in the file | 401 of 760 | **752 of 760** |
| company recall / precision | 0.528 / 0.980 | **0.989 / 0.986** |
| ground-truth companies with a website | 336 (44%) | **684 (90%)** |
| pages flagged incomplete | not checked | 2 |

| page | network | members | found | missing | not in ground truth | with website |
|---|---|---:|---:|---:|---:|---:|
| 004 | Automotive Nordwest | 33 | 32 | 1 | 1 | 24 |
| 005 | automotive thüringen | 124 | 123 | 1 | 1 | 124 |
| 009 | BDEW | 43 | 41 | 2 | 1 | 40 |
| 012 | BVMed | 50 | 50 | 0 | 0 | 38 |
| 025 | German Water Partnership | 14 | 14 | 0 | 1 | 13 |
| 032 | InnoZent OWL | 79 | 76 | 3 | 3 | 48 |
| 039 | Life Science Nord | 52 | 52 | 0 | 0 | 49 |
| 040 | Medical Valley EMN | 20 | 20 | 0 | 0 | 14 |
| 043 | NMWP.NRW | 49 | 49 | 0 | 2 | 43 |
| 050 | SPECTARIS | 296 | 295 | 1 | 2 | 296 |

"with website" counts rows in the file, so it includes the 11 names not in the
ground truth. At least three of those 11 are a member written with extra text
("Allego GmbH c/o Design Offices", "Brunel GmbH – neue Adresse ab
01.02.2025", "Goldbeck Nord GmbH Niederlassung Bremen"); the rest were not
checked.

| website source | rows | share |
|---|---:|---:|
| directory page, paired in code (no model) | 349 | 46% |
| directory page, returned by the model | 138 | 18% |
| web search, verified (stage 4) | 100 | 13% |
| profile page (stage 3) | 97 | 13% |
| web search, domain evidence only | 5 | 1% |
| none | 74 | 10% |

**The largest single source of websites is now code, not the model.** This
sharpens §3.13m: the benchmark decides which model reads the page, but most of
the delivered websites come from fetching, pairing and searching.

### Source dataset column (Marco, 2026-09-24)

Neovation reports the publicly funded ZIM networks separately from the
privately funded ones, so the deliverable carries a **source dataset** column
per row rather than leaving the split to be rebuilt by hand. It is joined in
Python: the Finalv1 sheet's own "Source dataset" value, matched by host; if
the network is not in that sheet, the list the URL was collected in
("Private funded", "Technical association"); never a guess, and "unknown" when
neither applies. On the current ten pages that gives 476 rows privately funded
and 287 from the technical-association list; the ZIM networks arrive with the
20 new pages.

### Verification, and its limit

Scoring the paired websites against `link_coverage.csv` would be circular:
that file is built by the same pairing code. The independent evidence is:

- **Hand check:** 16 randomly sampled paired websites, 8 from SPECTARIS and 8
  from automotive thüringen, each read against the page text. In every case
  the address is printed in the same block, directly under that company's name
  and address. 16 of 16 correct.
- **Agreement with the model:** where the model returned an address for a
  company whose website is printed on the page, it matched the page's pairing
  on 131 of 131 companies.

Sixteen is a small sample. The 30-page run should check more.

### For the thesis

- **The best benchmark configuration was not enough to build the deliverable.**
  The full-record winner silently loses most of the two longest pages.
  Splitting the task, names from one run and websites paired from the page,
  beats asking for everything at once, on exactly the pages where asking for
  everything fails. §3.13k observed this for SPECTARIS; §3.13n shows it on a
  second page, and shows that the failure can look like success.
- **Validate the final output, not only each stage.** Every per-stage metric
  here was correct, and together they missed 359 companies.

Counted with `benchmark.match_key` against `data/ground_truth/*.json`, after
`.venv/bin/python export_deliverable.py`.

---

## 3.13m The deliverable with all four stages merged, before the long-page fix (superseded by §3.13n)

> **Correction (2026-09-15).** The figures in this section describe the file
> *before* the fix in §3.13n. "82%" is a share of the 409 companies that were
> in the file; the file held only 401 of the 760 ground-truth companies, so as
> a share of all 760 it was 44%. The "members" column in the per-network table
> counts companies in the file, not on the page: automotive thüringen has 124
> members, of which the file held 71. Use §3.13n.

All three sources merged for the first time. `llama3.1:8b` +
`few_shot_full_record` + `prompt_only` over 9 of the 10 ground-truth networks
(SPECTARIS absent, §3.13k), plus stage 3 profile pages and stage 4 search.

**409 companies, 336 with a website: 82% of the 409, 44% of the 760
ground-truth companies.**

| website source | companies | share |
|---|---:|---:|
| directory page (stage 1, the model) | 138 | 34% |
| profile page (stage 3, fetch + model) | 97 | 24% |
| web search verified (stage 4) | 97 | 24% |
| web search, domain evidence only | 4 | 1% |
| none | 73 | 18% |

**No single stage supplies even half.** The model reading the directory page,
the best-measured part of this work and the whole subject of the benchmark,
accounts for 34%. That is the most useful thing this table says: the model
comparison answers which tool to use for a third of the problem, and the other
two thirds are solved by fetching and searching, neither of which needs a model
at all.

### Contact fields, which the directory listings did not have

| field | companies | share |
|---|---:|---:|
| city | 291 | 71% |
| street | 175 | 43% |
| postcode | 174 | 43% |
| phone | 120 | 29% |
| email | 39 | 10% |

Almost all of this comes from stage 3. Directory listings print an address for
a handful of members; profile pages carry one about 90% of the time. These are
the fields Marco and Yusif asked for so that two companies with the same name
in different cities can be told apart, and before stage 3 they were empty.

### Per network, and why the spread is the finding

| network | members | with website |
|---|---:|---:|
| automotive thüringen | 72 | 100% |
| BDEW | 42 | 95% |
| Life Science Nord | 52 | 94% |
| German Water Partnership | 12 | 92% |
| NMWP.NRW | 49 | 82% |
| BVMed | 50 | 76% |
| Automotive Nordwest | 33 | 73% |
| Medical Valley EMN | 20 | 70% |
| InnoZent OWL | 79 | 61% |

Every network is above 60% and four are above 90%, but they get there by
different routes. automotive thüringen prints every website on the page, so
stage 1 alone reaches 100%. Life Science Nord prints none and links every
member to a profile page, so it goes from 2% to 94% entirely through stage 3.
InnoZent OWL prints neither and depends wholly on search, which is why it
finishes lowest.

**A pipeline built on any one of these stages would have failed on most of the
corpus.** That is the practical result, and it is not a statement about models.

---

## 3.13k The deliverable before stage 3 and 4 were merged

`export_deliverable.py` now builds the workbook from the configuration the
study chose rather than from whichever run happened to return the most rows.
That default was wrong for a deliverable: volume is not accuracy, and the most
prolific run on a page can come from the model that fabricates (§3.13j).

Current output, `llama3.1:8b` + `few_shot_full_record` + `prompt_only`:

- **409 member records from 9 of the 10 networks**
- **138 carry a company website, 34%**

### SPECTARIS is missing, and no configuration can supply it

All three repetitions failed on page 050 with `unparseable JSON`. Checking
every other full-record configuration on that page: only qwen's
`few_shot_full_record` produced anything at all, and it returned **3 companies
out of 296** (F1 0.013).

**No configuration in the study extracts full records from the largest page in
the corpus.** 4,203 words, three chunks, 296 members: asking for seven fields
per company exceeds what any of these models completes. That is a limitation
of the one-pass full-record approach, not of a particular model, and it should
be stated as such.

The workaround is already available and is worth reporting as the practical
recommendation: extract **names** with the names-arm winner, which scores
F1 0.995 on that page, then attach websites from the page separately. 295 of
SPECTARIS's 296 companies have a website printed beside them, and the
positional pairing in `link_coverage.py` recovers it without a model. Splitting
the task beats asking for it all at once, on exactly the page where asking for
it all at once fails.

**Done on 2026-09-15 (§3.13n).** SPECTARIS now contributes 295 of its 296
members to the deliverable. The same fix recovered 52 members of automotive
thüringen, where the full-record run had also failed, but without any error.

### Why 34% coverage is the expected number, not a disappointment

Against the ceiling from §3.13d rather than against 100%:

| route | companies | share | who can supply the website |
|---|---:|---:|---|
| website on the page | 481 | 63% | stage 1, the model |
| profile page only | 115 | 15% | stage 3, one fetch each |
| no link at all | 165 | 22% | stage 4, web search |

The deliverable's 34% reflects that it currently runs stage 1 only, over 9
pages, one of which (SPECTARIS, 295 of the 481) is missing. The remaining 37%
was never reachable in one pass.

---

## 3.13l Stage 4: web search, and why verification is the whole job

Built as `search_websites.py`. Handles the 165 companies with no link of any
kind. No model: a search returns candidates and Python decides whether any
belongs to the company, which is string and hostname comparison.

### The failure mode is accepting a plausible wrong answer

A search always returns something. Every result looks reasonable. The value of
this stage is refusing the ones that are wrong, for the same reason a
fabricated URL is worse than a blank cell: a blank is visibly missing, a
plausible wrong domain is a bad record nobody catches.

The first live test of ten companies made this concrete. Eight results passed
a name-appears-on-the-page check, and **three of those eight were business
directories**:

```
Allego GmbH        -> elektro-einkaufsfuehrer.de     supplier directory
A. Höfer GmbH      -> lieferanten.de/lieferant-653   supplier directory
Abbott Medical     -> online-handelsregister.de      company registry
```

A directory naturally mentions every company it lists, so "the page names the
company" is satisfied by exactly the results that are wrong.

### The heuristic that fixed it

A blocklist cannot enumerate the German B2B directory long tail. What
distinguishes them is structural:

> A company's own site carries its name in the **hostname**
> (`hoefer.de`). A directory carries it in the **path**
> (`lieferanten.de/lieferant-653-hoefer`).

Rejecting results whose name-match is in the path and not the domain moved
Allego to `allego.eu` and Abbott Medical to `abbott.com`, both correct, in the
same ten-company sample.

### Four outcomes, reported separately

| status | meaning | safe to load |
|---|---|---|
| `verified` | domain resembles the name **and** the page mentions it | yes |
| `domain_match` | domain resembles the name, page not confirmed | yes |
| `page_only` | page mentions the name, domain does not resemble it | **no**, usually a directory |
| `unverified` / `no_result` | nothing survived the filters | no |

Collapsing `page_only` into "found" would inflate the coverage figure with
exactly the results most likely to be wrong, so it is counted apart.

### Known limits, measured on the ten-company sample

- **Similar names are not separable.** `TARGO Leasing GmbH` resolves to
  `targobank.de`: the domain genuinely resembles the name and the page
  genuinely mentions it, but they are different companies. No string test
  distinguishes these; only an address or registry check would.
- **Short names fall through.** `aap Implantate AG` is correct at `aap.de`,
  but a three-character token is below the matching threshold, so it is
  reported as `page_only`. The threshold exists to stop three-letter fragments
  matching everything, and lowering it would cost more than it gains.

Both push in the safe direction: `page_only` under-claims rather than
over-claims. For a database that is the right way to be wrong.

### Result over all 165 companies

| status | count | share |
|---|---:|---:|
| `verified` | 105 | 64% |
| `domain_match` | 8 | 5% |
| `page_only` (rejected) | 25 | 15% |
| `unverified` | 19 | 12% |
| `no_result` | 8 | 5% |
| **confirmed and loadable** | **113** | **68%** |

A hand inspection of 14 randomly sampled confirmed results found **13
correct**. The one error is instructive: `Hochschule Bielefeld` matched
`chancenportal-bielefeld.de` on the token "bielefeld", a city rather than the
institution. Place names are now stopwords, and the check then prefers
`hsbi.de` correctly. The general case needs a gazetteer.

Inspecting the 25 rejected as `page_only`, most are in fact correct
(`aap.de`, `de.abbott`, `investors.bd.com`, `bgs.eu`). The filter is
deliberately conservative and the cost is visible: roughly 15 correct answers
are withheld to keep out a smaller number of directory entries. For a database
Neovation will act on, that trade is the right way round, but it should be
reported rather than hidden inside a coverage percentage.

### End-to-end coverage, the number this project is for

| stage | who supplies it | companies | share |
|---|---|---:|---:|
| 1 | model, website printed on the page | 481 | 63% |
| 3 | profile page fetch (96% carry a website) | 110 | 15% |
| 4 | web search, confirmed | 113 | 15% |
| | **reachable in total** | **704** | **93%** |
| | still without a website | 57 | 7% |

**93% of 761 member companies can be given a verified website**, against the
63% any single-pass extraction could reach. The three stages are complementary
rather than redundant: each covers a distinct failure of the one before, and
none of them alone gets past two thirds.

This is what the pipeline can **reach**, not what was **delivered**. The
deliverable held a website for 336 of the 760 ground-truth companies (44%)
until the long-page fix, and holds one for 684 (90%) after it (§3.13n).

That framing is the practical contribution alongside the model comparison. The
benchmark answers which model to use; this answers what the pipeline as a whole
can actually deliver, and shows that the answer depends far more on how each
directory publishes its data than on which model reads it.

---

## 3.13j URL arm complete: 960 runs, and why name accuracy alone picks the wrong model

All three models, three strategies, two JSON modes, ten pages, three
repetitions. `results/benchmark_results.csv` now holds 960 rows and
`results/extractions_long.csv` 41,802 extracted records.

### The finding that matters most for the deliverable

On **name** accuracy in the URL arm the top two models are indistinguishable:

| model | strategy | JSON | name F1 |
|---|---|---|---:|
| qwen2.5-coder:7b | zero_shot_full_record | prompt_only | **0.859** |
| llama3.1:8b | few_shot_full_record | prompt_only | **0.858** |

A one-thousandth difference across 30 runs each. On that evidence alone the two
models are interchangeable for this task.

On **website** accuracy they are not close at all:

| model | strategy | JSON | web P | web R | web F1 |
|---|---|---|---:|---:|---:|
| llama3.1:8b | few_shot_full_record | prompt_only | 0.949 | 0.708 | **0.811** |
| llama3.1:8b | zero_shot_full_record | prompt_only | 0.953 | 0.654 | 0.776 |
| llama3.1:8b | few_shot_full_record | constrained | 0.941 | 0.658 | 0.774 |
| llama3.1:8b | zero_shot_full_record | constrained | 0.950 | 0.487 | 0.644 |
| qwen2.5-coder:7b | few_shot_full_record | either | 0.907 | 0.368 | 0.524 |
| llama3.1:8b | multi_stage_full_record | constrained | 0.969 | 0.328 | 0.490 |
| qwen2.5-coder:7b | zero_shot_full_record | constrained | 0.898 | 0.310 | 0.461 |
| llama3.1:8b | multi_stage_full_record | prompt_only | 0.963 | 0.217 | 0.354 |
| qwen2.5-coder:7b | multi_stage_full_record | either | 0.929 | 0.217 | 0.352 |
| gemma4:12b | any | either | 1.000 | 0.057 | 0.108 |

**llama's best is 0.811, qwen's best is 0.524.** The same two configurations
that tie on names differ by 0.29 on websites.

**Two models can be equally good at finding company names and very unequal at
binding a website to the right one.** Had this study measured only the metric
the guideline asked for, it would have declared the models equivalent and the
deliverable would have been built on the weaker one. This is the strongest
argument in the thesis for scoring every field the deliverable actually needs,
rather than the one the ground truth happens to contain.

### Hallucination is a property of the model, not of the task

| model | invented | returned | rate |
|---|---:|---:|---:|
| llama3.1:8b | 7 | 2,431 | **0.3%** |
| qwen2.5-coder:7b | 45 | 2,114 | **2.1%** |
| gemma4:12b | 0 | 42 | 0.0% |

Same prompts, same pages, same instruction never to infer a URL from a company
name. qwen fabricates web addresses at seven times llama's rate, and 45 of the
52 fabrications in the entire study are its `zero_shot_full_record` runs.
gemma4's zero is not a virtue: it returned 42 addresses in total.

For a database Neovation will act on, a 2.1% fabrication rate is
disqualifying in a way that a lower recall is not. A missing website is a task
for stage 3 or 4; a plausible wrong domain is a bad record nobody will catch.

### gemma4:12b is not usable for record extraction

Website recall **0.057**. It returned 42 addresses across 180 runs where llama
returned 2,431. Its precision of 1.000 is an artefact of near-total abstention.

Its ordering across strategies also inverts: `few_shot_full_record` is its
**worst** configuration (name F1 0.167, 25 failures of 30) while
`generic_multi_stage` is its best (0.603). More structure in the prompt makes
it worse, which is the opposite of the pattern in both working models.

### Final configuration for the deliverable

**`llama3.1:8b` + `few_shot_full_record` + `prompt_only`.**

- name F1 0.858, the joint best in the URL arm
- website F1 0.811, clear of everything else by 0.29
- **zero fabricated addresses in 414 returned**
- 348 s/page, roughly half the cost of either zero-shot variant

Note this is a different configuration from the names-arm winner
(`zero_shot` + `prompt_only`, F1 0.981). The thesis reports both, and the
distinction is the point: the best configuration depends on which fields the
task requires.

---

## 3.13i URL arm, llama3.1:8b complete (180 runs): what the extra fields cost

llama3.1:8b finished all three strategies under both JSON modes on the URL
arm. This is the answer to the question §3.11c raised before any of it ran.

### The ranking does not transfer

Names only (from §3.13) against the same approach asked for the full record:

| approach | names only | with full record | cost |
|---|---:|---:|---:|
| zero-shot | 0.981 | 0.855 | **-0.126** |
| few-shot | 0.955 | 0.858 | -0.097 |
| multi-stage | 0.824 | 0.747 | -0.077 |

**Zero-shot's advantage disappears.** It leads by 0.026 on names and by
-0.003 on records, which is to say not at all. The strategy that loses least
is the one that was already behind, and the ordering at the top inverts within
noise. Assuming the names-arm winner would carry over, which was the tempting
shortcut, would have been wrong.

### Name accuracy, all twelve llama configurations

| strategy | JSON | name P | name R | name F1 | s/run |
|---|---|---:|---:|---:|---:|
| zero_shot | prompt_only | 0.983 | 0.978 | **0.981** | 26 |
| zero_shot | constrained | 0.982 | 0.978 | 0.980 | 26 |
| few_shot_schema | constrained | 0.977 | 0.942 | 0.955 | 24 |
| few_shot_schema | prompt_only | 0.977 | 0.933 | 0.950 | 23 |
| few_shot_full_record | prompt_only | 0.960 | 0.831 | 0.858 | 348 |
| zero_shot_full_record | constrained | 0.950 | 0.833 | 0.855 | 538 |
| few_shot_full_record | constrained | 0.961 | 0.824 | 0.852 | 346 |
| zero_shot_full_record | prompt_only | 0.946 | 0.827 | 0.846 | 635 |
| generic_multi_stage | constrained | 0.986 | 0.720 | 0.824 | 59 |
| generic_multi_stage | prompt_only | 0.986 | 0.701 | 0.810 | 56 |
| multi_stage_full_record | constrained | 0.987 | 0.630 | 0.747 | 367 |
| multi_stage_full_record | prompt_only | 0.986 | 0.593 | 0.696 | 642 |

**Precision barely moves; recall collapses.** Across every strategy precision
stays between 0.946 and 0.987 whether one field is requested or seven. Recall
falls from 0.978 to 0.83 for zero-shot and from 0.942 to 0.824 for few-shot.
The model does not become less accurate about what a company is. It stops
sooner, because each record now costs seven fields instead of one name, and
the same output-length ceiling that truncates long pages (§3.13) is reached
after fewer companies.

### The runtime cost is the larger finding

| | names only | full record | factor |
|---|---:|---:|---:|
| zero-shot | 26 s | 538-635 s | **21-24x** |
| few-shot | 23-24 s | 346-348 s | 15x |
| multi-stage | 56-59 s | 367-642 s | 7-11x |

Asking for six extra fields costs an order of magnitude in wall clock, far more
than the roughly 2x growth in output tokens would suggest. For a production run
over 291 networks this is the difference between two hours and two days, and it
is the single most important number for deciding whether to extract contact
details in one pass or to fetch profile pages afterwards (§3.13f).

Note also that zero-shot is now the **slowest** strategy at 538-635 s, having
been the fastest on names. With no worked example the model generates far more
per record, and few-shot's example evidently constrains that. The same anchoring
that hurt few-shot on long name lists (§3.13) helps it here.

### Website field: few-shot wins clearly

Scored with `score_websites.py`, so "correct" means the address that belongs to
that company, not merely one printed on the page:

| strategy | JSON | web P | web R | web F1 |
|---|---|---:|---:|---:|
| few_shot_full_record | prompt_only | 0.949 | 0.708 | **0.811** |
| zero_shot_full_record | prompt_only | 0.953 | 0.654 | 0.776 |
| few_shot_full_record | constrained | 0.941 | 0.658 | 0.774 |
| zero_shot_full_record | constrained | 0.950 | 0.487 | 0.644 |
| multi_stage_full_record | constrained | 0.969 | 0.328 | 0.490 |
| multi_stage_full_record | prompt_only | 0.963 | 0.217 | 0.354 |

**`few_shot_full_record` + `prompt_only` is the configuration to use for the
deliverable.** It leads on both name F1 (0.858) and website F1 (0.811), and is
roughly twice as fast as either zero-shot variant.

That few-shot wins here and lost on names is explicable rather than surprising:
a seven-field record has a shape, and a worked example communicates that shape
in a way a schema description does not. On a flat list of names there was no
shape to demonstrate, so the example only capped output length.

**Multi-stage is catastrophic for websites**, at recall 0.217-0.328. The
validation stage discards whole records, and a discarded record takes its
website with it. §3.13c-2 established that validation deletes correct entries;
this shows the cost compounds when each entry carries more.

### Invention stays near zero

7 fabricated addresses out of 2,635 returned, **0.27%**, and all 7 came from
`constrained` runs. The abstention property holds across every strategy.

---

## 3.13h Extracting a website is a harder task than extracting a name

First scored results from the URL arm, `llama3.1:8b` + `zero_shot_full_record`
+ constrained, 9 runs (partial, the arm is still running):

| | count |
|---|---:|
| addresses returned | 379 |
| correct, the right address for that company | 361 |
| wrong company, a real address bound to the wrong member | 18 |
| invented, not on the page at all | **0** |
| precision | 0.953 |
| recall, against the 481-company ceiling | 0.650 |

Per page:

| page | returned | correct | wrong company | precision | recall |
|---|---:|---:|---:|---:|---:|
| 005 automotive thüringen | 178 | 178 | 0 | 1.000 | 0.486 |
| 009 BDEW | 120 | 114 | 6 | 0.950 | 0.974 |
| 043 NMWP.NRW | 81 | 69 | 12 | 0.852 | 0.958 |

Website F1 is therefore **0.773**, against roughly **0.98** for names with
the same model. **Binding an address to the right company is a harder task
than recognising the name**, and the gap is the result. Note where the
difficulty sits: precision is high (0.953), so what the model returns is
almost always right, and recall on two of the three pages is above 0.95. The
gap is recall on page 005 alone, which finds 178 of 369 available across three
runs. That is the two-chunk
page, so this is the output-length ceiling seen throughout (§3.13), not a
failure to understand the task.

§3.11c predicted this before any of it was run: adding the field makes the task
relational rather than one of recognition. The model must decide that
`http://www.2mag.de`, printed three lines below `2mag AG` and labelled only
"Web", belongs to that company and not to the one above or below it. On pages
where entries are separated by nothing but line order, that inference is the
whole job.

### Two failure modes that must be reported separately

**Invention: zero.** Every one of the 379 addresses appears in the page text.
The "never infer a URL from a company name" rule holds, and this matches the
abstention seen on address fields (§3.11e). For the deliverable this is the
property that matters most: a blank cell is recoverable downstream, a
fabricated domain silently corrupts the database.

**Misattribution: 5%.** 18 of 379 are genuine addresses from the page attached
to the wrong member. **No metric in this project caught this before.** The
original check asked only whether a returned address appeared somewhere on the
page, and a partner's link bound to a member company passes that test. The
distinction only became visible once scoring compared against *which* company
each address sits with (§3.13d).

Precision on the website field is therefore 0.953, not the 1.000 the earlier
check implied. The difference is small in this configuration but it is the
only measure that can detect the failure at all, and misattribution is the
error that silently corrupts a database, since a wrong-but-real address looks
entirely plausible in a spreadsheet.

### Method note worth carrying into the write-up

The scorer itself was wrong on its first attempt, and in a way that would have
been damaging: it built its "addresses really on this page" set from the
ground-truth matches rather than from the page, so every link belonging to an
unannotated company or a sponsor counted as invented. It reported **48
hallucinations that were not hallucinations**.

That is the fourth instance in this project of a component producing plausible
wrong output without failing: silent context truncation (§3.2), link
annotation running after images were stripped (§3.13c), the CSV header
mismatch (§3.13g), and now a metric comparing against the wrong reference.

The pattern is specific enough to state as a lesson: **scoring code needs the
same scrutiny as extraction code, and arguably more.** A broken extractor
produces obviously poor numbers. A broken metric produces confident numbers
that are wrong, and nothing downstream objects. Both a false "the model
hallucinates 13% of the time" and a false "precision is 1.000" were one
careless line away here, and each would have reached the thesis as a finding.

---

## 3.13f The production pipeline: four stages, and what each one is worth

The benchmark answers "which model and prompt". The production pipeline is a
different thing: it uses **one** model and **one** prompt, the winner, and
runs four stages to fill Neovation's database. Conflating the two caused real
confusion and is worth stating plainly in the write-up.

| stage | who does it | what | code |
|---|---|---|---|
| 1 | model | names + website where the directory prints one | `benchmark.py --stage b` |
| 2 | Python | sort each company into website / profile / none | `link_coverage.py` |
| 3 | fetch + model | open profile pages, read website and contact details | `fetch_profiles.py` |
| 4 | Python + search | find whatever is still missing | not built |

Stages 2 and 4 use no model. Deciding whether a link points at the association
or at a company is a hostname comparison, which Python does exactly and for
free.

### Stage 3, measured (`fetch_profiles.py`)

114 profile pages queued from the ground-truth corpus (115 companies, a few
sharing a page), 112 fetched. What those pages contain, by plain text search
with no model involved:

| field | present | 
|---|---:|
| website | 96% |
| postcode | 97% |
| street | 66% |
| email | 37% |
| phone | 28% |

Median page length is **112 words**, one chunk, so extraction here is cheap
compared with a directory page of several thousand words.

This is the answer to a question open since the meetings of 12-13 August:
**the address and contact fields Marco and Yusif asked for are on the profile
pages, not in the directory listings.** BDEW's listing gives 42 members with
2 streets, 0 postcodes and 0 phones (§3.11e); its profile pages give 97%
postcodes. The fields were never missing from the web, only from the page the
pipeline was reading.

Stage 3 splits into `--fetch-only` and extraction, because fetching 114 pages
politely is minutes of waiting that should not compete with a benchmark for
the GPU.

### Two bugs found building this, both about resolving links

**`<base href>` was ignored.** Life Science Nord serves its member list from
`/de/mitglieder/member-companies.html` but declares
`<base href="https://www.lifesciencenord.de/">`, so its relative links are
written as `de/mitglieder/...`. Resolving those against the page URL instead
of the declared base produced `/de/mitglieder/de/mitglieder/...` and **all 51
of its profile pages returned 404**. Fixed in `link_coverage.py` and
`dump_extractions.py`; cached pages went from 50 to 101.

**Links written without a scheme are not recovered.** `href="www.meotec.eu"`
is treated as a relative path by browsers and by `urljoin`, so it is glued
onto the association's domain. Measured across the whole corpus: **4 such
links in 73 pages.** Fixing it properly means changing `cleaner.py`, which
would alter what the model sees and break comparability with every run already
completed, for four links. Recorded as a known limit and deliberately not
fixed, on the same reasoning that kept page 043 the only changed page in
§3.13c.

### What is worth claiming for the thesis

Stage 1 is the thesis. Stages 2 and 4 are engineering. Stage 3 sits in
between and is a fair research question in its own right: it runs a model on a
**different kind of page**, one company instead of a directory of hundreds, so
whether the stage 1 winner also wins there is not obvious and is cheap to
test. The coverage split (§3.13d) is a finding regardless of who computes it.

---

## 3.13g A silent CSV bug, and why it is worth reporting

Adding the five URL columns to `CSV_FIELDS` broke the results file, and the
failure was invisible.

`benchmark.py` appended with `csv.DictWriter(fieldnames=CSV_FIELDS)` but only
wrote a header when the file did not already exist:

```python
is_new = not config.BENCHMARK_CSV.exists()
if is_new:
    writer.writeheader()
```

The file existed, with the old 27-column header. New rows carried 32 values.
Every column after `f1` therefore read back **shifted**: asking for `error`
returned what should have been `url_returned`. The run reported normal
progress throughout.

It also broke resumability, because the skip logic tests `row.get("error")`,
which was now the string `"0"` rather than empty, so completed runs would have
been repeated.

Detected only because a summary command raised `KeyError: 'url_returned'`.
Nothing was lost: values were present and in order, so the file was repaired
by padding the old rows.

`benchmark.py` now compares the header on disk against `CSV_FIELDS` at
startup and migrates by column name, keeping the previous file alongside.

**Why it belongs in the write-up.** This is the third instance of the same
failure mode in this project, after Ollama's silent context truncation (§3.2)
and link annotation running after `img` was stripped (§3.13c). In all three a
component kept reporting success while producing wrong output, and in all
three the error surfaced only because something downstream happened to look.
For a pipeline whose output is thousands of rows nobody reads individually,
**the useful discipline is not "check the code" but "make each stage assert
something about its own output"**: that the context was not exceeded, that
links survived cleaning, that the header matches the rows.

---

## 3.13e Temperature 0 does not guarantee reproducibility

Found while investigating why gemma4's multi-stage failure rate collapsed
(§3.13c-2). This corrects a claim made earlier in this document and repeated
in the README, and it changes the experimental design going forward.

### What was claimed, and what is actually true

The claim was that output is deterministic at `temperature=0` with `seed=42`,
based on the winning configuration showing an F1 standard deviation of exactly
0.000 across three repetitions on all ten pages. That measurement was correct.
Generalising it to the whole grid was not.

Across all 180 configurations of the original 540-run grid, counting cells
where the three identical repetitions did not agree on F1 or on
success/failure:

| model | non-deterministic cells | rate |
|---|---:|---:|
| qwen2.5-coder:7b | 2 of 60 | 3% |
| llama3.1:8b | 6 of 60 | 10% |
| gemma4:12b | 14 of 60 | 23% |
| **total** | **22 of 180** | **12%** |

Examples from gemma4, same model, same prompt, same page, same seed:

```
zero_shot        constrained  004   F1 = [0.0, 0.9697]   errors = [False, True]
zero_shot        prompt_only  009   F1 = [0.0, 0.9767]   errors = [False, True]
few_shot_schema  constrained  012   F1 = [0.98, 1.0]     errors = [False]
```

The first two are the important shape: on one repetition the run succeeds with
F1 ~0.97, on another it fails outright.

### Why this happens

Sampling is deterministic at temperature 0, but the forward pass is not
bit-identical on a GPU. Floating-point addition is not associative, and
parallel reduction kernels can combine partial sums in different orders
depending on batching, memory layout and concurrent load. Tiny numeric
differences occasionally flip a token choice where two candidates are nearly
tied. Most of the time this changes nothing; occasionally it diverts
generation onto a path that does not terminate.

The rate tracks how close each model runs to the edge: qwen 3%, llama 10%,
gemma4 23%. gemma4 spends most of its time near the context limit where a
single diverted token decides between a clean stop and a runaway, so it is
the most exposed.

### This explains the gemma4 anomaly, without inventing a mechanism

§3.13c-2 recorded that gemma4's multi-stage failures went from 29 of 60 to
0 of 20 after the validator fix, and that the fix could not be the cause since
every failure was recorded at `stage2`, which was not modified.

The resolution is that **gemma4's failure rate is not a stable quantity**.
29 is not divisible by 3, which already showed that identical repetitions were
disagreeing. The re-run's 0 of 20 is not evidence that anything was fixed; it
is a second sample from an unstable process.

Report it that way. "The failure rate varies between identical runs" is a
finding about deployment reliability and is more useful than a spurious
before/after comparison.

### Consequences for the experimental design

1. **Repetitions are not redundant.** Earlier guidance in this document and in
   the README said 3 repetitions measured nothing and recommended `--reps 1`.
   That was wrong for 12% of cells. The guideline's instruction to *"repeat
   non-deterministic runs at least three times"* applies here after all.
2. **The P3 re-run used 1 repetition** (§3.13c-2), so its numbers carry
   unquantified run-to-run variance. The direction of the P3 finding is safe,
   since recall fell in all four model/mode cells for the two working models,
   but the exact values are single samples.
3. **Every gemma4 figure should carry this caveat.** At a 23% instability rate,
   a single run of gemma4 is not a measurement.
4. **Any future arm should use 3 repetitions**, or state plainly that it does
   not and why.

### For the limitations section

This is a genuine reproducibility result and worth stating positively: a reader
who reruns this pipeline with identical settings, seed and hardware **will not
always reproduce these numbers exactly**. That is a property of GPU inference,
not of this pipeline, and it is rarely reported in comparisons of this kind.

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

### The ceiling, measured against ground truth (`link_coverage.py`)

The figures below this heading come from model output on a partial run and are
superseded. The authoritative measurement runs against the **hand-labelled
ground truth**, so it states what is reachable in principle rather than what
one model happened to find, across all 761 companies:

| page | organisation | total | website | profile | none |
|---|---|---:|---:|---:|---:|
| 004 | Automotive Nordwest | 33 | 0 | 32 | 1 |
| 005 | automotive thüringen | 125 | 123 | 0 | 2 |
| 009 | BDEW | 43 | 40 | 2 | 1 |
| 012 | BVMed | 50 | 0 | 0 | 50 |
| 025 | German Water Partnership | 14 | 0 | 12 | 2 |
| 032 | InnoZent OWL | 79 | 0 | 0 | 79 |
| 039 | Life Science Nord | 52 | 0 | 51 | 1 |
| 040 | Medical Valley EMN | 20 | 0 | 0 | 20 |
| 043 | NMWP.NRW | 49 | 12 | 8 | 29 |
| 050 | SPECTARIS | 296 | 295 | 0 | 1 |
| **total** | | **761** | **470 (62%)** | **105 (14%)** | **186 (24%)** |

- **62% is the stage 1 ceiling.** No model can exceed it, because the website
  is not on the page for the other 38%. A model returning a website for one of
  those 291 companies is fabricating it.
- **14% need one profile-page fetch** (stage 3).
- **24% need a web search** (stage 4). Three directories (BVMed, InnoZent OWL,
  Medical Valley) print member names as plain text with no link of any kind,
  which alone accounts for 149 companies.

**A model's website coverage must be read against 62%, not against 100%.**
Reporting "the model found websites for 55% of companies" without that ceiling
would understate it badly; against the ceiling it is 89% of what was available.

### Why this measurement needed two methods, and what that says about the task

The first implementation matched company names against the clickable text of
each link and returned 8%. That was wrong, and the reason is the finding:

```
2mag AG
80992 München
Schragenhofstr. 35
Web <http://www.2mag.de>        <- the link's text is "Web"
```

On SPECTARIS the link is labelled "Web", not with the company name. Nothing in
the markup connects the two; the only thing that does is **the order they
appear in**. A second convention, used by BDEW, prints the name and link on
one line, and a third links the name to a profile page.

So the measurement needs positional logic, and the same is true of the
extraction itself. **This is the concrete argument for using a model rather
than a parser**: a lookup by link text finds 8% of what is there, and the
association a model has to make is positional, not structural. It is also why
preserving links improved *name* extraction (§3.11i): on these pages the
trailing URL is the only marker of where one member's block ends.

---

The figures below are from model output on a partial 459-record run and are
kept for the hallucination result, which the ceiling measurement does not
cover. Across 459 extracted records:

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
- **Results are not fully reproducible, even at temperature 0 with a fixed
  seed.** 22 of 180 configurations returned different output across identical
  repetitions (§3.13e): 3% of qwen cells, 10% of llama, 23% of gemma4. GPU
  floating-point reductions are not bit-stable, and a near-tied token
  occasionally flips. A reader rerunning this pipeline with identical settings
  and hardware will not always reproduce these numbers exactly.
- Following from that, the P3 re-run (§3.13c-2) used a single repetition, so
  its values are single samples. The direction of its finding is safe, since
  recall fell in all four cells for the two working models, but the exact
  numbers carry unquantified variance.
- Every gemma4 figure carries a 23% per-cell instability rate. A single gemma4
  run is not a measurement.
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
