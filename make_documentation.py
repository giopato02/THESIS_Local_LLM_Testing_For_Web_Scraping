"""
Generate the NeoHub work-package documentation in Neovation's template.

Template supplied by Marco (2026-08-11):

    Date · Work Package
    Goal    - why the task is relevant, what should be achieved
              (testing a solution / new feature / addressing a risk)
    Method  - the intended strategy; the emerging strategy where the intended
              one failed; actual state vs target state
    Metrics - how we know the goal was met, and the test process

One document, one section per task, author marked per section (Marco's
requirement so the reader knows whom to ask).

UPDATED REQUIREMENTS (2026-09-22), which this script does not meet yet:

  * at most 10 pages
  * general and readable: no code, no script names, no file paths
  * a summary, not a rigid grid of timeframes and tasks. It may name the
    strategies used and their results: "In June I spent three weeks on X.
    It did not work because Y, so I tried Z. The result was W."

The per-task Goal/Method/Metrics sections below, and the script named in each
Metrics section, have to be rewritten into that form before the report is sent.

Run:  .venv/bin/python make_documentation.py
"""

from __future__ import annotations

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

import config

OUT = config.RESULTS_DIR / "NeoHub_Documentation_AP1_Extraction.docx"

BODY = "Arial"
ACCENT = RGBColor(0x1F, 0x38, 0x64)
MUTED = RGBColor(0x59, 0x59, 0x59)


def setup(doc: Document) -> None:
    st = doc.styles["Normal"]
    st.font.name = BODY
    st.font.size = Pt(10)
    st.paragraph_format.space_after = Pt(6)


def h(doc, text, size=14, color=ACCENT, space_before=14):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(size)
    r.font.color.rgb = color
    r.font.name = BODY
    return p


def meta(doc, label, value):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(f"{label}: ")
    r.bold = True
    p.add_run(value)
    return p


def para(doc, text, italic=False, color=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic = italic
    if color:
        r.font.color.rgb = color
    return p


def bullets(doc, items, level=0):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.left_indent = Pt(18 + 18 * level)
        p.paragraph_format.space_after = Pt(2)
        if isinstance(it, tuple):
            r = p.add_run(it[0] + " ")
            r.bold = True
            p.add_run(it[1])
        else:
            p.add_run(it)


def table(doc, headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, htext in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        r = cell.paragraphs[0].add_run(htext)
        r.bold = True
        r.font.size = Pt(9)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(9)
    doc.add_paragraph()
    return t


def section(doc, *, date, wp, title, author, goal_intro, goal_bullets,
            task_type, intended, emerging, problem, metrics, test_process):
    """One task documented in the supplied template."""
    h(doc, title, size=13)
    meta(doc, "Date", date)
    meta(doc, "Work Package", wp)
    meta(doc, "Author", author)
    meta(doc, "Type", task_type)

    h(doc, "Goal", size=11, space_before=10)
    para(doc, goal_intro)
    if goal_bullets:
        bullets(doc, goal_bullets)

    h(doc, "Method", size=11, space_before=10)
    para(doc, "Intended strategy", italic=True, color=MUTED)
    for t in intended:
        para(doc, t)
    para(doc, "Problem: actual state vs target state", italic=True, color=MUTED)
    for t in problem:
        para(doc, t)
    para(doc, "Emerging strategy", italic=True, color=MUTED)
    for t in emerging:
        para(doc, t)

    h(doc, "Metrics", size=11, space_before=10)
    for t in metrics:
        para(doc, t)
    para(doc, "Test process", italic=True, color=MUTED)
    for t in test_process:
        para(doc, t)

    doc.add_paragraph("_" * 78).alignment = WD_ALIGN_PARAGRAPH.LEFT


def build() -> None:
    doc = Document()
    setup(doc)

    # ---- Title -----------------------------------------------------------
    h(doc, "NeoHub, Work Package 1: Unternehmensdatenbank", size=17)
    h(doc, "Documentation: LLM-based extraction of member companies from "
           "innovation-network websites", size=11, color=MUTED, space_before=2)
    meta(doc, "Author", "Giorgi Pataridze (Constructor University Bremen)")
    meta(doc, "Partner", "Neovation GmbH × Constructor University Bremen")
    meta(doc, "Period covered", "July - August 2026")
    para(doc, "Prepared using the documentation template supplied by Marco "
              "Sparovek on 11.08.2026. Every figure quoted was measured; the "
              "producing script is named in each Metrics section.",
         italic=True, color=MUTED)

    doc.add_page_break()

    # ---- Task 1: extraction pipeline ------------------------------------
    section(
        doc,
        date="26.07.2026 - 04.08.2026",
        wp="1. Unternehmensdatenbank",
        title="Task 1, Generic LLM extraction pipeline and model comparison",
        author="Giorgi Pataridze",
        task_type="Testing a solution (comparative evaluation)",
        goal_intro=(
            "Determine whether a locally hosted language model can extract "
            "member-company names from heterogeneous German innovation-network "
            "websites without website-specific code, and identify which model "
            "and prompting strategy performs best."),
        goal_bullets=[
            ("Relevance:", "member lists are a signal of innovation activity "
             "for the company database, but the 73 collected sites have no "
             "common structure, so per-site scrapers would not scale."),
            ("Local models:", "processing happens on our own hardware, so no "
             "company data leaves the machine and there are no per-page API "
             "costs."),
        ],
        intended=[
            "Build a four-stage pipeline: fetch and cache the page, strip HTML "
            "to plain text while preserving outbound links, send the text to a "
            "local model via Ollama, and score the result. Name filtering is "
            "deliberately excluded: per the meeting of 2026-07-28 it belongs at "
            "database-insert time, not during extraction.",
            "Compare three models (llama3.1:8b, qwen2.5-coder:7b, gemma4:12b) "
            "against three prompting strategies (zero-shot, few-shot schema, "
            "generic multi-stage) and two JSON modes, on ten websites, repeated "
            "three times: 540 runs.",
            "Score against a manually annotated ground truth so that accuracy, "
            "not merely output volume, can be measured.",
        ],
        problem=[
            "Target state: every configuration measured on identical input, "
            "with precision, recall and F1 per configuration.",
            "Actual state encountered: Ollama silently truncates input beyond "
            "its default 4,096-token context and raises no error. One page in "
            "the corpus cleans to 53,304 tokens, so most of it would have been "
            "discarded invisibly and the entire comparison would have measured "
            "a truncation defect rather than model capability.",
            "Second issue: the models occupy 4.7 GB, 4.9 GB and 7.6 GB and "
            "cannot remain resident together in 16 GB of RAM. Alternating them "
            "between runs would have measured disk reload time instead of "
            "inference.",
        ],
        emerging=[
            "num_ctx is set explicitly to 8,192 and pages exceeding it are "
            "split into ~6,000-token chunks on line boundaries, with results "
            "merged and deduplicated, chunking rather than truncation, so no "
            "member is lost silently.",
            "The benchmark loop iterates model-outermost, so each model is "
            "loaded once and stays resident for its entire half of the run.",
            "Fetching was separated from extraction and pages cached to disk, "
            "so every configuration reads byte-identical input and network "
            "latency never enters the measurement.",
        ],
        metrics=[
            "Precision, recall and F1 per configuration, scored against 761 "
            "hand-annotated company names across ten pages.",
            "Result: llama3.1:8b with few-shot schema prompting achieved "
            "F1 = 0.957 (precision 0.971, recall 0.945) at 56 s per page. "
            "Few-shot beat zero-shot for both models.",
            "Generic multi-stage prompting was the worst configuration: recall "
            "fell from 0.945 to 0.619 while precision rose only from 0.971 to "
            "0.985, at eleven times the runtime. Its validation step discards "
            "correct entries.",
            "Accuracy is scored on raw model output, before the Neovation name "
            "filter, so the model is not penalised for the filter's "
            "deliberate exclusions.",
        ],
        test_process=[
            "Deterministic decoding (temperature 0, fixed seed) with three "
            "repetitions per configuration; repetitions therefore measure "
            "latency variance, not output variance.",
            "Reproduce with: benchmark.py --stage a, then evaluate.py. Raw "
            "per-run data in results/benchmark_results.csv (360 rows).",
        ],
    )

    # ---- Task 2: pagination ---------------------------------------------
    section(
        doc,
        date="31.07.2026 - 01.08.2026",
        wp="1. Unternehmensdatenbank",
        title="Task 2, Detecting and recovering truncated member lists",
        author="Giorgi Pataridze",
        task_type="Addressing a risk (silent data loss)",
        goal_intro=(
            "Ensure that the extraction captures a complete member list rather "
            "than the first page of one."),
        goal_bullets=[
            ("Risk:", "a paginated directory returns HTTP 200 with plausible "
             "content, so partial extraction is indistinguishable from "
             "complete extraction. Every downstream figure would be understated "
             "with no indication that anything was missing."),
        ],
        intended=[
            "Fetch each member-list URL once and treat the response as the "
            "complete list.",
        ],
        problem=[
            "Target state: the full membership of each association.",
            "Actual state: BDEW's snapshot contained 43 companies, all "
            "beginning with the letter A, the directory is indexed A-Z across "
            "26 separate pages holding roughly 1,600 members. Medical Valley "
            "served 20 of about 280, across 14 JavaScript-driven pages with no "
            "URL variant. 24 of 53 usable pages showed pagination markers.",
            "The defect was found by eye during manual annotation, not by any "
            "automated check.",
        ],
        emerging=[
            "Two mechanisms were implemented separately because they require "
            "different handling: URL-based pagination (?letter=A-Z, ?page=N, "
            "record ranges such as 0-50 / 51-100) is followed with plain HTTP "
            "requests; JavaScript pagination is driven by a headless browser "
            "that scrolls, clicks 'load more', and walks numbered page links.",
            "An initial keyword-based detector was replaced after it proved "
            "wrong in both directions, it scored BDEW at zero because that "
            "site paginates with ordinary URL links rather than JavaScript, "
            "and raised a false alarm on SPECTARIS from CMS boilerplate. The "
            "replacement measures alphabet coverage of member initials, which "
            "separates the cases without any network access.",
        ],
        metrics=[
            "Content recovered per site, measured in words of cleaned text: "
            "BDEW 281 → 13,255 (47×); Medical Valley 714 → 10,894 (15×); "
            "bwcon 279 → 1,789 across 107 pagination pages; German Accelerator "
            "997 → 2,917.",
            "Headless rendering returned less content than the plain fetch on "
            "7 of 19 pages, most likely consent walls reacting to headless "
            "Chrome. A guard keeps whichever document is larger, so no content "
            "was lost.",
        ],
        test_process=[
            "check_completeness.py prints alphabet coverage per page; a "
            "complete directory spans most initials, a truncated one clusters "
            "on a single letter.",
            "Reproduce with: paginate.py --detect, browser_fetcher.py --compare <id>.",
        ],
    )

    # ---- Task 3: URL acquisition ----------------------------------------
    h(doc, "Task 3, Acquiring company websites", size=13)
    meta(doc, "Date", "06.08.2026 - 11.08.2026")
    meta(doc, "Work Package", "1. Unternehmensdatenbank")
    meta(doc, "Author", "Giorgi Pataridze")
    meta(doc, "Type", "Delivering a new feature")

    h(doc, "Goal", size=11, space_before=10)
    para(doc, "Deliver, for every extracted member, the company's own website "
              "alongside its name, so that a later scraper can visit each "
              "company site and extract innovation indicators.")
    bullets(doc, [
        ("Requirement:", "specified by Prof. Hendro Wicaksono on 06.08.2026 "
         "(output as Excel with company name, company website, network name, "
         "network URL) and restated by Marco Sparovek on 07.08.2026."),
        ("Constraint:", "Hendro requires names and links in a single extraction "
         "pass where possible, to avoid doubling token cost and creating a "
         "name-to-URL matching problem afterwards."),
    ])

    h(doc, "Method", size=11, space_before=10)
    para(doc, "Intended strategy", italic=True, color=MUTED)
    para(doc, "Extend the extraction schema from {name} to {name, url} and "
              "obtain both in one pass over the directory page.")

    para(doc, "Problem: actual state vs target state", italic=True, color=MUTED)
    para(doc, "Target state: a website for each of the 543 annotated companies.")
    para(doc, "Two obstacles were found, the first fatal to any prompt-level fix:")
    bullets(doc, [
        "The HTML cleaner discarded every href attribute, so the text given to "
        "the model contained zero URLs. No prompt could have returned a "
        "website; the information never reached the model.",
        "Even after link preservation, only 3 of 10 pages print company "
        "websites in their visible text. 459 of 543 companies sit on pages "
        "that show no URL.",
    ])

    para(doc, "Emerging strategy", italic=True, color=MUTED)
    para(doc, "Link targets are now written into the cleaned text beside their "
              "anchor text, so the model can read them. Beyond that, a "
              "five-stage cascade was designed, ordered cheapest and most "
              "reliable first, with each stage handling only what the previous "
              "one could not resolve:")
    table(doc,
          ["Stage", "Method", "Cost", "Coverage / result"],
          [
              ["1", "LLM reads the directory page", "included in extraction",
               "3 of 10 pages; 95-98% within those"],
              ["2", "Follow per-member profile pages", "1 request + small model call",
               "~204 of 218 remaining companies"],
              ["3", "Construct domain from name, verify", "free",
               "~72% resolve, ~60% correct"],
              ["4", "ddgs meta-search, LLM ranks results", "free",
               "4 of 5 on top result alone"],
              ["5", "Lookup in Neovation company database", "free (needs access)",
               "unknown; OpenCorporates holds no domains"],
          ])
    para(doc, "The decisive finding was stage 2. Directories that appear to "
              "contain no links mostly do: the link sits on the member's logo "
              "or on an adjacent 'Mehr lesen' element rather than on the "
              "company name, and it leads to a profile page on the "
              "association's own site carrying the company's website, street, "
              "postcode, city and contact email.")

    para(doc, "Approaches considered and rejected", italic=True, color=MUTED)
    bullets(doc, [
        ("Address first, then search on name + address, ", "proposed because a "
         "German company name is unique only within a city, which is correct. "
         "Rejected on measurement: postal addresses appear only on the pages "
         "that already carry company links. Of the seven link-free pages none "
         "has a postcode or street, so the chain cannot start where it is needed."),
        ("Feed raw HTML to the model, ", "would expose href attributes "
         "directly, but raw pages here reach 800 KB against 1,500-13,000 tokens "
         "of cleaned text, a 10-40× increase no context window absorbs. It also "
         "would not help: the href on a member entry is usually the profile "
         "URL, not the company website."),
        ("One single stage covering directory and all profiles together, ",
         "roughly 204 profiles at ~600 tokens each is ~122,000 tokens for one "
         "association, requiring about 20 chunks with no accuracy gain over "
         "handling profiles individually."),
        ("Hand-written parsers per association, ", "exact, but 300 networks "
         "would need 300 parsers, each breaking on redesign. This is the "
         "per-site cost the project set out to remove. Generic format-based "
         "extraction (postcode shape, outbound non-social link, email pattern) "
         "achieves the same result without site-specific code."),
        ("Paid search APIs as the primary route, ", "superseded by ddgs, which "
         "is free. Retained only as a last resort."),
    ])

    h(doc, "Metrics", size=11, space_before=10)
    bullets(doc, [
        "Link preservation verified: llama3.1:8b returned 42 companies from "
        "BDEW with 40 correct websites, at +26-48% input tokens and 92 s "
        "against 25 s for names alone.",
        "Profile-page route verified: llama3.1:8b returned all six fields "
        "(name, website, street, postcode, city, email) correctly from an "
        "Automotive Nordwest profile page in 13.5 s on a laptop.",
        "Profile-link coverage measured against ground truth: 100% of Life "
        "Science Nord's 52 members, 97% of Automotive Nordwest's 33, 92% of "
        "NMWP's 49, 86% of German Water Partnership's 14.",
        "Success criterion: a website is accepted only if fetching it confirms "
        "the company name appears on the page. Two further free checks are "
        "available, whether the site references the network (suggested by "
        "Marco Sparovek), and whether it agrees with the email domain from the "
        "profile page.",
    ])
    para(doc, "Test process", italic=True, color=MUTED)
    bullets(doc, [
        "Every candidate URL is verified against the cached page, so URL "
        "accuracy needs no manual annotation: a returned URL either appears in "
        "the source page or the model invented it.",
        "The proportion resolved at each cascade stage is recorded, which is "
        "the honest basis for deciding whether a paid route is needed rather "
        "than estimating coverage in advance.",
    ])
    doc.add_paragraph("_" * 78)

    # ---- Open items ------------------------------------------------------
    h(doc, "Open items", size=13)
    bullets(doc, [
        ("Hardware, ", "Constructor Knowledge Labs has confirmed access to an "
         "A100 80 GB node. The full three-model grid is estimated at 3-5 hours "
         "there against 60-100 hours on the laptop, and gemma4:12b becomes "
         "usable: on 16 GB it runs 11.6× slower than a 7B model purely through "
         "memory swapping."),
        ("Database access, ", "Neovation offered on 11.08.2026 to link "
         "extracted names against their records. This needs an export or query "
         "endpoint, and would also measure how many names are ambiguous, the "
         "figure that decides whether per-company address extraction is "
         "required at all."),
        ("Outlier, ", "Medical Valley EMN is the one directory with neither "
         "company links nor per-member profile pages: 20 companies reachable "
         "only through stages 3-5."),
    ])

    doc.save(OUT)
    print(f"wrote {OUT}")
    print(f"  {len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables")


if __name__ == "__main__":
    build()
