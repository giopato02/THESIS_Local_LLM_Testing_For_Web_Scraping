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

import cleaner
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

# Round 2 (2026-09-22): 20 pages chosen from the 291 Finalv1 networks to cover
# every layout, a range of sizes, long pages and ZIM networks, with each
# look-alike website template and each network manager at most once. Two
# first choices were replaced because their saved page held only page one of
# a longer list. Method and reasons: THESIS_NOTES section 3.14 and
# results/ground_truth_expansion_20.csv. 045 (OptoNet) was already in the URL
# list; 079 is VDGH at its Finalv1 address, because 055's saved page is empty.
SAMPLE_IDS += [
    "074", "075", "076", "077", "078", "079", "080", "081", "082", "083",
    "084", "045", "085", "086", "087", "088", "089", "090", "091", "092",
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


def is_contact_detail(text: str) -> bool:
    """
    A web address, e-mail address or phone number rather than a name.

    The old rule wanted an e-mail to be one unbroken token, which missed
    VDGH's spam-protected form, "info@ avoid-unrequested-mails agendia.com".
    85 of that page's 203 candidates were contact details (2026-09-25). Any
    "@" is enough to disqualify a line, since company names do not carry one.
    """
    # An e-mail has a domain after the "@". A bare "@" does not disqualify a
    # line: "ST@RT HÜRTH Zentrum für Technologie und Existenzgründung" is a
    # real member of BVIZ, and the first version of this rule deleted it.
    if re.search(r"@[^@]{0,40}\.[a-z]{2,}\b", text, re.IGNORECASE):
        return True
    if re.match(r"^(https?://|www\.)", text, re.IGNORECASE):
        return True
    # A bare domain on its own line: "cepheid.com/de", "WWW.BIOTYPE.DE".
    if re.match(r"^[\w.-]+\.(de|com|eu|net|org|info|io|ch|at|nl|fr|uk)(/\S*)?$",
                text, re.IGNORECASE):
        return True
    if re.match(r"^(tel|telefon|fax|mobil|phone)\b", text, re.IGNORECASE):
        return True
    if re.match(r"^\+?\d[\d\s/()-]{6,}$", text):
        return True
    # Address lines. Wirtschaftsvereinigung Stahl prints "47137 Duisburg"
    # under every member, 43 of its 132 candidates (2026-09-25). A line with a
    # legal form in it is a name, never an address, so it is safe from here.
    if LEGAL_HINT.search(text):
        return False
    if re.match(r"^\d{4,5}\s+[A-ZÄÖÜ][\w.\-/ ]{1,40}$", text):
        return True
    return bool(re.match(
        r"^[\w.\-äöüßÄÖÜ ]{2,40}(stra(ß|ss)e|str\.|weg|allee|platz|gasse|ring|damm)"
        r"\s+\d+[a-z]?$", text, re.IGNORECASE))


DOMAIN_TAIL = re.compile(
    r"\s+(https?://\S+|www\.\S+|[\w.-]+\.(de|com|eu|net|org|info|io|ch|at|nl|fr|uk)(/\S*)?)$",
    re.IGNORECASE)
PLACE_TAIL = re.compile(r"\s+\d{4,5}\s+[A-ZÄÖÜ][\w.\-/ ]{1,40}$")


def is_filter_facet(text: str) -> bool:
    """
    A filter checkbox from the page's search sidebar, not a member.

    OSBA's page ends its member list with a filter widget whose every entry
    carries the number of matching companies: "Agile Methoden / Scrum (24)",
    "Beratung (94)". 157 of that worksheet's 252 candidates were these
    (2026-09-25). A real company name can end in brackets, so the count alone
    decides, and a line carrying a legal form is never a facet.
    """
    if not re.search(r"\(\d{1,4}\)\s*$", text):
        return False
    return not LEGAL_HINT.search(text)


def core_name(text: str) -> str:
    """
    Strip a trailing address and web address from a candidate line.

    Wirtschaftsvereinigung Stahl prints every member twice: once as
    "ArcelorMittal Bremen GmbH 28237 Bremen bremen.arcelormittal.com" and once
    as "ArcelorMittal Bremen GmbH" (2026-09-25). Ground truth holds the name
    alone, so the tail comes off and the pair collapses into one entry.
    """
    out = text.strip()
    for _ in range(3):
        new = PLACE_TAIL.sub("", DOMAIN_TAIL.sub("", out)).strip(" ,;|-")
        # "Laser 2000 GmbH" and "BSK 1818 AG" look like "<something> <postcode>
        # <Word>" to the address rule. A tail carrying a legal form is part of
        # the name, never an address (2026-09-26).
        if new != out and LEGAL_HINT.search(out[len(new):]):
            break
        if new == out:
            break
        out = new
    return out or text.strip()


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
    text = cleaner.strip_invisible(text)
    text = DATE_RE.sub(" ", text)
    text = " ".join(text.split()).strip(" -|,;")

    # "X X" -> "X" when the string is exactly its own first half twice.
    words = text.split()
    if len(words) >= 2 and len(words) % 2 == 0:
        half = len(words) // 2
        if words[:half] == words[half:]:
            text = " ".join(words[:half])

    return text


def extract_candidates(html: str, page_url: str | None = None) -> list[str]:
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
        if is_contact_detail(text) or is_filter_facet(text):
            continue
        # Sentences are page copy, not company names.
        if text.count(" ") > 9 or text.endswith((".", "!", "?")) and " " in text:
            continue

        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)

    # Round 2 (2026-09-22) found pages the element walk above barely sees: a
    # logo wall, where each name exists only as an image's alt text (VSI, 0
    # candidates), and a list printed as plain lines (vdp, 0 candidates). Both
    # are added here: image alt texts, and lines of the cleaned page text that
    # carry a legal form. Still rules only, never a model, and still only a
    # pre-fill for a human to correct.
    extra = []
    for img in soup.find_all("img"):
        extra.append(re.sub(r"^(logo|firmenlogo)\s*[:-]?\s*", "",
                            (img.get("alt") or img.get("title") or "").strip(),
                            flags=re.IGNORECASE))
    if page_url is not None:
        import cleaner
        for line in cleaner.process(html, page_url).text.split("\n"):
            line = re.sub(r"\s*<https?://[^>]+>", "", line).strip()
            if LEGAL_HINT.search(line):
                extra.append(line)
    for text in extra:
        text = _tidy(" ".join(text.split()))
        if not (3 <= len(text) <= 90) or not re.search(r"[A-Za-zÄÖÜäöüß]{2}", text):
            continue
        if text.casefold() in NAV_NOISE or text.count(" ") > 9:
            continue
        key = text.casefold()
        if key not in seen:
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
# Saved copy (exactly what the model reads): results/html_cache/{cache_file}
# Page: {words} words, ~{tokens} tokens{chunk_note}
#
# WHAT TO DO
#   1. Open the saved copy above (or the URL) in your browser, next to this file.
#   2. SECTION A below is my best guess at the member companies.
#      Read down it and DELETE any line that is not a member company.
#   3. SECTION B is what I think is page furniture (menus, filters,
#      categories). Skim it. If I wrongly binned a real company there,
#      MOVE that line up into Section A.
#   4. Then look at the WEBPAGE itself top to bottom. If a member is
#      missing from Section A entirely, type it in. This step matters
#      most -- it catches what my guessing missed. Only this page: do not
#      follow "page 2" or "load more".
#   5. Keep names EXACTLY as printed (keep GmbH, AG, umlauts), but leave out
#      a city or address printed on the same line.
#   6. Delete Section B entirely when you are done with it, or leave it --
#      everything below the SECTION B marker is ignored either way.
#   7. Save. Lines starting with # are ignored.
#   8. When this page is finished, change TODO to DONE on the STATUS line
#      below. --check turns only DONE worksheets into answer keys.
#
# When finished, run:  .venv/bin/python make_ground_truth.py --check
# ============================================================================
# STATUS: TODO

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
        candidates = extract_candidates(html, row["url"])

        # Page order is preserved within each section so the worksheet still
        # scrolls alongside the live page.
        likely, unlikely = partition(candidates)

        chunk_note = ("  -- this page is SPLIT INTO CHUNKS for the model"
                      if man["would_chunk"] == "True" else "")
        header = HEADER.format(
            org_name=row["org_name"], url=row["url"],
            cache_file=fetcher.cache_path(row["url"]).name,
            words=man["word_count"], tokens=man["est_tokens"],
            chunk_note=chunk_note, n_likely=len(likely))

        body = "\n".join(likely) + "\n"
        body += SECTION_B.format(n_unlikely=len(unlikely))
        body += "\n".join(unlikely) + "\n"

        path.write_text(header + body, encoding="utf-8")
        print(f"  wrote {path.name:<50} "
              f"{len(likely):>4} likely + {len(unlikely):>4} binned")


def worksheet_status(text: str) -> str:
    """'todo' or 'done'. Round-1 worksheets predate the STATUS line: done."""
    m = re.search(r"^# STATUS:\s*(\w+)", text, re.MULTILINE)
    return "todo" if m and m.group(1).upper() != "DONE" else "done"


def parse_worksheet(text: str) -> list[str]:
    """The names in Section A. Section B and comment lines are ignored."""
    names = []
    for line in text.splitlines():
        # Everything from the Section B marker onward is discarded --
        # that is the bin, and leaving it in place is allowed.
        if line.startswith("# --- SECTION B"):
            break
        line = line.strip()
        if line and not line.startswith("#"):
            names.append(line)
    return names


def check() -> None:
    """Turn finished (DONE) worksheets into the JSON answer keys."""
    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}

    done = todo = 0
    for uid in SAMPLE_IDS:
        row = urls[uid]
        path = worksheet_path(row)
        out = config.GROUND_TRUTH_DIR / f"{uid}.json"
        if not path.exists():
            print(f"  MISSING   {uid} {row['org_name'][:44]}")
            continue
        text = path.read_text(encoding="utf-8")

        # An unfinished worksheet must never become an answer key. Before the
        # STATUS line existed, --check converted every worksheet it found, and
        # the unedited pre-fill of the 20 new pages briefly became "ground
        # truth" (2026-09-22). A stale key from such a run is removed here.
        if worksheet_status(text) == "todo":
            if out.exists():
                out.unlink()
            print(f"  todo      {uid} {row['org_name'][:44]}")
            todo += 1
            continue

        names = parse_worksheet(text)

        # A repeated name is normal: a directory lists the same firm once per
        # site, as Industrieverband Klebstoffe does for Evonik in Darmstadt and
        # in Marl (2026-09-25). Scoring compares sets, so the company counts
        # once and a model that returns it once loses nothing. Both numbers are
        # reported rather than warned about.
        import benchmark
        distinct = len({benchmark.match_key(n) for n in names
                        if benchmark.match_key(n)})

        out.write_text(json.dumps({
            "id": uid, "org_name": row["org_name"], "url": row["url"],
            "companies": names,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        note = ("" if distinct == len(names)
                else f"  ({distinct} distinct, a name listed twice is one company)")
        print(f"  ok        {uid} {len(names):>4} companies  "
              f"{row['org_name'][:38]}{note}")
        done += 1

    print(f"\n  {done}/{len(SAMPLE_IDS)} worksheets done, {todo} still to label")
    if done == len(SAMPLE_IDS):
        print("  Ground truth ready -- Stage A can run.")
    else:
        print("  Stage A skips every page without an answer key until it is done.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="validate finished worksheets and emit JSON")
    args = ap.parse_args()
    check() if args.check else generate()
