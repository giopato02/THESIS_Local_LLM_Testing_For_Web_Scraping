"""
Measure the quality of the ground truth, so its limits are numbers.

Two questions, both worth reporting in the thesis rather than assuming.

OFFLINE (default)
    Does every answer-key entry appear in the text the model receives, and is
    the key free of the things that should never be in it: duplicates, contact
    details, filter entries, addresses left on a line?

    An entry the model cannot see costs every model a miss, so it makes the
    task look harder than it is. An entry missing from the key turns a correct
    answer into a false alarm, which looks like hallucination. The first is
    visible here; the second only shows up in the consensus audit after a run.

LIVE (--live)
    How far the saved copies have drifted from the websites since they were
    taken. Members join and leave, so a key written against a snapshot is a
    statement about that date. Measured, this is a result for Neovation: it
    says how quickly a company database built from these pages goes stale.

    Not all pages can be measured this way: several build their member list in
    the browser, so a plain request sees nothing. Those are reported as
    "cannot tell" rather than counted as drift.

Run:  .venv/bin/python check_ground_truth.py
      .venv/bin/python check_ground_truth.py --live
      .venv/bin/python check_ground_truth.py --live --page 079
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
import unicodedata

import benchmark
import cleaner
import config
import fetcher
import make_ground_truth as G


def squash(text: str) -> str:
    """Letters and digits only, so spacing and punctuation cannot differ."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text)


def page_text(url: str) -> str:
    path = fetcher.cache_path(url)
    if not path.exists():
        return ""
    return cleaner.process(path.read_text(encoding="utf-8", errors="ignore"), url).text


def audit_page(uid: str, row: dict) -> dict:
    names = json.loads((config.GROUND_TRUTH_DIR / f"{uid}.json")
                       .read_text(encoding="utf-8"))["companies"]
    text = page_text(row["url"])
    flat = squash(text)
    keys = [benchmark.match_key(n) for n in names]
    return {
        "id": uid, "network": row["org_name"], "entries": len(names),
        "distinct": len({k for k in keys if k}),
        "repeated": len(names) - len({k for k in keys if k}),
        "contact_or_filter": [n for n in names
                              if G.is_contact_detail(n) or G.is_filter_facet(n)],
        "address_on_line": [n for n in names if G.core_name(n) != n],
        # The legal form may sit on the next line ("Ritterschaftliches
        # Kreditinstitut Stade" / "AG"), and scoring ignores it anyway.
        "not_in_model_text": [n for n in names if squash(n) not in flat
                              and squash(benchmark.strip_legal_suffix(n)) not in flat],
        "empty_key": [n for n in names if not benchmark.match_key(n)],
    }


def live_drift(uid: str, row: dict, session) -> dict:
    """How much the live page has moved away from the saved copy."""
    names = json.loads((config.GROUND_TRUTH_DIR / f"{uid}.json")
                       .read_text(encoding="utf-8"))["companies"]
    try:
        resp = session.get(row["url"], timeout=25)
    except Exception as exc:
        return {"id": uid, "status": f"unreachable ({type(exc).__name__})"}
    if resp.status_code != 200:
        return {"id": uid, "status": f"HTTP {resp.status_code}"}

    live = squash(resp.text)
    saved = squash(page_text(row["url"]))
    # A page that renders its list in the browser returns almost none of the
    # companies to a plain request. Saying "everything disappeared" there would
    # measure JavaScript, not drift.
    still_there = sum(1 for n in names if squash(n) in live)
    if still_there < 0.2 * len(names):
        return {"id": uid, "status": "cannot tell (the live page needs a browser)",
                "gone": None}
    gone = [n for n in names if squash(n) not in live]
    return {"id": uid, "status": "ok", "entries": len(names), "gone": gone,
            "saved_still_matches": squash(saved) == live}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="also compare against the websites as they are today")
    ap.add_argument("--page", default=None, help="restrict to one url_id")
    args = ap.parse_args()

    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}
    ids = [u for u in G.SAMPLE_IDS
           if (config.GROUND_TRUTH_DIR / f"{u}.json").exists()
           and (args.page is None or u == args.page)]

    print(f"{'id':<5}{'network':<32}{'entries':>8}{'distinct':>9}  what to look at")
    totals = {"entries": 0, "repeated": 0, "unseen": 0, "other": 0}
    for uid in ids:
        a = audit_page(uid, urls[uid])
        totals["entries"] += a["entries"]
        totals["repeated"] += a["repeated"]
        totals["unseen"] += len(a["not_in_model_text"])
        totals["other"] += len(a["contact_or_filter"]) + len(a["address_on_line"]) + len(a["empty_key"])
        notes = []
        if a["repeated"]:
            notes.append(f"{a['repeated']} repeated (same firm listed twice)")
        if a["not_in_model_text"]:
            notes.append(f"{len(a['not_in_model_text'])} not in the model's text: "
                         f"{a['not_in_model_text'][0][:34]!r}")
        for label, key in (("contact/filter", "contact_or_filter"),
                           ("address on line", "address_on_line"),
                           ("empty after normalising", "empty_key")):
            if a[key]:
                notes.append(f"{len(a[key])} {label}: {a[key][0][:30]!r}")
        print(f"{uid:<5}{a['network'][:30]:<32}{a['entries']:>8}{a['distinct']:>9}  "
              f"{'; '.join(notes) if notes else 'clean'}")

    n = totals["entries"]
    print(f"\n  {len(ids)} pages, {n} entries")
    print(f"  entries the model cannot see in its input: {totals['unseen']} "
          f"({totals['unseen'] / n:.2%})  <- every model loses these")
    print(f"  repeated names (counted once when scoring): {totals['repeated']}")
    print(f"  other problems: {totals['other']}")
    print("  what this cannot see: a member missing from the key. That only "
          "surfaces\n  after a run, when every model returns the same name the "
          "key does not have.")

    if not args.live:
        return
    import requests
    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT,
                            "Accept-Language": "de-DE,de;q=0.9"})
    print(f"\n{'id':<5}{'network':<32}{'gone from the live site':>26}  note")
    measurable = drift = entries = 0
    for uid in ids:
        d = live_drift(uid, urls[uid], session)
        time.sleep(1)
        if d["status"] != "ok":
            print(f"{uid:<5}{urls[uid]['org_name'][:30]:<32}{'-':>26}  {d['status']}")
            continue
        measurable += 1
        drift += len(d["gone"])
        entries += d["entries"]
        share = len(d["gone"]) / d["entries"]
        count = f"{len(d['gone'])} of {d['entries']}"
        print(f"{uid:<5}{urls[uid]['org_name'][:30]:<32}{count:>26}  {share:.0%}")
    if measurable:
        print(f"\n  measurable on {measurable} of {len(ids)} pages: {drift} of {entries} "
              f"companies ({drift / entries:.1%}) are no longer on the live page")
        print("  the rest need a browser to read, so drift there is unknown")


if __name__ == "__main__":
    main()
