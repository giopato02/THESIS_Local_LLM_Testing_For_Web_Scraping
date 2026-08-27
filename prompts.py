"""
Phase 2 -- the prompt techniques under comparison.

Each strategy is a named function returning (system, user). The name is what
lands in the Prompt_Technique_Name column, so the CSV is self-documenting.

Three techniques, chosen so the ablation isolates one variable at a time:

These are P1-P3 from Hendro's thesis guideline, section 3.7:

  zero_shot            P1 -- instruction only, the baseline
  few_shot_schema      P2 -- instruction + explicit schema + 2 worked examples
  generic_multi_stage  P3 -- locate the list, extract it, then validate the
                             result, as three separate model calls

Comparing zero_shot against few_shot_schema measures what the examples buy.
Comparing both against generic_multi_stage measures whether decomposing the
task into locate/extract/validate is worth roughly 3x the runtime -- which is
exactly what RQ2 in the guideline asks.

Design notes that apply to all three:
  * Instructions are in English, content is in German. Both models handle this
    cross-lingual setup well and it keeps the prompt short.
  * We ask for the name EXACTLY as printed. Any normalisation is the filter's
    job (Phase 3), not the model's -- if the model "helpfully" expands or
    translates a name, we can no longer verify it against the source page.
  * Every strategy forbids inventing entries. Hallucinated members are the
    dominant failure mode when a page contains no list at all.
"""

from __future__ import annotations

from typing import Callable

# --------------------------------------------------------------------------
# Shared fragments
# --------------------------------------------------------------------------

_ROLE = (
    "You extract member-company names from German industry-association and "
    "innovation-network websites."
)

_RULES = """Rules:
- Extract ONLY organisations listed as members, participants, or partners.
- Copy each name EXACTLY as it appears. Do not translate, expand, abbreviate,
  or correct spelling. Keep German characters (ä, ö, ü, ß) intact.
- Ignore website navigation, headings, contact details, page titles, cookie
  notices, and the name of the association hosting the page.
- If the text contains no member list, return an empty array. Never invent
  names to fill the list."""


# --------------------------------------------------------------------------
# Strategy 1 -- zero-shot baseline
# --------------------------------------------------------------------------

def zero_shot(page_text: str) -> tuple[str, str]:
    system = f"{_ROLE}\n\n{_RULES}"
    user = (
        "Extract every member company from the page text below.\n"
        'Respond with JSON only, in the form {"companies": ["Name 1", "Name 2"]}.\n\n'
        "--- PAGE TEXT ---\n"
        f"{page_text}"
    )
    return system, user


# --------------------------------------------------------------------------
# Strategy 2 -- schema-driven few-shot
# --------------------------------------------------------------------------

# Both examples are modelled on real pages in this corpus. The second is
# deliberately a near-miss: a page whose only "list" is navigation chrome,
# teaching the model that an empty answer is a valid and expected outcome.
_EXAMPLE_1_IN = """Unsere Mitglieder
Robert Bosch GmbH
Siemens AG
IFM electronic gmbh
Kontakt | Impressum | Datenschutz"""

_EXAMPLE_1_OUT = (
    '{"companies": ["Robert Bosch GmbH", "Siemens AG", "IFM electronic gmbh"]}'
)

_EXAMPLE_2_IN = """Startseite
Über uns
Der Verband vertritt die Interessen der Branche seit 1952.
Mitglied werden
Newsletter abonnieren"""

_EXAMPLE_2_OUT = '{"companies": []}'


# --------------------------------------------------------------------------
# Strategy 2b -- few-shot, extracting name AND website in one pass
# --------------------------------------------------------------------------
#
# Requested by Hendro (meeting 2026-08-06): the deliverable needs each member's
# own website alongside its name, and in a SINGLE pass -- extracting names and
# links separately would cost twice the tokens and create a name-matching
# problem afterwards.
#
# This is only possible where the directory actually links to member websites.
# Measured coverage on the ten annotated pages: 95-98% on three of them
# (BDEW, automotive thueringen, SPECTARIS) and 0% on the other seven, whose
# entries either carry no link at all or link to a profile page on the
# association's own site. The prompt therefore treats the URL as optional and
# forbids guessing -- an invented company domain is worse than a blank field,
# because it looks correct.

_URL_RULES = """URL rules:
- Use the URL shown in angle brackets <...> beside a company, and only that.
- If a company has no URL beside it, return an empty string. Never guess a
  website from the company's name, and never reuse another company's URL.
- Ignore URLs for social media, the association itself, and page navigation."""


def few_shot_with_url(page_text: str) -> tuple[str, str]:
    system = (
        f"{_ROLE}\n\n"
        "Output schema (respond with this JSON object and nothing else):\n"
        '{"companies": [{"name": "<company name as printed>", '
        '"url": "<company website, or empty string>"}]}\n\n'
        f"{_RULES}\n\n{_URL_RULES}"
    )
    user = (
        "### Example\n"
        "PAGE TEXT:\n"
        "Unsere Mitglieder\n"
        "Robert Bosch GmbH\n"
        "Web <https://www.bosch.de>\n"
        "Siemens AG\n"
        "Web <https://www.siemens.com>\n"
        "IFM electronic gmbh\n"
        "Kontakt | Impressum\n"
        "JSON:\n"
        '{"companies": [{"name": "Robert Bosch GmbH", "url": "https://www.bosch.de"}, '
        '{"name": "Siemens AG", "url": "https://www.siemens.com"}, '
        '{"name": "IFM electronic gmbh", "url": ""}]}\n\n'
        "### Now your turn\n"
        "PAGE TEXT:\n"
        f"{page_text}\n"
        "JSON:"
    )
    return system, user


# --------------------------------------------------------------------------
# Strategy 2c -- full company record in one pass
# --------------------------------------------------------------------------
#
# Agreed in the meetings of 2026-08-12 and 2026-08-13. Two requirements
# converge on the same schema:
#
#   * Hendro (06.08): the deliverable needs the company's website beside its
#     name, obtained in a single pass.
#   * Marco (07.08) and Yusif (12.08): a German company name is unique only
#     within a city, so Neovation's record matching needs a disambiguating
#     attribute. Yusif: "in case you are able to get any extra information
#     apart from the name -- address, city, country" the second stage can
#     resolve the URL from name plus that extra data.
#
# Every field is optional and the model is told to leave it empty rather than
# infer it. A fabricated address is worse than a blank one: it looks correct,
# it will not be caught by eye, and it would corrupt exactly the field the
# matching depends on.
#
# Applicable to both page types:
#   * directory listings that print contact details beside each member
#   * association profile pages, one company per page, which carry the full
#     record (verified: all six fields extracted correctly from an Automotive
#     Nordwest profile in a single call)

_RECORD_SCHEMA = (
    '{"companies": [{"name": "", "url": "", "street": "", "postcode": "", '
    '"city": "", "phone": "", "email": ""}]}'
)

_RECORD_RULES = """Field rules:
- name is the only required field. Every other field is "" when the page does
  not state it.
- NEVER infer, guess or complete a field. Do not derive a website from the
  company name, do not supply a postcode for a city you recognise, and do not
  reuse another company's details. An empty string is always correct when the
  information is absent.
- url is the company's OWN website. Never the association's, never social
  media, never a page on the site currently being read.
- street is the street and house number only; postcode and city go in their
  own fields. German postcodes are five digits.
- phone and email must belong to the company, not to the association's office."""


def few_shot_full_record(page_text: str) -> tuple[str, str]:
    system = (
        f"{_ROLE}\n\n"
        "Output schema (respond with this JSON object and nothing else):\n"
        f"{_RECORD_SCHEMA}\n\n"
        f"{_RULES}\n\n{_RECORD_RULES}"
    )
    user = (
        "### Example 1: a listing with contact details\n"
        "PAGE TEXT:\n"
        "Unsere Mitglieder\n"
        "Robert Bosch GmbH\n"
        "Robert-Bosch-Platz 1\n"
        "70839 Gerlingen\n"
        "Web <https://www.bosch.de>\n"
        "Siemens AG\n"
        "Kontakt | Impressum\n"
        "JSON:\n"
        '{"companies": ['
        '{"name": "Robert Bosch GmbH", "url": "https://www.bosch.de", '
        '"street": "Robert-Bosch-Platz 1", "postcode": "70839", '
        '"city": "Gerlingen", "phone": "", "email": ""}, '
        '{"name": "Siemens AG", "url": "", "street": "", "postcode": "", '
        '"city": "", "phone": "", "email": ""}]}\n\n'
        "### Example 2: a single company profile page\n"
        "PAGE TEXT:\n"
        "ACME Sensortechnik GmbH\n"
        "Intzestr. 5\n"
        "52072 Aachen\n"
        "Tel. +49 241 123456\n"
        "info@acme-sensor.de\n"
        "Zur Website <https://www.acme-sensor.de>\n"
        "JSON:\n"
        '{"companies": [{"name": "ACME Sensortechnik GmbH", '
        '"url": "https://www.acme-sensor.de", "street": "Intzestr. 5", '
        '"postcode": "52072", "city": "Aachen", '
        '"phone": "+49 241 123456", "email": "info@acme-sensor.de"}]}\n\n'
        "### Now your turn\n"
        "PAGE TEXT:\n"
        f"{page_text}\n"
        "JSON:"
    )
    return system, user


def zero_shot_full_record(page_text: str) -> tuple[str, str]:
    """
    P1 with the full record schema.

    The zero-shot counterpart of few_shot_full_record, so the URL arm tests
    the same three approaches as the names arm. Without it the URL arm is
    entirely few-shot and cannot answer whether the names-arm ranking (where
    zero-shot won) still holds once a second field is requested.

    No worked example, matching zero_shot: the schema and the rules carry the
    whole specification.
    """
    system = (
        f"{_ROLE}\n\n"
        "Output schema (respond with this JSON object and nothing else):\n"
        f"{_RECORD_SCHEMA}\n\n"
        f"{_RULES}\n\n{_RECORD_RULES}"
    )
    user = (
        "Extract every member company from the page text below, with its "
        "website and contact details where the page shows them.\n"
        "Leave a field as an empty string when the page does not show it.\n\n"
        "--- PAGE TEXT ---\n"
        f"{page_text}"
    )
    return system, user


def few_shot_schema(page_text: str) -> tuple[str, str]:
    system = (
        f"{_ROLE}\n\n"
        "Output schema (respond with this JSON object and nothing else):\n"
        '{"companies": ["<company name as printed>", ...]}\n\n'
        f"{_RULES}"
    )
    user = (
        "### Example 1\n"
        f"PAGE TEXT:\n{_EXAMPLE_1_IN}\n"
        f"JSON:\n{_EXAMPLE_1_OUT}\n\n"
        "### Example 2\n"
        f"PAGE TEXT:\n{_EXAMPLE_2_IN}\n"
        f"JSON:\n{_EXAMPLE_2_OUT}\n\n"
        "### Now your turn\n"
        "PAGE TEXT:\n"
        f"{page_text}\n"
        "JSON:"
    )
    return system, user


# --------------------------------------------------------------------------
# Strategy 3 -- generic multi-stage extraction with a validation step
# --------------------------------------------------------------------------
#
# This is P3 in Hendro's thesis guideline (section 3.7), and it replaces the
# chain-of-thought strategy an earlier draft used. His definition, from the
# meeting of 2026-07-31: "you are doing like two stage kind of information
# retrieval -- first is to get the base of the network information, then get
# the company list, and then extract the information about the company."
#
# Implemented as three separate model calls per page:
#
#   1 LOCATE    Where in this text does the member list start and end, and
#               what layout is it in? Cheap, and it stops the model treating
#               navigation as data.
#   2 EXTRACT   Pull the names, told where to look.
#   3 VALIDATE  Re-read the extracted names and drop anything that is page
#               furniture rather than a member company.
#
# The cost is roughly 3x the latency of a single-call strategy. Whether that
# buys enough accuracy to be worth it is exactly what RQ2 asks.

def multi_stage_locate(page_text: str) -> tuple[str, str]:
    """Stage 1 -- find the member list before trying to read it."""
    system = (
        f"{_ROLE}\n\n"
        "You are performing the FIRST stage of a multi-stage extraction: "
        "locating the member list. Do not extract the members yet.\n\n"
        "Respond with JSON only:\n"
        '{"has_member_list": true|false, '
        '"section_heading": "<the heading above the list, or empty>", '
        '"first_entry": "<the first member name you can see, or empty>", '
        '"layout": "table|list|cards|alphabetical_index|prose|none"}'
    )
    user = (
        "Determine whether the page text below contains a list of member "
        "organisations, and if so where it begins.\n\n"
        "--- PAGE TEXT ---\n"
        f"{page_text}"
    )
    return system, user


def multi_stage_extract(page_text: str, hint: str = "") -> tuple[str, str]:
    """Stage 2 -- extract, guided by what stage 1 found."""
    system = (
        f"{_ROLE}\n\n"
        "You are performing the SECOND stage of a multi-stage extraction. A "
        "previous stage located the member list; use that to focus your "
        "reading.\n\n"
        "Output schema (respond with this JSON object and nothing else):\n"
        '{"companies": ["<company name as printed>", ...]}\n\n'
        f"{_RULES}"
    )
    guidance = f"\nWhat the locating stage found:\n{hint}\n" if hint else ""
    user = (
        f"Extract every member company from the page text below.{guidance}\n"
        "--- PAGE TEXT ---\n"
        f"{page_text}"
    )
    return system, user


def multi_stage_extract_record(page_text: str, hint: str = "") -> tuple[str, str]:
    """Stage 2 for the record-returning multi-stage variant."""
    system = (
        f"{_ROLE}\n\n"
        "You are performing the SECOND stage of a multi-stage extraction. A "
        "previous stage located the member list; use that to focus your "
        "reading.\n\n"
        "Output schema (respond with this JSON object and nothing else):\n"
        f"{_RECORD_SCHEMA}\n\n"
        f"{_RULES}\n\n{_RECORD_RULES}"
    )
    guidance = f"\nWhat the locating stage found:\n{hint}\n" if hint else ""
    user = (
        "Extract every member company from the page text below, with its "
        f"website and contact details where the page shows them.{guidance}\n"
        "--- PAGE TEXT ---\n"
        f"{page_text}"
    )
    return system, user


def multi_stage_full_record(page_text: str) -> tuple[str, str]:
    """
    Registry entry point for P3 with the full record schema.

    Driven by extractor.py in the same locate -> extract -> validate shape as
    generic_multi_stage; only the extraction stage differs. Validation still
    operates on names, since removing a wrongly-extracted company should not
    depend on whether its address was found.
    """
    return multi_stage_extract_record(page_text)


def multi_stage_validate(names: list[str]) -> tuple[str, str]:
    """Stage 3 -- the validation step the guideline explicitly asks for."""
    system = (
        f"{_ROLE}\n\n"
        "You are performing the THIRD stage of a multi-stage extraction: "
        "validation. You are given names a previous stage extracted. Remove "
        "any entry that is NOT a member organisation -- menu labels, section "
        "headings, category names, page numbers, dates, people's names, "
        "contact details, or the hosting association itself.\n\n"
        "Keep every genuine organisation exactly as written. Do not add, "
        "translate, or correct anything.\n\n"
        "Respond with JSON only:\n"
        '{"companies": ["<validated name>", ...]}'
    )
    # Stage 2 hands back records, not strings. Interpolating those directly
    # showed the model "- {'name': 'Robert Bosch GmbH'}" instead of the name,
    # so the validator was judging Python syntax rather than company names.
    items = [n.get("name", "") if isinstance(n, dict) else str(n) for n in names]
    user = (
        "Validate this extracted list and return only the genuine member "
        "organisations:\n\n"
        + "\n".join(f"- {n}" for n in items if n)
    )
    return system, user


def generic_multi_stage(page_text: str) -> tuple[str, str]:
    """
    Registry entry point.

    Multi-stage needs several model calls, which the single-call signature
    cannot express, so extractor.py detects this strategy by name and drives
    the three stages above directly. This function returns stage 2 without a
    hint so the strategy still degrades gracefully if called generically.
    """
    return multi_stage_extract(page_text)


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

# The three strategies named in Hendro's guideline section 3.7:
#   P1 zero-shot structured extraction
#   P2 few-shot structured extraction
#   P3 generic multi-stage extraction with a validation step
STRATEGIES: dict[str, Callable[[str], tuple[str, str]]] = {
    "zero_shot": zero_shot,
    "few_shot_schema": few_shot_schema,
    "generic_multi_stage": generic_multi_stage,
    # Winning strategy extended with the website field (Hendro, 2026-08-06).
    "few_shot_with_url": few_shot_with_url,
    # Full record: name + website + address + phone + email (2026-08-13).
    "few_shot_full_record": few_shot_full_record,
    # Zero-shot and multi-stage counterparts, so the URL arm mirrors the
    # names arm approach for approach (2026-08-28).
    "zero_shot_full_record": zero_shot_full_record,
    "multi_stage_full_record": multi_stage_full_record,
}

# The three guideline strategies (P1/P2/P3) that answer RQ1-RQ3. They request
# a flat list of names, so they are scored against the hand-labelled ground
# truth and nothing else. Kept as an explicit tuple because iterating
# STRATEGIES would silently pull the record arms into the grid and turn a
# 540-run experiment into a 900-run one.
BENCHMARKED = ("zero_shot", "few_shot_schema", "generic_multi_stage")

# The URL arm: the same three approaches as BENCHMARKED, each returning the
# full record (name + website + address + phone + email) instead of a bare
# name. Deliberately one-to-one with the names arm, so the two are directly
# comparable and the question "does the ranking survive asking for a URL?"
# can be answered per approach rather than only in aggregate.
URL_ARM = ("zero_shot_full_record", "few_shot_full_record",
           "multi_stage_full_record")

# few_shot_with_url returns name + website only, without the address fields.
# Kept for the ablation "does asking for five extra fields cost accuracy?",
# which is a different question from "does asking for a URL cost accuracy?".
URL_ABLATION = ("few_shot_with_url",)

ARMS = {
    "guideline": BENCHMARKED,
    "url": URL_ARM,
    "url_ablation": URL_ABLATION,
    "all": BENCHMARKED + URL_ARM + URL_ABLATION,
}

# Strategies that need more than one model call, driven by extractor.py.
MULTI_STAGE = {"generic_multi_stage", "multi_stage_full_record"}

# Strategies whose output is an object per company rather than a bare
# string; constrained decoding must be given the matching JSON schema.
RECORD_STRATEGIES = {"few_shot_with_url", "few_shot_full_record",
                     "zero_shot_full_record", "multi_stage_full_record"}

# Every strategy now emits pure JSON, so constrained decoding is compatible
# with all of them. Kept as an explicit (empty) set so the benchmark's grid
# logic stays unchanged if a prose-emitting strategy is added later.
INCOMPATIBLE_WITH_CONSTRAINED: set[str] = set()


def build(strategy: str, page_text: str) -> tuple[str, str]:
    if strategy not in STRATEGIES:
        raise KeyError(f"unknown strategy {strategy!r}; have {list(STRATEGIES)}")
    return STRATEGIES[strategy](page_text)
