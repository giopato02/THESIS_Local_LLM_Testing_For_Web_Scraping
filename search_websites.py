"""
Stage 4: find a website for companies the directory does not link at all.

link_coverage.py sorts every member into three routes. This handles `none`:
the company name is plain text on the page, with no link of any kind, so
neither the model (stage 1) nor a profile-page fetch (stage 3) can help.
Measured on the ground-truth corpus, that is 165 of 761 companies, 22%.

No model is used. A web search returns candidate URLs and Python decides
whether any of them belongs to the company. Deciding that is string and
hostname comparison, which Python does exactly, so a model would be slower and
no more accurate.

--------------------------------------------------------------------------
VERIFICATION IS THE POINT, NOT THE SEARCH
--------------------------------------------------------------------------
A search always returns something. The whole value of this stage is refusing
the results that are wrong, because an unverified guess is worse than a blank
cell: a blank is visibly missing, a plausible wrong domain enters Neovation's
database and nobody catches it. The measured hallucination difference between
models (0.3% against 2.1%, section 3.13j) is the same concern one layer down.

Three filters, in order of how much work they cost:

  1. Reject known aggregators. A German company search returns business
     directories far more often than the company's own site: northdata,
     wlw, firmenwissen, LinkedIn, Wikipedia. None of those is a company
     website, and no amount of page-fetching makes them one.

  2. Prefer a domain that resembles the name. "actain engineering GmbH" ->
     actain.de is strong evidence on its own and costs nothing to check.

  3. Fetch the candidate and look for the company name in the page. This is
     the expensive check and the only one that confirms rather than suggests.

A result passes only if it survives 1 and then satisfies 2 or 3.

Run:  .venv/bin/python search_websites.py --limit 10   # try a few first
      .venv/bin/python search_websites.py
      .venv/bin/python search_websites.py --no-fetch   # search only, faster
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from urllib.parse import urlparse

import requests

import config

IN_CSV = config.RESULTS_DIR / "link_coverage.csv"
OUT_CSV = config.RESULTS_DIR / "searched_websites.csv"

FIELDS = [
    "url_id", "org_name", "company", "query",
    "found_url", "status", "evidence", "candidates_seen",
]

# Business directories, registries, social networks and job boards. These
# dominate German company searches and none of them is a company website.
AGGREGATORS = {
    "northdata.com", "northdata.de", "wlw.de", "firmenwissen.de",
    "companyhouse.de", "unternehmensregister.de", "bundesanzeiger.de",
    "handelsregister.de", "creditreform.de", "moneyhouse.de", "bisnode.de",
    "dnb.com", "opencorporates.com", "crunchbase.com", "bloomberg.com",
    "zoominfo.com", "dun-bradstreet.com", "implisense.com", "kompass.com",
    "europages.de", "europages.com", "gelbeseiten.de", "dasoertliche.de",
    "11880.com", "meinestadt.de", "cylex.de", "yelp.com", "yelp.de",
    "linkedin.com", "xing.com", "facebook.com", "instagram.com", "twitter.com",
    "x.com", "youtube.com", "tiktok.com", "kununu.com", "glassdoor.com",
    "indeed.com", "stepstone.de", "monster.de",
    "wikipedia.org", "wikidata.org", "dbpedia.org",
    "amazon.de", "ebay.de", "google.com", "bing.com", "duckduckgo.com",
    "researchgate.net", "scholar.google.com",
    # Found in live testing; the long tail of German B2B directories is
    # effectively endless, which is why the path heuristic below matters more
    # than this list.
    "lieferanten.de", "wirtschaftsforum.de", "online-handelsregister.de",
    "elektro-einkaufsfuehrer.de", "industrystock.de", "exportpages.de",
    "firmendb.de", "unternehmensauskunft.de", "web2.cylex.de", "branchenbuch.de",
    "goyellow.de", "marktplatz-mittelstand.de", "trustpilot.com",
}

# Words that carry no identity, so a domain matching only these means nothing.
STOPWORDS = {
    "gmbh", "ag", "kg", "se", "ug", "mbh", "co", "und", "the", "der", "die",
    "das", "deutschland", "germany", "group", "gruppe", "holding", "system",
    "systems", "solution", "solutions", "service", "services", "technologie",
    "technologies", "technology", "engineering", "consulting", "institut",
    "institute", "zentrum", "center", "centre", "verein", "eV", "international",
    "europe", "european", "nord", "sued", "west", "ost", "neue", "adresse",
    # Industry words. A domain matching only these is not evidence: TARGO
    # Leasing GmbH matched targo-leasing.de on "leasing", which would equally
    # have matched any other leasing company.
    "leasing", "logistik", "logistics", "transport", "spedition", "immobilien",
    "industrie", "industrial", "produktion", "production", "handel", "trading",
    "vertrieb", "beratung", "management", "digital", "media", "labor",
    "energie", "energy", "elektronik", "electronics", "automation",
    "software", "computer", "data", "medizin", "medical", "pharma", "chemie",
    "kunststoff", "metall", "maschinenbau", "werke", "werk", "partner",
    "partners", "projekt", "projekte", "innovation", "innovations",
    # Place names. Found by spot-check: "Hochschule Bielefeld" matched
    # chancenportal-bielefeld.de on the city, which would equally have matched
    # any other organisation in Bielefeld. Only the cities appearing in this
    # corpus are listed; the general problem needs a gazetteer.
    "bielefeld", "berlin", "muenchen", "munich", "hamburg", "koeln",
    "cologne", "frankfurt", "stuttgart", "duesseldorf", "dortmund", "essen",
    "bremen", "hannover", "nuernberg", "aachen", "paderborn", "erfurt",
    "leipzig", "dresden", "chemnitz", "bochum", "wuppertal", "bonn",
    "muenster", "karlsruhe", "mannheim", "augsburg", "kiel", "luebeck",
    "rostock", "jena", "ilmenau", "suhl", "goettingen", "kassel",
}


def match_key(name: str) -> str:
    import benchmark
    return benchmark.match_key(name)


def host_of(url: str) -> str:
    u = url.strip().lower()
    for prefix in ("https://", "http://", "//"):
        if u.startswith(prefix):
            u = u[len(prefix):]
            break
    u = u.split("?")[0].split("#")[0].split("/")[0]
    return u[4:] if u.startswith("www.") else u


def is_aggregator(host: str) -> bool:
    return any(host == a or host.endswith("." + a) for a in AGGREGATORS)


def tokens(name: str) -> list[str]:
    """Identity-carrying words of a company name, longest first."""
    words = [w for w in match_key(name).split()
             if len(w) >= 3 and w not in STOPWORDS]
    return sorted(words, key=len, reverse=True)


def looks_like_a_listing(url: str, name: str) -> bool:
    """
    True when the company name appears in the URL PATH but not the domain.

    This is the structural signature of a directory entry. A company's own
    site carries its name in the hostname (hoefer.de); a directory carries it
    in the path (lieferanten.de/lieferant-653-hoefer). The distinction catches
    the long tail of German B2B directories that no blocklist can enumerate,
    and it was found by inspecting live results rather than assumed: three of
    the first ten searches returned directories that a name-in-the-page check
    happily accepted, because a directory naturally mentions every company it
    lists.
    """
    parsed = urlparse(url)
    if domain_resembles(parsed.netloc, name):
        return False
    path = parsed.path.lower().replace("-", "").replace("_", "")
    return any(len(t) >= 4 and t.replace(" ", "") in path for t in tokens(name))


def domain_resembles(host: str, name: str) -> str:
    """
    Return the token that the domain matches, or "" if none does.

    "actain engineering GmbH" -> actain.de matches on "actain". Requiring a
    token of at least four characters keeps "ane.de" from matching every
    company whose name contains a three-letter fragment.
    """
    stem = host.split(".")[0].replace("-", "")
    for tok in tokens(name):
        if len(tok) >= 4 and tok.replace(" ", "") in stem:
            return tok
    return ""


def page_mentions(url: str, name: str, session: requests.Session) -> str:
    """Fetch the candidate and return the token it mentions, or ""."""
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return ""
        resp.encoding = resp.apparent_encoding or resp.encoding
        text = re.sub(r"<[^>]+>", " ", resp.text[:400_000]).lower()
        text = re.sub(r"\s+", " ", text)
    except requests.RequestException:
        return ""
    for tok in tokens(name):
        if len(tok) >= 4 and tok in text:
            return tok
    return ""


def load_queue(limit: int | None) -> list[dict]:
    if not IN_CSV.exists():
        raise SystemExit(f"run link_coverage.py first: {IN_CSV} is missing")
    with open(IN_CSV, encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh) if r["route"] == "none"]
    return rows[:limit] if limit else rows


def load_done() -> dict[str, dict]:
    if not OUT_CSV.exists():
        return {}
    with open(OUT_CSV, encoding="utf-8-sig") as fh:
        return {f"{r['url_id']}|{r['company']}": r for r in csv.DictReader(fh)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip the page-fetch check; domain evidence only")
    ap.add_argument("--max-results", type=int, default=5)
    ap.add_argument("--delay", type=float, default=2.0,
                    help="seconds between searches, to stay polite")
    args = ap.parse_args()

    from ddgs import DDGS

    queue = load_queue(args.limit)
    done = load_done()
    todo = [r for r in queue if f"{r['url_id']}|{r['company']}" not in done]
    print(f"  {len(queue)} companies without a link, {len(done)} already "
          f"searched, {len(todo)} to do\n")

    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT,
                            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})

    out = list(done.values())
    counts = {"verified": 0, "domain_match": 0, "page_only": 0,
              "unverified": 0, "no_result": 0}

    for i, r in enumerate(todo, start=1):
        company = r["company"].strip()
        query = f"{company} Firma Webseite"
        found, status, evidence, seen = "", "no_result", "", 0

        try:
            with DDGS() as ddgs:
                hits = list(ddgs.text(query, region="de-de",
                                      max_results=args.max_results))
        except Exception as exc:
            hits = []
            evidence = f"search failed: {type(exc).__name__}"

        for hit in hits:
            url = (hit.get("href") or hit.get("url") or "").strip()
            if not url.startswith("http"):
                continue
            host = host_of(url)
            if is_aggregator(host):
                continue
            seen += 1

            tok = domain_resembles(host, company)
            if tok:
                found, status, evidence = url, "domain_match", f"domain~{tok}"
                if not args.no_fetch:
                    mention = page_mentions(url, company, session)
                    if mention:
                        status, evidence = "verified", f"domain~{tok}, page~{mention}"
                break

            if looks_like_a_listing(url, company):
                continue        # a directory entry, not the company's site

            # The page names the company but the domain does not. That is
            # weaker evidence and is reported as its own category rather than
            # counted as confirmed, because it is exactly what a directory
            # looks like. Kept because a company trading under a different
            # brand also lands here.
            if not args.no_fetch:
                mention = page_mentions(url, company, session)
                if mention and not found:
                    found, status, evidence = url, "page_only", f"page~{mention}"
                    continue
            if not found:
                found, status = url, "unverified"

        counts[status] = counts.get(status, 0) + 1
        out.append({
            "url_id": r["url_id"], "org_name": r["org_name"],
            "company": company, "query": query,
            "found_url": found if status != "unverified" else "",
            "status": status, "evidence": evidence, "candidates_seen": seen,
        })

        mark = {"verified": "  ", "domain_match": "~ ", "page_only": "? ",
                "unverified": "? ", "no_result": "! "}[status]
        print(f"{mark}[{i:>4}/{len(todo)}] {company[:34]:<36}"
              f"{(found or '-')[:40]:<42}{evidence[:26]}")

        # Written every iteration so an interrupted run loses nothing.
        with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(out)
        time.sleep(args.delay)

    n = len(out) or 1
    ok = sum(1 for r in out if r["status"] in ("verified", "domain_match"))
    print(f"\n  {len(out)} companies searched")
    for k in ("verified", "domain_match", "page_only", "unverified", "no_result"):
        c = sum(1 for r in out if r["status"] == k)
        print(f"    {k:<14}{c:>5}  ({c/n:.0%})")
    weak = sum(1 for r in out if r["status"] == "page_only")
    print(f"\n  confirmed (domain evidence): {ok} of {n} ({ok/n:.0%})")
    print(f"  weak (page mentions the name but the domain does not): {weak}")
    print("  weak results are NOT safe to load into the database unchecked; "
          "they are usually directory entries.")
    print(f"  -> {OUT_CSV}")


if __name__ == "__main__":
    main()
