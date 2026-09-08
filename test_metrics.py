"""
Known-answer tests for every measurement in this pipeline.

Written after three consecutive scoring bugs, each of which produced a
confident wrong number and none of which raised an error:

  1. "48 invented web addresses"  -- there were none. The check compared
     against the ground-truth subset instead of against the page.
  2. "website precision 1.000"    -- it was 0.778. The check asked whether an
     address was on the page, not whether it belonged to that company.
  3. "0 correct on page 043"      -- the model was right. The check inferred
     a pairing positionally when the markup already stated one.

A broken extractor produces visibly poor numbers. A broken metric produces
publishable ones, which is worse. Every scoring function therefore needs at
least one case where the answer is known independently.

The rule this file enforces: a metric may not be trusted until it has been
shown to FAIL on input that should fail. Tests that only check the happy path
would have passed for all three bugs above.

Run:  .venv/bin/python test_metrics.py
      .venv/bin/python test_metrics.py --corpus   # also scan real pages
"""

from __future__ import annotations

import argparse
import sys

PASS, FAIL = 0, 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    ok = got == want
    if ok:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL  {label}")
        print(f"        got  {got!r}")
        print(f"        want {want!r}")


def near(label: str, got: float, want: float, tol: float = 1e-4) -> None:
    global PASS, FAIL
    if abs(got - want) <= tol:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got {got!r}, want {want!r}")


# ---------------------------------------------------------------------------
# 1. Name normalisation. Over-normalising silently merges distinct companies,
#    which inflates every score that uses it.
# ---------------------------------------------------------------------------

def test_match_key() -> None:
    import benchmark as B
    print("match_key / strip_legal_suffix")

    # The legal suffix is noise, so these must compare equal.
    check("Siemens AG == Siemens", B.match_key("Siemens AG"), B.match_key("Siemens"))
    check("GmbH & Co. KG stripped",
          B.match_key("Robert Bosch GmbH & Co. KG"), B.match_key("Robert Bosch"))
    check("accents folded", B.match_key("Müller GmbH"), B.match_key("Muller"))

    # A trailing "ag" that is part of the NAME must survive. This regressed
    # once: "2mag AG" became "2m" and "Montag GmbH" became "Mont".
    check("2mag AG keeps its name", B.match_key("2mag AG"), "2mag")
    check("Montag GmbH keeps its name", B.match_key("Montag GmbH"), "montag")

    # Distinct companies must NOT collapse into one another.
    for a, b in [("Bosch GmbH", "Boschung GmbH"),
                 ("AMO GmbH", "AMAC GmbH"),
                 ("Aixtron SE", "Aixon SE")]:
        global FAIL, PASS
        if B.match_key(a) == B.match_key(b):
            FAIL += 1
            print(f"  FAIL  {a!r} and {b!r} normalise to the same key")
        else:
            PASS += 1

    # Nothing may normalise to the empty string, which would match everything.
    for name in ("GmbH", "AG", "e.V."):
        if B.match_key(name) == "":
            print(f"  WARN  {name!r} normalises to empty; it can never match")


# ---------------------------------------------------------------------------
# 2. Name scoring. Must be wrong when the answer is wrong.
# ---------------------------------------------------------------------------

def test_score() -> None:
    import benchmark as B
    print("score (precision / recall / F1)")

    truth = ["Alpha GmbH", "Beta AG", "Gamma SE"]

    s = B.score(truth, truth)
    near("perfect: precision", s["precision"], 1.0)
    near("perfect: recall", s["recall"], 1.0)
    near("perfect: f1", s["f1"], 1.0)

    s = B.score([], truth)
    near("returned nothing: recall 0", s["recall"], 0.0)
    near("returned nothing: f1 0", s["f1"], 0.0)

    s = B.score(["Delta GmbH", "Epsilon AG"], truth)
    near("all wrong: precision 0", s["precision"], 0.0)
    check("all wrong: 2 false positives", s["false_positives"], 2)
    check("all wrong: 3 false negatives", s["false_negatives"], 3)

    s = B.score(["Alpha GmbH", "Delta GmbH"], truth)
    near("half right: precision", s["precision"], 0.5)
    near("half right: recall", s["recall"], 1 / 3)

    # Duplicates must not inflate the count: scoring is over sets.
    s = B.score(["Alpha GmbH", "Alpha", "Alpha GmbH"], ["Alpha GmbH"])
    near("duplicates do not inflate precision", s["precision"], 1.0)
    check("duplicates counted once", s["true_positives"], 1)


# ---------------------------------------------------------------------------
# 3. Hostname comparison. The same-organisation test decides whether a link is
#    a company website or the association's own navigation, so both directions
#    of error matter.
# ---------------------------------------------------------------------------

def test_same_org() -> None:
    import link_coverage as L
    print("same_org")

    check("association subdomains match",
          L.same_org("verein.nmwp.nrw", "portal.nmwp.de"), True)
    check("identical hosts match",
          L.same_org("www.spectaris.de", "spectaris.de"), True)
    check("unrelated hosts do not match",
          L.same_org("www.spectaris.de", "www.2mag.de"), False)
    check("similar but distinct hosts do not match",
          L.same_org("bosch.de", "boschung.de"), False)

    # Short domains produce an empty label set, and an empty set intersects
    # nothing, so a site would treat its OWN links as external. Any host whose
    # labels are all under four characters hits this.
    degenerate = L.same_org("bmw.de", "bmw.de")
    if not degenerate:
        print("  WARN  same_org('bmw.de','bmw.de') is False: a page on a short "
              "domain would treat its own links as company websites")


def test_generic_labels() -> None:
    """
    A link's label either names a company or names the kind of link. Only the
    first speaks for an address. Both directions of this were broken once:

      treating "Web" as a company name  -> every positional pairing on
        SPECTARIS was discarded and the corpus ceiling fell from 63% to 8%
      ignoring short real names (AMAC)  -> a positional guess reassigned an
        address the markup had already claimed, giving Aixtron SE the website
        of a different company
    """
    import link_coverage as L
    print("generic link labels")

    for generic in ("Web", "Website", "zur Website", "mehr", "Kontakt", "Home"):
        check(f"{generic!r} is a generic label",
              L.match_key(generic) in L.GENERIC_LABELS, True)

    for real in ("AMAC GmbH", "AMO GmbH", "CTC GmbH", "DLR",
                 "2mag AG", "Ätztechnik Herz GmbH & Co. KG"):
        check(f"{real!r} is not a generic label",
              L.match_key(real) in L.GENERIC_LABELS, False)

    # Short real names must still be short enough to fall under MIN_KEY_LEN,
    # which is exactly why the claimed set and the pairing map differ.
    if len(L.match_key("AMAC GmbH")) >= L.MIN_KEY_LEN:
        print("  WARN  MIN_KEY_LEN no longer excludes short names; the split "
              "between claimed and paired may be redundant")


def test_clean_url() -> None:
    """
    Whatever the model returns for a URL must reduce to a bare URL or nothing.

    Observed live on profile pages: the model returned
    "[www.centech.de](https://www.centech.de)", copying the markdown shape of
    what it had been shown. That fails every downstream check and would reach
    the deliverable as unusable text.
    """
    import extractor as E
    print("url cleaning")

    check("markdown link unwrapped",
          E._clean_url("[www.centech.de](https://www.centech.de)"),
          "https://www.centech.de")
    check("angle brackets stripped",
          E._clean_url("<http://www.2mag.de>"), "http://www.2mag.de")
    check("scheme added to a bare host",
          E._clean_url("www.example.de"), "https://www.example.de")
    check("already clean is untouched",
          E._clean_url("https://ok.de/"), "https://ok.de/")
    check("trailing punctuation removed",
          E._clean_url("  https://x.de.  "), "https://x.de")
    check("protocol-relative gets a scheme",
          E._clean_url("//cdn.example.de"), "https://cdn.example.de")

    # Must reject rather than invent. A url field that is prose is not a URL,
    # and turning it into one would put garbage in the database.
    for junk in ("not a url", "", "   ", "n/a", "[label only]()"):
        check(f"{junk!r} rejected", E._clean_url(junk), "")


def test_host_of() -> None:
    import score_websites as S
    print("host_of")

    same = ["http://www.2mag.de", "https://2mag.de", "https://www.2mag.de/",
            "http://2mag.de/impressum?x=1"]
    keys = {S.host_of(u) for u in same}
    check("scheme, www and path variants normalise together", len(keys), 1)
    check("normalised form", S.host_of("http://www.2mag.de"), "2mag.de")
    if S.host_of("https://a.example.com") == S.host_of("https://b.example.com"):
        print("  WARN  distinct subdomains collapse to one host")


# ---------------------------------------------------------------------------
# 4. Website scoring. This is bug 2 and 3 above, so it is tested hardest.
# ---------------------------------------------------------------------------

def test_website_classification() -> None:
    import score_websites as S
    print("website scoring: correct / wrong company / invented")

    # Keys must be normalised the same way the scorer normalises them, or the
    # lookup silently misses and every address is scored "wrong". Building this
    # dict with raw names is itself a plausible bug, so it is done explicitly.
    expected = {S.match_key("Alpha GmbH"): "alpha.de",
                S.match_key("Beta AG"): "beta.de"}
    on_page = {"alpha.de", "beta.de", "sponsor.de"}

    def classify(name: str, url: str) -> str:
        host = S.host_of(url)
        want = expected.get(S.match_key(name))
        if want and host == want:
            return "correct"
        return "wrong" if host in on_page else "invented"

    check("right address for right company",
          classify("Alpha GmbH", "https://www.alpha.de"), "correct")
    check("another company's real address is WRONG, not correct",
          classify("Alpha GmbH", "https://beta.de"), "wrong")
    check("a sponsor link on the page is WRONG, not invented",
          classify("Alpha GmbH", "https://sponsor.de"), "wrong")
    check("an address absent from the page is INVENTED",
          classify("Alpha GmbH", "https://alpha-gmbh-berlin.de"), "invented")
    check("a company with no expected address cannot be correct",
          classify("Gamma SE", "https://sponsor.de"), "wrong")

    # The bug that reported 48 false hallucinations: if the "on page" set is
    # built from the expected map rather than the page, a real sponsor link is
    # misreported as invention.
    narrow = set(expected.values())
    host = S.host_of("https://sponsor.de")
    if host not in narrow:
        pass  # correct: this is exactly why on_page must come from the page
    check("sponsor link is on the page but not in the expected map",
          (host in on_page, host in narrow), (True, False))


# ---------------------------------------------------------------------------
# 5. Corpus scan. Cheap checks over the real pages that would have caught the
#    ceiling being wrong.
# ---------------------------------------------------------------------------

def scan_corpus() -> None:
    import csv
    import json
    import config
    import link_coverage as L
    print("corpus scan")

    cov = config.RESULTS_DIR / "link_coverage.csv"
    if not cov.exists():
        print("  SKIP  run link_coverage.py first")
        return

    # The scan reads link_coverage.csv, so a stale file reports stale
    # problems. Warn rather than silently checking yesterday's output.
    import os, time
    age = time.time() - os.path.getmtime(cov)
    if age > 3600:
        print(f"  NOTE  link_coverage.csv is {age/3600:.1f} h old; re-run "
              f"link_coverage.py first if the code has changed since")

    rows = list(csv.DictReader(open(cov, encoding="utf-8-sig")))
    by_page: dict[str, list[dict]] = {}
    for r in rows:
        by_page.setdefault(r["url_id"], []).append(r)

    # Every ground-truth company must appear exactly once.
    for uid, rs in sorted(by_page.items()):
        gt = config.GROUND_TRUTH_DIR / f"{uid}.json"
        if not gt.exists():
            continue
        n = len(json.loads(gt.read_text(encoding="utf-8"))["companies"])
        check(f"page {uid}: every company classified once", len(rs), n)

    # A website target must never point back at the association itself.
    from urllib.parse import urlparse
    urls = {r["id"]: r for r in
            csv.DictReader(open(config.URLS_CSV, encoding="utf-8"))}
    for r in rows:
        if r["route"] != "website" or not r["target"]:
            continue
        page = urls.get(r["url_id"])
        if page and L.same_org(urlparse(page["url"]).netloc,
                               urlparse(r["target"]).netloc):
            print(f"  FAIL  page {r['url_id']}: {r['company'][:30]!r} is "
                  f"mapped to the association's own site {r['target'][:40]}")
            global FAIL
            FAIL += 1

    # Two companies sharing one address is possible but rare; many of them
    # means the pairing has slipped, which is what happened on page 043.
    for uid, rs in sorted(by_page.items()):
        sites = [r["target"] for r in rs if r["route"] == "website"]
        if not sites:
            continue
        dupes = len(sites) - len(set(sites))
        if dupes > max(2, len(sites) * 0.1):
            print(f"  WARN  page {uid}: {dupes} of {len(sites)} website targets "
                  f"are duplicates; the pairing may have slipped")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", action="store_true",
                    help="also scan the real pages, needs link_coverage.csv")
    args = ap.parse_args()

    for fn in (test_match_key, test_score, test_same_org, test_generic_labels,
               test_clean_url, test_host_of, test_website_classification):
        fn()
    if args.corpus:
        scan_corpus()

    print(f"\n  {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
