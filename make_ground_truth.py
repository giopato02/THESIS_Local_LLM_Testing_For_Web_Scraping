"""
Build hand-labelling worksheets for the ground-truth sample.

Hand-labelling from a blank page would take a full day. Instead we pre-fill:
this script pulls every plausible company name out of the cached HTML using
structural heuristics (links, list items, table cells, card headings), then
writes a plain-text worksheet with one candidate per line.

The human job is then subtractive and fast:
    delete the lines that are not member companies, add anything missed, save.

Deliberately heuristic, never model-based -- ground truth produced by an LLM
would not be independent of the systems we are grading.

Run:  .venv/bin/python make_ground_truth.py
      .venv/bin/python make_ground_truth.py --check     # validate + summarise
"""

from __future__ import annotations

import argparse
import csv
import json
import re

from bs4 import BeautifulSoup

import config
import fetcher

# Stratified sample across page size. Every entry was VERIFIED by eye to be a
# real member directory -- an earlier draft picked pages that merely fetched
# "ok" and turned out to be cookie banners (010), news feeds (035, 047, 049)
# and a product-category taxonomy (002). Fetching 200 is not the same as
# containing a member list, which is itself a finding worth reporting.
#
# id     tokens  candidates  why it is in the sample
# Every entry is confirmed to be a real member directory by the entries-vs-bios
# test: a directory has many short lines carrying a legal form and few job
# titles. Pages that merely LOOK dense were rejected -- 014 (Cluster
# Mechatronik) had 7 entries against 26 staff bios, and 028 (Hanse-Aerospace)
# pointed at an "ueber-uns" page. Both were dropped after inspection.
#
# id     tokens  entries  why it is in the sample
SAMPLE_IDS = [
    "039",  #    469    42   tiny
    "043",  #    722    34   tiny
    "009",  #    827    36   small
    "012",  #    912    48   small
    "004",  #   1014    36   small
    "032",  #   1149    47   medium
    "040",  #   1943    20   medium, sparse markup
    "025",  #   2872    15   medium
    "005",  #   4873   112   large, still fits one chunk
    "050",  #   9383   268   CHUNKED - exercises the chunk/merge path
]

# Text that appears in navigation and cookie banners on nearly every German
# association site. Dropped from the candidate list to reduce manual work.
NAV_NOISE = {
    "startseite", "home", "kontakt", "impressum", "datenschutz", "suche",
    "anmelden", "login", "newsletter", "mitglied werden", "über uns",
    "aktuelles", "news", "veranstaltungen", "termine", "presse", "karriere",
    "jobs", "downloads", "sitemap", "cookie", "cookies", "akzeptieren",
    "alle akzeptieren", "einstellungen", "mehr", "mehr erfahren", "weiterlesen",
    "zurück", "weiter", "menü", "navigation", "english", "deutsch", "de", "en",
    "facebook", "linkedin", "twitter", "xing", "instagram", "youtube",
    "agb", "haftungsausschluss", "barrierefreiheit", "mitglieder",
    "unsere mitglieder", "mitgliederliste", "partner", "sponsoren",
}

CANDIDATE_TAGS = ["a", "li", "td", "th", "h2", "h3", "h4", "h5",
                  "dt", "dd", "figcaption", "strong", "b",
                  # SPECTARIS renders every member name in a bare <span> inside
                  # nested divs. Omitting these tags cost 146 of 287 names on
                  # that page -- half the directory -- and the gap only showed
                  # up because a human noticed names missing every other line.
                  # They are noisy on other sites, so leaf-only filtering below
                  # keeps the extra volume manageable.
                  "span", "div"]

# <span> and <div> nest, so a parent repeats all its children's text. Only
# elements with no element children of their own are considered, which yields
# the innermost text node rather than a wrapper containing the whole list.
LEAF_ONLY_TAGS = {"span", "div"}

_MONTHS = ("Januar|Februar|März|April|Mai|Juni|Juli|August|September|"
           "Oktober|November|Dezember")
# Several directories print a "member since" date beside each company, and a
# few list event dates. Both arrive as their own candidate lines.
DATE_RE = re.compile(
    rf"\b\d{{1,2}}\.?\s*(?:{_MONTHS})\s*\d{{4}}\b|\b\d{{1,2}}\.\d{{1,2}}\.\d{{2,4}}\b",
    re.IGNORECASE)


# Directory pages wrap their member list in filter widgets, category legends
# and pagination. These are the recurring German labels for that furniture.
UI_VOCAB = {
    "filtern nach", "filter", "filtern", "sortieren", "sortierung",
    "zurücksetzen", "auswahl", "auswählen", "alle zeigen", "alle anzeigen",
    "alle", "kategorie", "kategorien", "branche", "branchen", "region",
    "regionen", "bundesland", "plz", "ort", "land", "typ", "art", "status",
    "seite", "nächste", "vorherige", "ergebnisse", "treffer", "anzeigen",
    "ausblenden", "details", "profil", "mehr infos", "website", "webseite",
    "e-mail", "email", "telefon", "adresse", "ansprechpartner",
    "kontaktperson", "zum profil", "mehr lesen", "alle mitglieder",
    "ordentliche mitglieder", "fördermitglieder", "assoziierte mitglieder",
    "mitgliedsunternehmen", "unsere partner", "suchbegriff", "suche",
    "zulieferer", "sonstige", "übersicht", "liste", "karte", "raster",
    "a-z", "0-9", "nach oben", "schließen", "öffnen", "drucken", "teilen",
}

# Anything containing one of these is almost certainly a real organisation.
LEGAL_HINT = re.compile(
    r"\b(GmbH|mbH|AG|KG|KGaA|SE|OHG|GbR|eG|e\.\s?V|gGmbH|UG|Ltd|LLC|Inc|"
    r"B\.?V|N\.?V|S\.?A|GmbH\s*&\s*Co)\b", re.IGNORECASE)

# Research institutes are members on many of these pages, so treat them as
# organisations here. Whether the FILTER later drops them is a separate
# question -- ground truth records what the page says.
ORG_HINT = re.compile(
    r"\b(Fraunhofer|Leibniz|Max[- ]Planck|Helmholtz|Institut|Universität|"
    r"Hochschule|Technologie|Systems?|Technik|Engineering|Solutions?|"
    r"Group|Werke?|Labor|Consulting|Automation|Elektronik|Maschinenbau)\b",
    re.IGNORECASE)


def looks_like_company(text: str) -> bool:
    """
    Split candidates into 'probably a company' and 'probably page furniture'.

    Deliberately permissive: nothing is discarded, only sorted into two
    sections of the worksheet. Real directories list bare brand names like
    "3Dator" or "accompio" that no rule reliably recognises, so an aggressive
    filter would quietly delete true members and corrupt the answer key.
    """
    low = text.casefold().strip()

    if low in UI_VOCAB:
        return False
    # "Alle Kategorien", "Seite 2", "Filter zurücksetzen" ...
    if any(low.startswith(v + " ") or low.endswith(" " + v) for v in UI_VOCAB):
        return False

    if LEGAL_HINT.search(text) or ORG_HINT.search(text):
        return True

    # A lone lowercase German word is a label, not a company name.
    if " " not in text and text.islower():
        return False
    # Generic single Title-Case words ("Software", "Beratung") are category
    # legends; real single-word brands almost always carry odd casing or
    # digits ("3Dator", "accompio", "embeteco", "IMTEK").
    if " " not in text and text.istitle() and len(text) < 14:
        return False

    return True


def partition(candidates: list[str]) -> tuple[list[str], list[str]]:
    """
    Split candidates into (likely members, probable page furniture).

    Beyond the per-line test, this exploits a layout regularity: filter
    widgets and category legends sit ABOVE the member list, so everything
    before the first entry carrying a legal form is furniture unless it
    looks like a company in its own right. That single rule catches the
    long German compound category names ("Logistikdienstleister",
    "Qualitätsmanagement") that no keyword list would ever cover.

    Nothing is discarded -- the bin is written to the worksheet so any
    mistake here is visible and reversible by hand.
    """
    first_member = next(
        (i for i, c in enumerate(candidates) if LEGAL_HINT.search(c)), 0)

    likely, unlikely = [], []
    for i, cand in enumerate(candidates):
        if i < first_member and not LEGAL_HINT.search(cand):
            # In the pre-list region: keep only things that look like a brand
            # rather than a label (digits or internal capitals, e.g. "3Dator").
            if not re.search(r"\d|[a-zäöüß][A-ZÄÖÜ]", cand):
                unlikely.append(cand)
                continue
        (likely if looks_like_company(cand) else unlikely).append(cand)

    return likely, unlikely


def _tidy(text: str) -> str:
    """
    Strip dates and collapse doubled text.

    Nested markup makes a parent element repeat its child's text, so
    "Brandes Innovation Brandes Innovation 23. Oktober 2017" is one candidate.
    Removing the date and de-duplicating the halves recovers the actual name.
    """
    text = DATE_RE.sub(" ", text)
    text = " ".join(text.split()).strip(" -|,;")

    # "X X" -> "X" when the string is exactly its own first half twice.
    words = text.split()
    if len(words) >= 2 and len(words) % 2 == 0:
        half = len(words) // 2
        if words[:half] == words[half:]:
            text = " ".join(words[:half])

    return text


def extract_candidates(html: str) -> list[str]:
    """Pull plausible organisation names out of structured page elements."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()

    seen: set[str] = set()
    out: list[str] = []

    for el in soup.find_all(CANDIDATE_TAGS):
        # For container tags, keep only leaves; a wrapping <div> would
        # otherwise contribute the entire member list as one candidate.
        if el.name in LEAF_ONLY_TAGS and el.find(True) is not None:
            continue

        text = _tidy(" ".join(el.get_text(separator=" ").split()))

        if not (3 <= len(text) <= 90):
            continue
        # A line that was nothing but a date is gone after _tidy.
        if not re.search(r"[A-Za-zÄÖÜäöüß]{2}", text):
            continue
        if text.casefold() in NAV_NOISE:
            continue
        if not re.search(r"[A-Za-zÄÖÜäöüß]", text):
            continue
        # Pure URLs, e-mail addresses and phone numbers are not names.
        if re.match(r"^(https?://|www\.|\+?\d[\d\s/()-]{6,}$|\S+@\S+)", text):
            continue
        # Sentences are page copy, not company names.
        if text.count(" ") > 9 or text.endswith((".", "!", "?")) and " " in text:
            continue

        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)

    return out


def worksheet_path(row: dict):
    slug = re.sub(r"[^a-z0-9]+", "-", row["org_name"].casefold()).strip("-")[:40]
    return config.GROUND_TRUTH_DIR / f"{row['id']}_{slug}.txt"


HEADER = """\
# ============================================================================
# GROUND TRUTH WORKSHEET  --  {org_name}
#
# URL : {url}
# Page: {words} words, ~{tokens} tokens{chunk_note}
#
# WHAT TO DO
#   1. Open the URL above in your browser, next to this file.
#   2. SECTION A below is my best guess at the member companies.
#      Read down it and DELETE any line that is not a member company.
#   3. SECTION B is what I think is page furniture (menus, filters,
#      categories). Skim it. If I wrongly binned a real company there,
#      MOVE that line up into Section A.
#   4. Then look at the WEBPAGE itself top to bottom. If a member is
#      missing from Section A entirely, type it in. This step matters
#      most -- it catches what my guessing missed.
#   5. Keep names EXACTLY as printed (keep GmbH, AG, umlauts).
#   6. Delete Section B entirely when you are done with it, or leave it --
#      everything below the SECTION B marker is ignored either way.
#   7. Save. Lines starting with # are ignored.
#
# When finished, run:  .venv/bin/python make_ground_truth.py --check
# ============================================================================

# --- SECTION A: likely member companies ({n_likely}) -------------------------

"""

SECTION_B = """
# --- SECTION B: probably page furniture ({n_unlikely}) -----------------------
# Everything below this line is IGNORED. Move anything real up into Section A.

"""


def generate() -> None:
    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}
    with open(config.FETCH_MANIFEST_CSV, encoding="utf-8") as fh:
        manifest = {r["id"]: r for r in csv.DictReader(fh)}

    for uid in SAMPLE_IDS:
        row, man = urls[uid], manifest[uid]
        path = worksheet_path(row)

        if path.exists():
            print(f"  skip (exists) {path.name}")
            continue

        html = fetcher.cache_path(row["url"]).read_text(
            encoding="utf-8", errors="ignore")
        candidates = extract_candidates(html)

        # Page order is preserved within each section so the worksheet still
        # scrolls alongside the live page.
        likely, unlikely = partition(candidates)

        chunk_note = ("  -- this page is SPLIT INTO CHUNKS for the model"
                      if man["would_chunk"] == "True" else "")
        header = HEADER.format(
            org_name=row["org_name"], url=row["url"],
            words=man["word_count"], tokens=man["est_tokens"],
            chunk_note=chunk_note, n_likely=len(likely))

        body = "\n".join(likely) + "\n"
        body += SECTION_B.format(n_unlikely=len(unlikely))
        body += "\n".join(unlikely) + "\n"

        path.write_text(header + body, encoding="utf-8")
        print(f"  wrote {path.name:<50} "
              f"{len(likely):>4} likely + {len(unlikely):>4} binned")


def check() -> None:
    """Validate completed worksheets and write the JSON the evaluator reads."""
    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}

    done = 0
    for uid in SAMPLE_IDS:
        row = urls[uid]
        path = worksheet_path(row)
        if not path.exists():
            print(f"  MISSING   {uid} {row['org_name'][:44]}")
            continue

        names = []
        for line in path.read_text(encoding="utf-8").splitlines():
            # Everything from the Section B marker onward is discarded --
            # that is the bin, and leaving it in place is allowed.
            if line.startswith("# --- SECTION B"):
                break
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            names.append(line)

        # Duplicates in a worksheet mean the same firm gets counted twice.
        dupes = {n for n in names if sum(1 for m in names
                                         if m.casefold() == n.casefold()) > 1}

        out = config.GROUND_TRUTH_DIR / f"{uid}.json"
        out.write_text(json.dumps({
            "id": uid, "org_name": row["org_name"], "url": row["url"],
            "companies": names,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        warn = f"  ! {len(dupes)} duplicate(s)" if dupes else ""
        print(f"  ok        {uid} {len(names):>4} companies  "
              f"{row['org_name'][:38]}{warn}")
        done += 1

    print(f"\n  {done}/{len(SAMPLE_IDS)} worksheets complete")
    if done == len(SAMPLE_IDS):
        print("  Ground truth ready -- Stage A can run.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="validate finished worksheets and emit JSON")
    args = ap.parse_args()
    check() if args.check else generate()
