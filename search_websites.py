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
import os
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

# Mailboxes hosted by a provider. The domain of one of these says where the
# company reads its mail, not where its website is, so it is not evidence.
FREEMAIL = {
    "gmail.com", "googlemail.com", "web.de", "gmx.de", "gmx.net", "gmx.at",
    "t-online.de", "outlook.com", "outlook.de", "hotmail.com", "hotmail.de",
    "live.com", "live.de", "yahoo.com", "yahoo.de", "aol.com", "icloud.me",
    "me.com", "mail.de", "posteo.de", "mailbox.org", "freenet.de",
    "arcor.de", "online.de", "gmx.com", "protonmail.com", "proton.me",
}

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


# Directory brands that run one domain per country. Listing every TLD is a
# losing game: `cylex.de` was blocked and `cylex.at` still came back as the
# top result for A. Höfer GmbH. These are matched on the registrable label
# alone, so every country variant is covered at once.
#
# Only brands that are unmistakably directories belong here, because matching
# by label ignores the TLD and would otherwise block a real company that
# happens to share the word.
AGGREGATOR_BRANDS = {
    "cylex", "europages", "yelp", "kompass", "northdata", "gelbeseiten",
    "dasoertliche", "meinestadt", "firmenwissen", "companyhouse",
    "moneyhouse", "opencorporates", "dun-bradstreet", "implisense",
    "wlw", "linkedin", "xing", "facebook", "instagram", "wikipedia",
    # Seen live on the production run: "form & function GmbH" returned
    # kompany.de/p/de/hrb91363, a commercial register entry. It was left
    # unconfirmed, so it would not have shipped, but it cost a fetch.
    "kompany", "hokify", "firmendb", "yellowmap", "branchenbuch",
}


# Suffixes that are two labels long, where the name sits one further left:
# "europages.co.uk" is europages, not "co".
COMPOUND_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au",
    "co.nz", "co.za", "co.jp", "or.jp", "com.br", "com.mx", "com.tr",
    "com.cn", "com.hk", "com.sg", "co.in", "co.kr", "com.pl",
}


def registrable_label(host: str) -> str:
    """
    The name part of a hostname, ignoring subdomains and the suffix.

        web2.cylex.de      -> cylex
        cylex.at           -> cylex
        europages.co.uk    -> europages
    """
    parts = [p for p in host.lower().split(".") if p]
    if len(parts) < 2:
        return ""
    if len(parts) >= 3 and ".".join(parts[-2:]) in COMPOUND_SUFFIXES:
        return parts[-3]
    return parts[-2]


def is_aggregator(host: str) -> bool:
    if any(host == a or host.endswith("." + a) for a in AGGREGATORS):
        return True
    return registrable_label(host) in AGGREGATOR_BRANDS


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


def email_domain(email: str) -> str:
    """
    The host part of an address, or "" when it says nothing about a website.

    A company's own address is the strongest single piece of evidence there
    is: `info@5microns.de` states the website outright, with no search and no
    guessing. A provider mailbox states only who carries the mail.
    """
    e = (email or "").strip().lower()
    if "@" not in e:
        return ""
    host = e.rsplit("@", 1)[1].strip().strip(".")
    if not host or "." not in host or host in FREEMAIL:
        return ""
    return host[4:] if host.startswith("www.") else host


def phone_tail(phone: str) -> str:
    """
    The distinctive digits of a phone number, for comparing across formats.

    The same number is printed as "+49 341 253966-0", "0341/253966-0" and
    "0049 341 2539660". Country code, leading zero and every separator vary,
    so only the last digits can be compared, and there have to be enough of
    them that two unrelated numbers do not collide.
    """
    digits = re.sub(r"\D", "", phone or "")
    return digits[-7:] if len(digits) >= 8 else ""


def load_records(paths: list) -> dict:
    """
    Contact details per company, keyed by (url_id, normalised name).

    Stage 4 handles the companies a directory names and does not link, so the
    only thing it starts with is a name. Anything else the pipeline learned
    about that company (a postcode, a phone number, an address) turns a guess
    into a check, which is the whole difficulty of this stage: a search always
    returns something, and everything it returns looks plausible.
    """
    out: dict = {}
    for path in paths:
        if not path or not os.path.exists(path):
            continue
        with open(path, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                company = (r.get("company") or r.get("name") or "").strip()
                if not company:
                    continue
                key = (r.get("url_id", ""), match_key(company))
                rec = out.setdefault(key, {})
                # "website" is here so load_queue can skip a company stage 1
                # already found an address for; the rest are evidence.
                for f in ("website", "street", "postcode", "city",
                          "phone", "email"):
                    v = (r.get(f) or "").strip()
                    if v and not rec.get(f):
                        rec[f] = v
    return out


def page_evidence(url: str, name: str, rec: dict,
                  session: requests.Session) -> set:
    """
    Fetch the candidate once and report every kind of evidence it carries.

    One download answers several questions, so they are all asked here rather
    than in separate passes. The kinds are deliberately unequal in strength,
    and `decide` is where that is weighed:

      name      the company is mentioned. A directory mentions every company
                it lists, so on its own this is the weakest signal there is.
      postcode  the company's postcode appears. Shared by a town, but a town
                and a name together are unlikely to coincide.
      phone     the company's number appears. Close to unique to one business.
      email     the company's exact address appears. Decisive.
    """
    found = set()
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return found
        resp.encoding = resp.apparent_encoding or resp.encoding
        text = re.sub(r"<[^>]+>", " ", resp.text[:400_000]).lower()
        text = re.sub(r"\s+", " ", text)
        digits = re.sub(r"\D", "", text)
    except requests.RequestException:
        return found

    for tok in tokens(name):
        if len(tok) >= 4 and tok in text:
            found.add("name")
            break

    postcode = (rec.get("postcode") or "").strip()
    if len(postcode) == 5 and postcode.isdigit() and postcode in digits:
        found.add("postcode")

    tail = phone_tail(rec.get("phone", ""))
    if tail and tail in digits:
        found.add("phone")

    mail = (rec.get("email") or "").strip().lower()
    if mail and "@" in mail and mail in text:
        found.add("email")

    return found


# What each kind of evidence is worth. Set so that no single weak signal can
# confirm a result on its own, and any strong one can:
#   name alone (1)                  -> page_only, reported but not confirmed
#   domain resembles the name (2)   -> domain_match
#   name + postcode (3)             -> verified
#   phone (3) or email (4)          -> verified by itself
WEIGHTS = {"domain": 2, "name": 1, "postcode": 2, "phone": 3, "email": 4}
CONFIRMED = 3


def decide(evidence: set) -> tuple:
    """(status, evidence string) from the set of things that matched."""
    score = sum(WEIGHTS.get(e, 0) for e in evidence)
    detail = "+".join(sorted(evidence)) + f"={score}" if evidence else ""
    if score >= CONFIRMED:
        return "verified", detail
    if "domain" in evidence:
        return "domain_match", detail
    if evidence:
        return "page_only", detail
    return "unverified", ""


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


def load_profile_results() -> dict:
    """
    {(url_id, company key) -> True} for companies stage 3 gave a website.

    Returns None when stage 3 has not run, so the queue falls back to the
    route alone rather than silently treating every profile company as
    unserved and searching for all of them.
    """
    path = config.RESULTS_DIR / "profile_records.csv"
    if not path.exists():
        return None
    out = {}
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if (r.get("company_url") or "").strip():
                out[(r.get("url_id", ""), match_key(r.get("company", "")))] = True
    return out


def load_queue(limit: int | None, records: dict = None) -> list[dict]:
    """
    The companies that genuinely need a search.

    The route comes from `link_coverage.py`, which pairs a company with the
    address printed beside it positionally. That pairing is conservative and
    misses a great deal: on the production corpus it found 4,769 websites
    where the model found 9,360, and of the model's extra ones **3,682 of
    3,683 hostnames are present in the page**, a 0.03% invention rate
    matching the research corpus.

    So a company routed "none" may still have a perfectly good website that
    stage 1 read and the pairing did not. Searching for it wastes 5 seconds
    and, worse, risks returning a different and wrong answer for a company we
    already had right. Those are skipped: 3,682 of 8,452 on the production
    run, which is 5 hours and 3,682 chances to be wrong.
    """
    if not IN_CSV.exists():
        raise SystemExit(f"run link_coverage.py first: {IN_CSV} is missing")
    with open(IN_CSV, encoding="utf-8-sig") as fh:
        all_rows = list(csv.DictReader(fh))
    rows = [r for r in all_rows if r["route"] == "none"]

    # Plus anyone the profile stage was routed to but could not serve. This
    # is the backstop for every way a "profile link" turns out not to be a
    # profile page, and there are more ways than can be predicted from a URL:
    #
    #   the Leasingverband points all 134 members at one page with different
    #   #fragments, which a URL rule does catch
    #   Composites United points its 582 members at 582 distinct paths that
    #   all return the same page, which no URL rule can catch
    #
    # Both were skipped by stage 3 for exceeding its word limit and never
    # queued here, because their route said "profile". 716 companies, 4.4% of
    # the corpus, served by nothing. Asking "did stage 3 actually produce
    # something?" needs no cleverness and cannot miss a case.
    served = load_profile_results()
    if served is not None:
        unserved = [r for r in all_rows
                    if r["route"] == "profile"
                    and not served.get((r["url_id"], match_key(r["company"])))]
        if unserved:
            print(f"  {len(unserved):,} were routed to a profile page that "
                  f"produced nothing, searching those too")
            rows += unserved

    if records:
        keep, known = [], 0
        for r in rows:
            rec = records.get((r["url_id"], match_key(r["company"])), {})
            if (rec.get("website") or "").strip():
                known += 1
                continue
            keep.append(r)
        if known:
            print(f"  {known:,} already have a website from the directory page, "
                  f"skipping those")
        rows = keep
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
    ap.add_argument("--records", nargs="*",
                    default=[str(config.RESULTS_DIR / "profile_records.csv")],
                    help="CSVs of company contact details, used as evidence "
                         "and for the email shortcut. Missing files are "
                         "ignored, and without any the stage still runs on "
                         "name evidence alone")
    args = ap.parse_args()

    # The library was renamed from `duckduckgo_search` to `ddgs`, and the new
    # name requires Python 3.9. The GPU node runs 3.8.10, where only the old
    # name installs, so accept either rather than pinning the environment to
    # one of them. Same class, same `.text()` call.
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            raise SystemExit(
                "  no search library installed. On Python 3.9+:\n"
                "      .venv/bin/pip install ddgs\n"
                "  on Python 3.8 (this GPU node):\n"
                "      .venv/bin/pip install 'duckduckgo-search<6'")

    # Records first: the queue depends on them, because a company stage 1
    # already found a website for does not need searching at all.
    records = load_records(args.records)
    print(f"  contact details available for {len(records):,} companies")

    queue = load_queue(args.limit, records)
    done = load_done()
    todo = [r for r in queue if f"{r['url_id']}|{r['company']}" not in done]
    print(f"  {len(queue):,} companies need a search, {len(done):,} already "
          f"done, {len(todo):,} to do\n")

    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT,
                            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})

    out = list(done.values())
    counts = {"email_domain": 0, "verified": 0, "domain_match": 0,
              "page_only": 0, "unverified": 0, "no_result": 0}

    for i, r in enumerate(todo, start=1):
        company = r["company"].strip()
        query = f"{company} Firma Webseite"
        found, status, evidence, seen = "", "no_result", "", 0
        rec = records.get((r["url_id"], match_key(company)), {})

        # The company's own email address states its website. Deriving beats
        # searching: no query, no candidate ranking, nothing to verify. Only
        # skipped when the mailbox is a provider's, or when the address
        # belongs to the association rather than the member.
        derived = email_domain(rec.get("email", ""))
        if derived and not is_aggregator(derived):
            found = f"https://{derived}"
            status, evidence = "email_domain", f"email={rec['email']}"
            counts[status] += 1
            out.append({
                "url_id": r["url_id"], "org_name": r["org_name"],
                "company": company, "query": "", "found_url": found,
                "status": status, "evidence": evidence, "candidates_seen": 0,
            })
            print(f"@ [{i:>4}/{len(todo)}] {company[:34]:<36}"
                  f"{found[:40]:<42}{evidence[:26]}")
            with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.DictWriter(fh, fieldnames=FIELDS)
                w.writeheader()
                w.writerows(out)
            continue

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

            # A directory entry carries the name in the path, not the domain.
            # Only skip when the domain gives us nothing, since a real company
            # site whose name is also in its path must not be thrown away.
            if not tok and looks_like_a_listing(url, company):
                continue

            # Gather every kind of evidence from one download, then weigh it
            # all together. Previously each signal was judged on its own, so a
            # postcode and a phone number could not combine into a confirmed
            # result, and a domain match short-circuited before anything else
            # was even looked at.
            kinds = set()
            if tok:
                kinds.add("domain")
            if rec.get("email") and email_domain(rec["email"]) == host:
                kinds.add("email")
            if not args.no_fetch:
                kinds |= page_evidence(url, company, rec, session)

            candidate_status, detail = decide(kinds)
            if tok and detail:
                detail = f"domain~{tok}, {detail}"

            # Keep the best candidate, not the first: a confirmed result later
            # in the list beats an unconfirmed one at the top.
            rank = {"verified": 3, "domain_match": 2, "page_only": 1,
                    "unverified": 0}
            if not found or rank[candidate_status] > rank.get(status, -1):
                found, status, evidence = url, candidate_status, detail
            if status == "verified":
                break

        counts[status] = counts.get(status, 0) + 1
        out.append({
            "url_id": r["url_id"], "org_name": r["org_name"],
            "company": company, "query": query,
            "found_url": found if status != "unverified" else "",
            "status": status, "evidence": evidence, "candidates_seen": seen,
        })

        mark = {"email_domain": "@ ", "verified": "  ", "domain_match": "~ ",
                "page_only": "? ", "unverified": "? ", "no_result": "! "}[status]
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
