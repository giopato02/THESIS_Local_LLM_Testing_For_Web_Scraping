"""
Stage 2: work out how each member company's website can be reached.

This runs before any model and does not use one. For every company in the
ground truth it looks at the directory page and decides which of three routes
applies:

    website     the page links straight to the company's own site.
                Stage 1 (the model) can read it off the page in one pass.

    profile     the page links the company to a profile page on the
                association's own site. The website is one more fetch away.
                This is the stage 3 queue.

    none        the company name is plain text with no link of any kind.
                Only a web search can find it. This is the stage 4 queue.

The split is decided by comparing hostnames, which Python does exactly, so
spending model tokens on it would be slower and less accurate.

Because it runs against the hand-labelled ground truth rather than model
output, the result is a CEILING: the best any model could possibly do at
stage 1, and the true size of the stage 3 and 4 queues. Comparing a model's
actual website coverage against this number separates "the model missed it"
from "it was never on the page".

Run:  .venv/bin/python link_coverage.py
      .venv/bin/python link_coverage.py --page 050
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

import cleaner
import config
import fetcher

# The marker annotate_links() writes into the cleaned text: Name <https://url>
import re
URL_IN_TEXT = re.compile(r"<(https?://[^>\s]+)>")

# A link written without a scheme, e.g. href="www.meotec.eu". Browsers treat
# it as a relative path, and so does urljoin, gluing it onto the association's
# own domain. On a member directory the intent is almost always the company's
# own site, so it is recovered rather than followed into a 404.
BARE_DOMAIN = re.compile(r"^(?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+(?:/|$)",
                         re.IGNORECASE)


def host_of(url: str) -> str:
    """Bare hostname, for deciding whether two entries claim the same site."""
    u = url.strip().lower()
    for prefix in ("https://", "http://", "//"):
        if u.startswith(prefix):
            u = u[len(prefix):]
            break
    u = u.split("?")[0].split("#")[0].split("/")[0]
    return u[4:] if u.startswith("www.") else u


def resolve(href: str, base: str) -> str:
    """Turn one href into an absolute URL, handling the scheme-less case."""
    href = href.strip()
    if BARE_DOMAIN.match(href) and not href.startswith(("/", "?", "#")):
        return "https://" + href
    return urljoin(base, href)


OUT_CSV = config.RESULTS_DIR / "link_coverage.csv"

# Anchor text shorter than this is navigation ("Home", "Kontakt"), not a
# company name. Measured: no ground-truth member name normalises shorter.
MIN_KEY_LEN = 5

# Link labels that identify the KIND of link rather than the company behind
# it. SPECTARIS labels every member's website "Web"; NMWP puts the company
# name in the logo's alt text. Only the second kind speaks for an address, so
# only the second kind may block a positional pairing. Getting this wrong in
# either direction is costly: treating "Web" as a company name discards every
# positional pairing on SPECTARIS and drops the corpus ceiling from 63% to 8%,
# while ignoring short real names such as AMAC lets a positional guess
# reassign an address that the markup had already spoken for.
GENERIC_LABELS = {
    "web", "website", "webseite", "homepage", "home", "link", "url",
    "zur website", "zur webseite", "website besuchen", "mehr", "mehr erfahren",
    "more", "hier", "info", "infos", "details", "profil", "kontakt",
    "email", "mail", "seite", "www", "internet",
}


def match_key(name: str) -> str:
    """Same normalisation the scorer uses, so 'found' means the same thing."""
    import benchmark
    return benchmark.match_key(name)


def same_org(host_a: str, host_b: str) -> bool:
    """
    True when two hostnames belong to the same organisation.

    A plain equality test is not enough: one association serves its directory
    from verein.nmwp.nrw and its member profiles from portal.nmwp.de. Those
    are different hostnames, one organisation, and treating the profile pages
    as company websites would be wrong. Comparing the meaningful name parts
    catches it.
    """
    a = host_a.replace("www.", "").lower().strip(".")
    b = host_b.replace("www.", "").lower().strip(".")
    if a == b:
        return True

    # Same registrable domain, e.g. a.example.com and b.example.com. Checked
    # before the label heuristic because that heuristic drops labels shorter
    # than four characters, so a site on a short domain such as vda.de or
    # aif.de produced an empty label set and failed to recognise its OWN
    # links. Measured: 4 of the 73 corpus pages hit that case.
    pa, pb = a.split("."), b.split(".")
    if len(pa) >= 2 and len(pb) >= 2 and pa[-2:] == pb[-2:]:
        return True

    def labels(parts: list[str]) -> set[str]:
        return {p for p in parts
                if len(p) >= 4 and p not in {"com", "net", "org", "info",
                                             "portal", "verein", "www"}}
    return bool(labels(pa) & labels(pb))


def index_profile_links(html: str, page_url: str) -> dict[str, str]:
    """
    Return {company name -> profile page on the association's own site}.

    Profile links are reliably matched by the link's clickable text, because a
    directory that links each member to its own detail page uses the company
    name as the link. Where the entry is a logo instead, the name is in the
    image's alt attribute, so both are read.
    """
    soup = BeautifulSoup(html, "lxml")
    own = urlparse(page_url).netloc
    profile: dict[str, str] = {}

    # A <base> tag redefines what relative links resolve against. Life Science
    # Nord serves its member list from /de/mitglieder/member-companies.html but
    # declares <base href="https://www.lifesciencenord.de/">, so its relative
    # hrefs are written as "de/mitglieder/...". Resolving those against the
    # page URL instead produces /de/mitglieder/de/mitglieder/... and every one
    # of its 51 profile pages 404s.
    base_tag = soup.find("base", href=True)
    base = urljoin(page_url, base_tag["href"].strip()) if base_tag else page_url

    for a in soup.find_all("a", href=True):
        href = resolve(a["href"], base)
        if not href.startswith("http"):
            continue
        if not same_org(own, urlparse(href).netloc):
            continue

        text = " ".join(a.get_text(separator=" ").split())
        if not text:
            img = a.find("img")
            if img:
                text = (img.get("alt") or img.get("title") or "").strip()
        key = match_key(text)
        if len(key) >= MIN_KEY_LEN:
            profile.setdefault(key, href)

    return profile


def index_websites_from_markup(html: str, page_url: str) -> dict[str, str]:
    """
    Return {company name -> its own website} taken from the markup itself.

    Where a directory is a grid of logos, the HTML states the pairing outright:

        <a href="http://www.aetztechnik-herz.de/">
          <img alt="Ätztechnik Herz GmbH & Co. KG">
        </a>

    Returns (pairings, every labelled outbound href). The second is wider than
    the first: a link whose label is too short to use as a key is still spoken
    for by that label, and must not be reassigned positionally.

    The pairing is authoritative and must be preferred over anything
    positional. A
    page can carry two separate listings, a text list and a logo grid, and
    walking down from a name in one of them lands on a URL belonging to the
    other. Measured on NMWP.NRW: positional matching alone paired "Aixtron SE"
    with Effing's website and scored the model 0 correct out of 81, when the
    model had in fact reproduced the markup's own pairings correctly.
    """
    soup = BeautifulSoup(html, "lxml")
    own = urlparse(page_url).netloc
    base_tag = soup.find("base", href=True)
    base = urljoin(page_url, base_tag["href"].strip()) if base_tag else page_url

    found: dict[str, str] = {}
    labelled: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = resolve(a["href"], base)
        if not href.startswith("http") or same_org(own, urlparse(href).netloc):
            continue
        text = " ".join(a.get_text(separator=" ").split())
        if not text:
            img = a.find("img")
            if img:
                text = (img.get("alt") or img.get("title") or "").strip()
        key = match_key(text)
        if not key or key in GENERIC_LABELS:
            continue
        # A link labelled with a company name is spoken for by that company,
        # even when the name is too short to use as a lookup key. Short real
        # names exist -- AMAC, AMO, CTC, DLR -- and excluding them from the
        # claimed set let a positional guess reassign their address to a
        # different company. That is how "Aixtron SE" acquired Effing's site.
        labelled.add(href)
        if len(key) >= MIN_KEY_LEN:
            found.setdefault(key, href)
    return found, labelled


def index_websites(page_text: str, names: list[str]) -> dict[str, str]:
    """
    Return {company name -> its own website}, matched BY POSITION.

    Matching on the link's clickable text does not work for company websites.
    The commonest layout in this corpus prints:

        2mag AG
        80992 Munchen
        Schragenhofstr. 35
        Web <http://www.2mag.de>

    where the link's text is "Web". The company name and its address are
    ordinary text several lines above. Nothing connects them except the order
    they appear in, which is exactly why this job needs a model rather than a
    lookup, and why preserving links improved NAME extraction too: the URL is
    the only marker of where one member's block ends (section 3.11i).

    The same positional logic is applied here, so the number produced is the
    ceiling a model could reach rather than an artefact of how links happen to
    be labelled. A company's block runs from its own line to the line before
    the next company, capped at MAX_BLOCK_LINES for pages that list a member
    once and then discuss it at length.
    """
    MAX_BLOCK_LINES = 8
    lines = page_text.split("\n")
    wanted = {match_key(n) for n in names if match_key(n)}

    # The URL marker must come off before the line is matched against a
    # company name, or the two conventions in this corpus behave differently
    # for no good reason. Some directories print
    #     A.T. Kearney GmbH <https://www.kearney.com>
    # on one line, others put the link three lines below the name. Stripping
    # the marker makes the same code handle both.
    bare = [URL_IN_TEXT.sub("", ln).strip() for ln in lines]

    # Where each company's block starts. A name can appear more than once;
    # the first occurrence is the listing, later ones are usually prose.
    starts: list[tuple[int, str]] = []
    seen: set[str] = set()
    for i, line in enumerate(bare):
        key = match_key(line)
        if key in wanted and key not in seen:
            seen.add(key)
            starts.append((i, key))
    starts.sort()

    found: dict[str, str] = {}
    for pos, (start, key) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        end = min(end, start + MAX_BLOCK_LINES)
        for line in lines[start:end]:
            m = URL_IN_TEXT.search(line)
            if m:
                found[key] = m.group(1)
                break
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=None, help="restrict to one url_id")
    args = ap.parse_args()

    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}

    rows = []
    for gt_file in sorted(config.GROUND_TRUTH_DIR.glob("*.json")):
        uid = gt_file.stem
        if args.page and uid != args.page:
            continue
        row = urls.get(uid)
        if not row:
            continue
        cache = fetcher.cache_path(row["url"])
        if not cache.exists():
            print(f"  ! no cached HTML for {uid}, skipping")
            continue

        html = cache.read_text(encoding="utf-8", errors="ignore")
        companies = json.loads(gt_file.read_text(encoding="utf-8"))["companies"]

        profile = index_profile_links(html, row["url"])
        page = cleaner.process(html, row["url"])

        # Markup first, position second. Where an anchor names the company it
        # points at, the page has stated the pairing and there is nothing to
        # infer. Positional matching only fills the gap left by anchors
        # labelled "Web", "Zur Website" and the like.
        #
        # A website belongs to ONE company, so a positional guess at an address
        # the markup has already claimed is wrong by construction. Merging the
        # two maps without enforcing that left both entries alive under
        # different company names: on NMWP.NRW, 10 of 36 addresses were claimed
        # twice, once correctly from the markup and once by a positional guess
        # that had drifted into the wrong listing.
        markup, labelled = index_websites_from_markup(html, row["url"])
        claimed = {host_of(u) for u in labelled}
        website = {k: v for k, v in index_websites(page.text, companies).items()
                   if host_of(v) not in claimed}
        website.update(markup)

        for name in companies:
            key = match_key(name)
            if key in website:
                route, target = "website", website[key]
            elif key in profile:
                route, target = "profile", profile[key]
            else:
                route, target = "none", ""
            rows.append({
                "url_id": uid,
                "org_name": row["org_name"],
                "company": name,
                "route": route,
                "target": target,
            })

    if not rows:
        raise SystemExit("no ground-truth pages matched")

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- report ----------------------------------------------------------
    per_page: dict[str, Counter] = {}
    for r in rows:
        per_page.setdefault(r["url_id"], Counter())[r["route"]] += 1

    print(f"\n{'page':<6}{'organisation':<30}{'total':>7}"
          f"{'website':>9}{'profile':>9}{'none':>7}")
    print("-" * 68)
    for uid in sorted(per_page):
        c = per_page[uid]
        org = next(r["org_name"] for r in rows if r["url_id"] == uid)
        print(f"{uid:<6}{org[:28]:<30}{sum(c.values()):>7}"
              f"{c['website']:>9}{c['profile']:>9}{c['none']:>7}")

    total = Counter(r["route"] for r in rows)
    n = len(rows)
    print("-" * 68)
    print(f"{'TOTAL':<36}{n:>7}{total['website']:>9}"
          f"{total['profile']:>9}{total['none']:>7}")
    print(f"{'':<36}{'':>7}{total['website']/n:>8.0%}"
          f"{total['profile']/n:>9.0%}{total['none']/n:>7.0%}")

    print(f"\n  stage 1 ceiling  {total['website']:>4} companies "
          f"({total['website']/n:.0%}) have a website printed on the page")
    print(f"  stage 3 queue    {total['profile']:>4} companies "
          f"({total['profile']/n:.0%}) need one profile-page fetch")
    print(f"  stage 4 queue    {total['none']:>4} companies "
          f"({total['none']/n:.0%}) need a web search")
    print(f"\n  -> {OUT_CSV}")


if __name__ == "__main__":
    main()
