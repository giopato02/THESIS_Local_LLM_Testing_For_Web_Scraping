"""
Remove name+location duplicates from the ground-truth worksheets.

Some member directories print the company name and, directly beneath it, the
city and federal state. Nested markup means the candidate extractor picks up
both the inner element (the name alone) and the outer one (name + location):

    AFRY Management Consulting GmbH Düsseldorf Nordrhein-Westfalen
    AFRY Management Consulting GmbH

Ground truth must hold the NAME only. If the answer key contained the longer
string, a model that correctly returned "AFRY Management Consulting GmbH"
would be scored as wrong, and a correct model would look inaccurate.

SAFETY
------
Deleting any line that merely starts with another line would be dangerous:
"Siemens" is a prefix of "Siemens Energy AG", but those are different firms.
So a line is only removed when the extra text is *specifically* a German
location -- it ends in one of the 16 Bundesländer, or in a bare city name
that directly follows a complete company name ending in a legal form.

Edits are made in place and existing hand-edits are preserved: the script
only ever deletes a longer duplicate whose shorter twin is still present.

Run:  .venv/bin/python tidy_worksheets.py            # report only
      .venv/bin/python tidy_worksheets.py --apply    # actually edit
"""

from __future__ import annotations

import argparse
import re

import config

BUNDESLAENDER = [
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen",
    "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen",
    "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen-Anhalt",
    "Sachsen", "Schleswig-Holstein", "Thüringen",
]

# Address fragments that are never part of a company name.
ADDRESS_NOISE = re.compile(
    r"\s+(c/o|z\.?Hd\.?|Postfach|Niederlassung)\b.*$", re.IGNORECASE)


def is_location_suffix(extra: str) -> bool:
    """Is the text trailing a shorter name purely a German location?"""
    extra = extra.strip(" ,-–|")
    if not extra:
        return False
    # Ends in a federal state: "Düsseldorf Nordrhein-Westfalen", "Bayern".
    for land in BUNDESLAENDER:
        if extra.endswith(land):
            return True
    return False


def tidy_lines(lines: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Return (kept lines, [(removed, kept_twin), ...])."""
    # Index the content lines by their exact text for prefix lookup.
    content = [l for l in lines if l.strip() and not l.startswith("#")]
    by_text = {l.strip(): True for l in content}

    removed: list[tuple[str, str]] = []
    out: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out.append(line)
            continue

        drop_for: str | None = None
        # Does a shorter twin exist, with only a location between them?
        for other in by_text:
            if other == stripped or not stripped.startswith(other):
                continue
            if is_location_suffix(stripped[len(other):]):
                drop_for = other
                break

        if drop_for:
            removed.append((stripped, drop_for))
            continue

        # Strip trailing "c/o ..." style address noise even with no twin.
        cleaned = ADDRESS_NOISE.sub("", stripped).strip()
        if cleaned != stripped and cleaned:
            removed.append((stripped, cleaned))
            out.append(cleaned)
            continue

        out.append(line)

    return out, removed


def strip_trailing_city(uid: str, lines: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """
    Remove a trailing ", <City>" using the cached page as the authority.

    Some directories print the company and its town in one element, so the
    candidate extractor joins them: "AEU Tech GmbH, Borchen". In the cleaned
    text the model actually receives, those sit on separate lines, so the model
    returns the name alone. A key containing the city would score every correct
    extraction as both a miss and a false positive.

    To avoid stripping a genuine part of a name, a suffix is only removed when
    that exact text also appears as a standalone line in the cached page --
    i.e. it is demonstrably a separate field on the page, not part of the name.
    """
    import csv as _csv
    import cleaner as _cleaner
    import fetcher as _fetcher

    with open(config.URLS_CSV, encoding="utf-8") as fh:
        row = {r["id"]: r for r in _csv.DictReader(fh)}[uid]
    path = _fetcher.cache_path(row["url"])
    if not path.exists():
        return lines, []

    page = _cleaner.process(path.read_text(encoding="utf-8", errors="ignore"))
    standalone = {l.strip().rstrip(",") for l in page.text.split("\n")
                  if 0 < len(l.strip()) <= 40}

    out, removed = [], []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out.append(line)
            continue

        if "," in stripped:
            head, _, tail = stripped.rpartition(",")
            tail = tail.strip()
            # Only strip when the page itself prints that text on its own line.
            if head.strip() and tail and tail in standalone:
                removed.append((stripped, head.strip().rstrip(",")))
                out.append(head.strip().rstrip(","))
                continue

        out.append(line)
    return out, removed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the changes (default is a dry run)")
    ap.add_argument("--strip-city", metavar="ID",
                    help="remove trailing ', City' from one worksheet")
    args = ap.parse_args()

    if args.strip_city:
        uid = args.strip_city
        path = next(config.GROUND_TRUTH_DIR.glob(f"{uid}_*.txt"))
        lines = path.read_text(encoding="utf-8").splitlines()
        kept, removed = strip_trailing_city(uid, lines)
        print(f"  {path.name}: {len(removed)} line(s) would change\n")
        for before, after in removed[:10]:
            print(f"      {before[:58]}")
            print(f"   -> {after[:58]}")
        if len(removed) > 10:
            print(f"      ... and {len(removed)-10} more")
        if args.apply:
            path.write_text("\n".join(kept) + "\n", encoding="utf-8")
            print("\n  applied.")
        else:
            print("\n  dry run -- add --apply to write.")
        return

    total_removed = 0
    for path in sorted(config.GROUND_TRUTH_DIR.glob("*.txt")):
        lines = path.read_text(encoding="utf-8").splitlines()
        kept, removed = tidy_lines(lines)
        if not removed:
            continue

        total_removed += len(removed)
        print(f"\n  {path.name}  --  {len(removed)} duplicate(s)")
        for bad, good in removed[:6]:
            print(f"      drop: {bad[:66]}")
            print(f"      keep: {good[:66]}")
        if len(removed) > 6:
            print(f"      ... and {len(removed)-6} more")

        if args.apply:
            path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    print(f"\n  {total_removed} name+location duplicates found")
    if args.apply:
        print("  worksheets updated.")
    else:
        print("  dry run -- re-run with --apply to edit the files.")


if __name__ == "__main__":
    main()
