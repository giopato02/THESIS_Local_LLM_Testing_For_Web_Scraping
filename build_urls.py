"""
Build data/urls_73.csv -- the single input list for the whole pipeline.

The 73 target URLs come from two separate collection efforts and are NOT
equivalent, so we keep a url_type column:

  * 59 from Diego's Verbaende spreadsheet -> real member-directory pages.
  * 14 from Yusif's innovation-clubs spreadsheet -> organisation homepages only.

The homepages are expected to under-perform, because a homepage usually is not
a member list. Flagging them means that failure is explainable in the results
rather than looking like model error.

Run:  .venv/bin/python build_urls.py
"""

from __future__ import annotations

import csv

import config


def load_verbaende() -> list[dict]:
    """Rows from the technical-associations sheet that carry a member-list URL."""
    out = []
    with open(config.SOURCE_VERBAENDE, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            url = (row.get("URL Mitglieder-/Teilnehmerliste") or "").strip()
            # Most cells hold German prose like "Keine oeffentliche Liste
            # gefunden" rather than a link, so require a real scheme.
            if not url.lower().startswith("http"):
                continue
            out.append({
                "org_name": (row.get("Name") or "").strip(),
                "url": url,
                "url_type": "member_list",
                "source_file": "Deutsche_technische_Verbaende_erweitert",
                "collected_by": "Diego",
                "notes": (row.get("Mitgliederanzahl") or "").strip(),
            })
    return out


def load_clubs() -> list[dict]:
    """Innovation clubs marked Relevant? = Yes."""
    out = []
    with open(config.SOURCE_CLUBS, encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh, delimiter=";"))

    # Row 0 is a spreadsheet title banner; row 1 is the real header.
    header = rows[1]
    idx = {name: i for i, name in enumerate(header)}

    for row in rows[2:]:
        if len(row) <= idx["Relevant?"]:
            continue
        if row[idx["Relevant?"]].strip().lower() != "yes":
            continue
        url = row[idx["Website"]].strip()
        if not url.lower().startswith("http"):
            continue
        out.append({
            "org_name": row[idx["Name"]].strip(),
            "url": url,
            "url_type": "homepage",
            "source_file": "Private_funded_innovation_clubs_FINAL_200",
            "collected_by": "Yusif",
            "notes": row[idx["Notes"]].strip() if len(row) > idx["Notes"] else "",
        })
    return out


def main() -> None:
    verbaende = load_verbaende()
    clubs = load_clubs()
    records = verbaende + clubs

    # Deduplicate on URL while preserving order; member_list rows come first
    # so a duplicated URL keeps its more informative type.
    seen: set[str] = set()
    deduped = []
    for rec in records:
        key = rec["url"].rstrip("/").lower()
        if key in seen:
            print(f"  ! duplicate URL skipped: {rec['url']}")
            continue
        seen.add(key)
        deduped.append(rec)

    fields = ["id", "org_name", "url", "url_type", "source_file",
              "collected_by", "notes"]
    with open(config.URLS_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for i, rec in enumerate(deduped, start=1):
            writer.writerow({"id": f"{i:03d}", **rec})

    print(f"Verbaende (member lists, Diego): {len(verbaende)}")
    print(f"Clubs (homepages, Yusif):        {len(clubs)}")
    print(f"Total written:                   {len(deduped)} -> {config.URLS_CSV}")


if __name__ == "__main__":
    main()
