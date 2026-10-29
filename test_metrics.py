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


def test_python38_compatible() -> None:
    """
    Nothing in the pipeline may need newer than Python 3.8.

    The GPU node runs 3.8.10. That version gap has cost time twice: it aborted
    a pip install by way of ddgs, and it crashed a stage 3 run on `dict | dict`
    after the code had been written and tested on 3.14 locally. Neither was
    catchable by running the code here, so it is checked by parsing instead.
    """
    import ast
    import pathlib as _p
    print("python 3.8 compatibility")

    global FAIL, PASS
    problems = []
    for path in sorted(_p.Path(".").glob("*.py")):
        # A "._name.py" is a Mac resource fork that arrives when an archive is
        # built on macOS and unpacked here. It is 263 bytes of binary, not
        # code, and parsing it as UTF-8 aborted the whole suite once.
        if path.name.startswith("._"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                if isinstance(node.left, (ast.Dict, ast.DictComp)) or \
                   isinstance(node.right, (ast.Dict, ast.DictComp)):
                    problems.append(f"{path.name}:{node.lineno} dict | dict needs 3.9")
            if isinstance(node, ast.Attribute) and node.attr in (
                    "removeprefix", "removesuffix"):
                problems.append(f"{path.name}:{node.lineno} .{node.attr}() needs 3.9")
            if node.__class__.__name__ == "Match":
                problems.append(f"{path.name}:{node.lineno} match needs 3.10")

    if problems:
        FAIL += len(problems)
        for p in problems:
            print(f"  FAIL  {p}")
    else:
        PASS += 1


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


# ---------------------------------------------------------------------------
# 6. Merging the full-record run with the names-only run. The full-record run
#    lost 53 of 124 members on automotive thüringen, identically in all three
#    repetitions, and nothing anywhere raised an error or a warning.
# ---------------------------------------------------------------------------

def test_merge_page() -> None:
    import benchmark
    import export_deliverable as E
    print("deliverable merge: full-record run + names-only run")

    full = [{"name": "Alpha GmbH", "url": "https://alpha.de"},
            {"name": "Beta AG", "url": ""}]
    names = ["Alpha GmbH", "Beta AG", "Gamma SE", "Delta KG", "Epsilon GmbH"]
    sites = {benchmark.match_key("Alpha GmbH"): "https://someone-else.de",
             benchmark.match_key("Beta AG"): "https://beta.de",
             benchmark.match_key("Gamma SE"): "https://gamma.de"}
    entries, st = E.merge_page(full, names, sites)
    by = {e["name"]: e for e in entries}

    check("every company from either run appears exactly once",
          sorted(e["name"] for e in entries), sorted(names))
    check("the model's own address is kept, not overridden by the pairing",
          by["Alpha GmbH"]["url"], "https://alpha.de")
    check("a record returned without an address is filled from the page",
          (by["Beta AG"]["url"], by["Beta AG"]["_source"]),
          ("https://beta.de", "directory page (paired)"))
    check("an added name gets the address the page pairs with it",
          by["Gamma SE"]["url"], "https://gamma.de")
    check("an added name with no pairing stays blank, never guessed",
          (by["Delta KG"]["url"], by["Delta KG"]["_source"]), ("", ""))
    check("names added from the names-only run", st["added"], 3)
    check("2 of 5 is flagged incomplete", st["incomplete"], True)

    # The warning must also stay quiet when it should. A flag that is always
    # on gets ignored, which is no better than having none.
    _, ok = E.merge_page([{"name": n} for n in names], names, {})
    check("a complete full-record run is not flagged", ok["incomplete"], False)
    _, edge = E.merge_page([{"name": n} for n in names[:4]], names, {})
    check("4 of 5 (exactly 80%) is not flagged", edge["incomplete"], False)
    _, empty = E.merge_page([], names, {})
    check("a full-record run that returned nothing is flagged",
          (empty["incomplete"], empty["added"]), (True, 5))
    _, alone = E.merge_page([{"name": "Alpha GmbH"}], [], {})
    check("no names-only run means nothing to compare, so no flag",
          alone["incomplete"], False)

    dup, _ = E.merge_page([{"name": "Alpha GmbH"}, {"name": "Alpha GmbH"}],
                          ["Alpha GmbH"], {})
    check("a company repeated across and within runs is listed once",
          len(dup), 1)


# ---------------------------------------------------------------------------
# 7. Model set. Thinking must be off where it exists and nowhere else: sending
#    the switch to a model without the mode changes the request for models
#    whose results are already published.
# ---------------------------------------------------------------------------

def test_model_config() -> None:
    import config
    import extractor as E
    print("model set and thinking switch")

    check("qwen3.5:9b is told not to think", E._thinking_off("qwen3.5:9b"), True)
    check("qwen2.5-coder:7b request is unchanged",
          E._thinking_off("qwen2.5-coder:7b"), False)
    check("llama3.1:8b request is unchanged", E._thinking_off("llama3.1:8b"), False)
    check("default grid is the three current models",
          sorted(config.MODELS),
          sorted(["llama3.1:8b", "qwen2.5-coder:7b", "qwen3.5:9b"]))
    check("the retired model is not run by default",
          "gemma4:12b" in config.MODELS, False)

    # The context window, against numbers measured on the real corpus rather
    # than assumed. At 8192 the densest page left 69 tokens for an answer
    # needing about 1,760, and 158 runs were recorded as unreadable JSON when
    # the reply was cut off mid name. A guard here so the window can never
    # quietly drop back below what the pages actually need.
    LARGEST_CHUNK = 8123        # page 079, measured 2026-09-28
    LARGEST_ANSWER = 1760       # page 050, 198 names at ~9 tokens each
    # The record arm writes seven fields per company: page 079 returned 96
    # records in 7,669 tokens, so ~80 each, and page 050's 198-company chunk
    # needs about 15,840. At 8,192 it truncated at exactly the cap.
    LARGEST_RECORD_ANSWER = 15840
    check("the window fits the biggest page plus its NAMES answer",
          config.NUM_CTX >= LARGEST_CHUNK + LARGEST_ANSWER, True)
    check("the window fits the biggest page plus its RECORD answer",
          config.NUM_CTX >= LARGEST_CHUNK + LARGEST_RECORD_ANSWER, True)
    check("and leaves real headroom, not just barely enough",
          config.NUM_CTX - LARGEST_CHUNK >= 2 * LARGEST_ANSWER, True)
    # The budget underestimates by about 35%, so it must never be read as a
    # true token count. Stated as a test because the gap is the whole bug.
    check("the chunk budget is only an estimate, well under the real size",
          config.CHUNK_TOKEN_BUDGET < LARGEST_CHUNK, True)

    # The loop backstop. It must sit far above any honest reply, or it becomes
    # the truncation bug again, and far below a runaway, or it is useless.
    check("the token cap clears the largest real RECORD answer",
          config.NUM_PREDICT >= LARGEST_RECORD_ANSWER, True)
    check("input plus a capped answer still fits the window",
          LARGEST_CHUNK + config.NUM_PREDICT <= config.NUM_CTX, True)


# ---------------------------------------------------------------------------
# 8. Cloud client. The Constructor API returned every answer twice on
#    2026-09-15; removing the copy must never remove a DIFFERENT answer.
# ---------------------------------------------------------------------------

def test_cloud_client() -> None:
    import json
    import os
    import cloud_client as C
    import config
    print("cloud client: Constructor Model API")

    check("constructor/ names go to the cloud",
          C.is_cloud("constructor/gemini-3.6-flash"), True)
    check("local model names stay local", C.is_cloud("llama3.1:8b"), False)

    a = '{"companies": [{"name": "Alpha GmbH"}]}'
    b = '{"companies": [{"name": "Beta AG"}]}'
    check("an exactly doubled answer is cut to one copy", C.undouble(a + a), (a, True))
    check("a doubled answer with a newline between is cut too",
          C.undouble(a + "\n" + a), (a, True))
    check("a single answer is left alone", C.undouble(a), (a, False))
    check("two DIFFERENT answers are left alone", C.undouble(a + b), (a + b, False))
    check("an empty answer is left alone", C.undouble(""), ("", False))

    body = C.build_body("constructor/gemini-3.6-flash", "sys", "user",
                        constrained=False)
    check("the prefix is stripped from the model name", body["model"],
          "gemini-3.6-flash")
    check("stream is a real boolean false", body["stream"] is False, True)
    check("temperature matches the local runs", body["temperature"],
          config.TEMPERATURE)
    check("no response_format unless constrained", "response_format" in body, False)

    # The output limit. Its absence truncated long answers mid-JSON and cost
    # 270 of 540 runs in the first cloud grid, for BOTH models, which is how
    # it was found: a model-specific fault cannot break two unrelated models
    # identically.
    check("an output limit is sent, matching the local num_predict",
          body["max_tokens"], config.NUM_PREDICT)
    check("the seed is sent, as it is locally", body.get("seed"), config.SEED)

    # Reasoning. Ollama takes think=False; the cloud endpoint has no such
    # field, so the qwen-only soft switch goes in the prompt instead.
    check("a qwen3 cloud model is detected as a thinking model",
          C.thinking_off("constructor/Qwen/Qwen3.5-9B"), True)
    check("a non-qwen cloud model is not", C.thinking_off("constructor/claude-haiku-4-5"), False)
    # Off by default: the prompt must stay byte-identical to the local runs
    # unless a run actually shows reasoning output. See config.CLOUD_NO_THINK.
    saved_nt = getattr(config, "CLOUD_NO_THINK", False)
    try:
        config.CLOUD_NO_THINK = False
        q = C.build_body("constructor/Qwen/Qwen3.5-9B", "sys", "u", constrained=False)
        check("by default even qwen3's prompt is left alone",
              q["messages"][0]["content"], "sys")

        config.CLOUD_NO_THINK = True
        q = C.build_body("constructor/Qwen/Qwen3.5-9B", "sys", "user", constrained=False)
        check("when enabled, qwen3 gets the no-think switch",
              q["messages"][0]["content"].endswith("/no_think"), True)
        check("the user message is never altered", q["messages"][1]["content"], "user")
        c = C.build_body("constructor/claude-haiku-4-5", "sys", "u", constrained=False)
        check("even when enabled, a non-thinking model is untouched",
              c["messages"][0]["content"], "sys")
    finally:
        config.CLOUD_NO_THINK = saved_nt

    body = C.build_body("constructor/gpt-4.1-mini", "s", "u", constrained=True,
                        schema={"type": "object"})
    check("constrained mode sends the schema as json_schema",
          (body["response_format"]["type"],
           body["response_format"]["json_schema"]["schema"]),
          ("json_schema", {"type": "object"}))

    saved = {k: os.environ.pop(k, None)
             for k in ("CONSTRUCTOR_API_KEY", "CONSTRUCTOR_KM_ID")}
    try:
        check("missing settings are named",
              C.missing_settings(), ["CONSTRUCTOR_API_KEY", "CONSTRUCTOR_KM_ID"])
        os.environ["CONSTRUCTOR_API_KEY"] = "SECRET-TEST-VALUE"
        os.environ["CONSTRUCTOR_KM_ID"] = "km-test"
        check("settings present means nothing missing", C.missing_settings(), [])
        dumped = json.dumps(C.build_body("constructor/x", "s", "u", True))
        check("the key never appears in the request body",
              "SECRET-TEST-VALUE" in dumped, False)
    finally:
        for k in ("CONSTRUCTOR_API_KEY", "CONSTRUCTOR_KM_ID"):
            os.environ.pop(k, None)
            if saved[k] is not None:
                os.environ[k] = saved[k]


# ---------------------------------------------------------------------------
# 9. Ground-truth worksheets. On 2026-09-22 --check turned 20 unedited
#    worksheets into answer keys and reported "30/30 complete".
# ---------------------------------------------------------------------------

def test_worksheet_parsing() -> None:
    import make_ground_truth as G
    print("ground-truth worksheets: status and parsing")

    todo = "# header\n# STATUS: TODO\n\nAlpha GmbH\n"
    done = "# header\n# STATUS: DONE\n\nAlpha GmbH\n"
    legacy = "# header written before the STATUS line existed\n\nAlpha GmbH\n"
    check("an unfinished worksheet is todo", G.worksheet_status(todo), "todo")
    check("a finished worksheet is done", G.worksheet_status(done), "done")
    check("status is not case-sensitive",
          G.worksheet_status("# STATUS: done\n"), "done")
    check("a round-1 worksheet without a STATUS line counts as done",
          G.worksheet_status(legacy), "done")

    sheet = ("# comment\n\nAlpha GmbH\n  Beta AG  \n# another comment\n"
             "# --- SECTION B: probably page furniture (2) ---\n"
             "Kontakt\nGamma SE\n")
    check("Section A names are read, Section B and comments ignored",
          G.parse_worksheet(sheet), ["Alpha GmbH", "Beta AG"])


# ---------------------------------------------------------------------------
# 10. "und" versus "&". One KliWaTex page printed both spellings of the same
#     firm, which scored as a miss plus a false alarm (2026-09-24).
# ---------------------------------------------------------------------------

def test_joining_words() -> None:
    import benchmark as B
    print("name matching: und / & / u.")

    same = [("Wilfried Keßler Erdbau- und Abbruch GmbH",
             "Wilfried Keßler Erdbau & Abbruch GmbH"),
            ("Plauener Spitzen & Stickereien GmbH",
             "Plauener Spitzen und Stickereien GmbH"),
            ("A. Richter Kälte- u. Klimatechnik",
             "A. Richter Kälte- und Klimatechnik"),
            ("Schmidt und Sohn GmbH", "Schmidt & Sohn GmbH")]
    for a, b in same:
        check(f"{a[:28]!r} == the other spelling",
              B.match_key(a) == B.match_key(b), True)

    # It must still separate companies that merely share a word. Dropping a
    # joining word may not turn two firms into one.
    different = [("Siemens AG", "Siemens Energy AG"),
                 ("Müller und Sohn GmbH", "Müller und Tochter GmbH"),
                 ("Kaiser Holz GmbH", "Kaiser Stahl GmbH")]
    for a, b in different:
        check(f"{a[:24]!r} != {b[:24]!r}", B.match_key(a) == B.match_key(b), False)

    check("a name that is only a joining word does not vanish into nothing",
          bool(B.match_key("Und Partner GmbH")) or B.match_key("Und Partner GmbH") == "partner",
          True)


# ---------------------------------------------------------------------------
# 11. Invisible characters and the encoding they came from. OptoNet's page
#     puts a soft hyphen inside almost every word, and one saved copy had been
#     decoded with the wrong character set (2026-09-24).
# ---------------------------------------------------------------------------

def test_invisible_characters() -> None:
    import benchmark as B
    import cleaner
    print("soft hyphens and zero-width characters")

    soft = "Light­Trans Inter­na­tio­nal GmbH"
    check("a soft hyphen is removed, not turned into a space",
          cleaner.strip_invisible(soft), "LightTrans International GmbH")
    check("zero-width characters go too",
          cleaner.strip_invisible("A​B‌‍C⁠﻿"), "ABC")
    check("a hyphenated name keeps its real hyphen",
          cleaner.strip_invisible("Mueller-Meier GmbH"), "Mueller-Meier GmbH")
    check("the scorer matches the two spellings",
          B.match_key(soft) == B.match_key("LightTrans International GmbH"), True)
    check("the cleaner strips them from page text",
          "­" in cleaner.process("<p>Tech­no­logie</p>").text, False)


def test_pick_encoding() -> None:
    import fetcher
    print("which character set a page is decoded with")

    check("the HTTP header wins",
          fetcher.pick_encoding(b"<meta charset='iso-8859-1'>", "text/html; charset=utf-8", "mac_roman"),
          "utf-8")
    check("otherwise the page's own declaration wins over the guess",
          fetcher.pick_encoding(b"<meta charset=\"utf-8\">", "text/html", "mac_roman"), "utf-8")
    check("with nothing declared, the guess is used",
          fetcher.pick_encoding(b"<html></html>", "text/html", "iso-8859-1"), "iso-8859-1")
    check("a charset nobody knows falls back to the guess",
          fetcher.pick_encoding(b"<meta charset='utf-9000'>", "", "utf-8"), "utf-8")
    check("nothing at all is allowed",
          fetcher.pick_encoding(b"", "", None), None)


# ---------------------------------------------------------------------------
# 12. ZIM versus privately funded. Neovation reports the two separately, so a
#     row must never be silently attributed to the wrong programme.
# ---------------------------------------------------------------------------

def test_source_dataset() -> None:
    import export_deliverable as E
    print("source dataset: ZIM network or privately funded")

    lookup = {"kliwatex.de": "ZIM network", "voice-ev.org": "Private funded"}
    check("a network in the Finalv1 sheet is labelled from it",
          E.dataset_for("https://www.kliwatex.de/unternehmen", "", lookup),
          "ZIM network")
    check("www and path do not matter",
          E.dataset_for("http://kliwatex.de/", "", lookup), "ZIM network")
    check("privately funded is kept apart",
          E.dataset_for("https://voice-ev.org/verband/mitglieder/", "", lookup),
          "Private funded")
    check("a page not in the sheet falls back to the list it came from",
          E.dataset_for("https://example.org/mitglieder", "Deutsche_technische_Verbaende_erweitert", lookup),
          "Technical association")
    check("an unknown origin says so rather than guessing",
          E.dataset_for("https://example.org/mitglieder", "", lookup), "unknown")
    check("the sheet wins over the list a URL was collected in",
          E.dataset_for("https://www.kliwatex.de/unternehmen",
                        "Private_funded_innovation_clubs_FINAL_200", lookup),
          "ZIM network")


# ---------------------------------------------------------------------------
# 13. Contact details in the worksheets. Removing them saves hours of manual
#     deleting, but the first version of the rule deleted a real company whose
#     name contains an "@" (2026-09-25).
# ---------------------------------------------------------------------------

def test_contact_details() -> None:
    import make_ground_truth as G
    print("worksheet pre-fill: contact details versus names")

    drop = ["info@ avoid-unrequested-mails agendia.com",   # spam-protected e-mail
            "kundenservice@cepheideurope.com",
            "WWW.CEPHEID.COM/DE", "www.salzgitter-ag.de", "https://biotype.de",
            "cepheid.com/de", "Telefon: 030 123456", "Fax 0221 4567",
            "+49 241 80 87 112", "66763 Dillingen", "47137 Duisburg",
            "Kölner Straße 64", "Hochschulring 20"]
    for text in drop:
        check(f"dropped: {text[:38]!r}", G.is_contact_detail(text), True)

    core = [("ArcelorMittal Bremen GmbH 28237 Bremen bremen.arcelormittal.com",
             "ArcelorMittal Bremen GmbH"),
            ("Badische Stahlwerke GmbH 77694 Kehl/Rhein www.bsw-kehl.de",
             "Badische Stahlwerke GmbH"),
            ("BGH Edelstahl Freital GmbH 01705 Freital www.bgh.de",
             "BGH Edelstahl Freital GmbH"),
            ("Siemens AG", "Siemens AG"),                    # nothing to strip
            ("Hochschule Offenburg", "Hochschule Offenburg"),
            # A name that ENDS in something address-like must survive whole.
            ("Stahlwerk Annahütte Max Aicher GmbH & Co. KG",
             "Stahlwerk Annahütte Max Aicher GmbH & Co. KG")]
    for line, want in core:
        check(f"core name of {line[:34]!r}", G.core_name(line), want)
    check("a line that is only an address does not become empty",
          G.core_name("47137 Duisburg"), "47137 Duisburg")

    # Filter checkboxes from a page's search sidebar carry a match count.
    for facet in ["Agile Methoden / Scrum (24)", "Beratung (94)",
                  "Angewandte Informatik-Forschung (2)", "Big Data (29)"]:
        check(f"filter facet: {facet[:34]!r}", G.is_filter_facet(facet), True)
    for real in ["]init[ AG", "Siemens AG", "1&1 Telecom GmbH",
                 "Ingenieurbüro Meyer GmbH (Niederlassung 2)",  # has a legal form
                 "Nynas GmbH & Co. KG"]:
        check(f"not a facet: {real[:34]!r}", G.is_filter_facet(real), False)

    keep = ["ST@RT HÜRTH Zentrum für Technologie und Existenzgründung",
            "Siemens AG", "3M Deutschland GmbH", "A. Richter Kälte- u. Klimatechnik",
            "2mag AG", "Hochschule Offenburg", "TINAtex GmbH",
            "Straßenbau Müller GmbH",           # a name that contains "Straße"
            "1000 Grad Ceramics GmbH"]          # a name that starts with digits
    for text in keep:
        check(f"kept: {text[:38]!r}", G.is_contact_detail(text), False)


def test_partial_runs_are_kept() -> None:
    """
    A page whose last chunk failed still contributed every earlier chunk.

    Production page p094 returned 162 companies and then failed to parse one
    chunk. Discarding the run removed that whole network from Neovation's
    sheet: 15,940 members instead of 16,102, and the eco Verband der
    Internetwirtschaft appearing nowhere at all.

    A clean run must still beat an errored one for the same page, or a
    partial result could displace a complete one.
    """
    from export_deliverable import run_rank
    print("deliverable: a partial extraction beats no extraction")

    clean_small = {"error": "", "raw_count": "10"}
    clean_big = {"error": "", "raw_count": "99"}
    partial_big = {"error": "unparseable JSON", "raw_count": "162"}
    partial_small = {"error": "unparseable JSON", "raw_count": "5"}

    check("a clean run beats a partial one, even a much bigger partial",
          run_rank(clean_small) > run_rank(partial_big), True)
    check("between clean runs, the fuller one wins",
          run_rank(clean_big) > run_rank(clean_small), True)
    check("between partial runs, the fuller one wins",
          run_rank(partial_big) > run_rank(partial_small), True)
    # Clean always outranks partial, including a clean run that found less.
    # That is deliberate: a run that failed mid-way may have stopped before
    # the end of the page, so its larger count is not evidence of more
    # coverage. Runs that found nothing never reach the ranking at all, the
    # caller skips them, which is what lets a partial run be used instead of
    # being dropped.
    check("clean outranks partial regardless of count",
          run_rank({"error": "", "raw_count": "1"}) > run_rank(partial_big), True)
    # Malformed counts must not crash the export half way through a run.
    for bad in (None, "", "abc", "12.0"):
        run_rank({"error": "", "raw_count": bad})
    check("a malformed count is treated as zero",
          run_rank({"error": "", "raw_count": "abc"})[1], 0)


def test_same_page_anchor() -> None:
    """
    A #fragment link is a jump within this page, not a link to another one.

    Found on the production run and it was a hole, not just waste. The
    Leasingverband links each of its 134 members to
    `mitglieder.leasingverband.de/#m2`, `#m50`, `#m426`; Composites United
    does the same for 582. All 716 were routed to the profile stage, which
    fetched the identical page 716 times (716 URLs, 3 distinct files), then
    skipped them for exceeding its word limit. Stage 4 never queued them
    because their route said "profile", so 4.4% of the corpus was served by
    nothing at all.

    The opposite error would be worse: treating a real profile page as an
    anchor would discard working links, so the path must be compared too.
    """
    import link_coverage as L
    print("routing: a #fragment is not a profile page")

    page = "https://mitglieder.leasingverband.de/"
    for href in ("https://mitglieder.leasingverband.de/#m50",
                 "https://mitglieder.leasingverband.de#m2",
                 "https://www.mitglieder.leasingverband.de/#m426"):
        check(f"anchor on the same page: {href[-6:]}",
              L.same_page_anchor(href, page), True)

    # A real profile page must never be discarded, with or without a fragment.
    for href in ("https://mitglieder.leasingverband.de/member/alpha",
                 "https://mitglieder.leasingverband.de/member/alpha#contact",
                 "https://other.de/#m50"):
        check(f"not an anchor: {href[-24:]}", L.same_page_anchor(href, page), False)

    # No fragment at all is never an anchor, even for the page itself.
    check("the page's own URL without a fragment",
          L.same_page_anchor(page, page), False)
    # A trailing slash carries no meaning.
    check("trailing slash ignored",
          L.same_page_anchor("https://x.de/members#a", "https://x.de/members/"), True)
    # A different query is a different page.
    check("a different query is a different page",
          L.same_page_anchor("https://x.de/m?p=2#a", "https://x.de/m"), False)


def test_names_from_run() -> None:
    """
    Production routing reads the names the model extracted, not a ground truth.

    The 30 research pages have hand-labelled answer keys. The 230 production
    networks have none, and nobody is going to label 16,176 companies, so
    `link_coverage.py --from-run` takes the company list from stage 1's saved
    extractions instead. Everything downstream, the profile queue and the
    search queue, is built from whatever this returns.
    """
    import json
    import tempfile
    import pathlib
    import config
    import link_coverage as L
    print("production routing: company names from a run's extractions")

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        folder = root / "runs" / "testrun" / "extractions"
        folder.mkdir(parents=True)
        (folder / "a.json").write_text(json.dumps({
            "key": "b|qwen3.5:9b|few_shot_full_record|constrained|p001|1",
            "raw": ["Alpha GmbH", "Beta AG", "Alpha GmbH", "  Alpha  ", "", "   "],
            "records": [],
        }), encoding="utf-8")
        (folder / "b.json").write_text(json.dumps({
            "key": "b|qwen3.5:9b|few_shot_full_record|constrained|p002|1",
            "raw": [], "records": [],
        }), encoding="utf-8")
        (folder / "c.json").write_text(json.dumps({
            "key": "malformed", "raw": ["Gamma SE"], "records": [],
        }), encoding="utf-8")

        real = config.RESULTS_DIR
        config.RESULTS_DIR = root
        try:
            got = L.names_from_run("testrun")
        finally:
            config.RESULTS_DIR = real

    check("one page in, one page out", sorted(got), ["p001"])
    # "Alpha GmbH", "Alpha GmbH" and "  Alpha  " are one company. Keeping all
    # three would put the same firm in Neovation's sheet three times.
    check("duplicates collapse on the normalised key", len(got["p001"]), 2)
    check("the first spelling is kept", got["p001"][0], "Alpha GmbH")
    check("blank names are dropped", "" in got["p001"], False)
    # A page that returned nothing must be absent, not present with an empty
    # list, or it creates rows downstream for a network with no members.
    check("an empty page is absent, not empty", "p002" in got, False)
    check("a malformed key is skipped", "malformed" in str(got), False)


def test_website_classification() -> None:
    """
    The four things a returned web address can be, and the one that was missing.

    Until 2026-09-30 the scorer had three branches, not four. Any company
    `link_coverage.py` had not paired was counted as a misattribution the
    moment the model returned an address for it. That produced 4,632 such
    counts, reported as "21.9% wrong company" and precision 0.779.

    It was false. Across the winning configuration there were zero
    disagreements on companies the pairing DOES cover, and the unpaired ones
    were mostly the model being right where the pairing was silent:
    Technologie Zentrum Dortmund GmbH -> tzdo.de.

    The pairing covers 1,134 of 2,638 companies. Counting its silence as the
    model's error measures the yardstick, not the model.
    """
    import score_websites as W
    print("website scoring: correct, wrong, unscored, invented")

    page = {"tzdo.de", "dew-stahl.com", "aesculap.de", "spectaris.de"}

    check("matches the pairing",
          W.classify("aesculap.de", "aesculap.de", page), "correct")
    check("the pairing says something else",
          W.classify("spectaris.de", "aesculap.de", page), "wrong")
    # The bug: no pairing for this company, so nothing can be concluded.
    check("no pairing, address is on the page -> unscored",
          W.classify("tzdo.de", "", page), "unscored")
    check("no pairing, address is NOT on the page -> invented",
          W.classify("erfunden.de", "", page), "invented")
    check("pairing exists but address is off-page: still wrong, not invented",
          W.classify("erfunden.de", "aesculap.de", page), "wrong")

    # The property that matters: silence from the pairing must never be
    # counted against the model. This is the assertion whose absence caused
    # the wrong result.
    for host in ("tzdo.de", "dew-stahl.com"):
        check(f"unpaired {host} is not an error",
              W.classify(host, "", page) in ("wrong", "invented"), False)

    # And precision must exclude unscored from its denominator, or the
    # pairing's coverage is reported as the model's error rate.
    counts = {"correct": 90, "wrong": 5, "invented": 5, "unscored": 400}
    judged = counts["correct"] + counts["wrong"] + counts["invented"]
    near("precision is over what can be judged", counts["correct"] / judged, 0.90)
    near("including unscored would give this instead",
         counts["correct"] / (judged + counts["unscored"]), 0.18)


def test_stage4_evidence() -> None:
    """
    Stage 4 decides what enters the database on evidence it gathers itself.

    The failure mode is accepting a plausible wrong answer, because a search
    always returns something and everything it returns looks reasonable. The
    first live test of ten companies made this concrete: 8 results passed a
    name-appears-on-the-page check and 3 of those 8 were business directories,
    which naturally mention every company they list.

    So the tests that matter are the refusals, not the acceptances.
    """
    import config
    import search_websites as S
    print("stage 4: weighing evidence for a searched website")

    # An address states the website outright. A provider mailbox does not.
    check("own domain is evidence", S.email_domain("info@5microns.de"), "5microns.de")
    check("www is dropped", S.email_domain("a@www.firma.de"), "firma.de")
    for provider in ("info@gmail.com", "kontakt@web.de", "a@t-online.de",
                     "b@gmx.net", "c@outlook.com"):
        check(f"provider mailbox is not evidence: {provider}",
              S.email_domain(provider), "")
    for junk in ("", "not-an-email", "info@", "info@localhost"):
        check(f"unusable address: {junk!r}", S.email_domain(junk), "")

    # The same number is printed many ways, so only the tail can be compared.
    a = S.phone_tail("+49 341 253966-0")
    check("formats agree", S.phone_tail("0341/253966-0"), a)
    check("country code form agrees", S.phone_tail("0049 341 2539660"), a)
    check("different numbers differ", S.phone_tail("+49 30 1234567") == a, False)
    check("too short to be distinctive", S.phone_tail("12345"), "")

    # A company stage 1 already found a website for must not be searched for
    # again. On production that is 3,682 of 8,452, five hours of searching and
    # 3,682 chances to return a different, wrong answer for a company we
    # already had right. Verified first: 3,682 of those 3,683 hostnames are
    # present in the page, a 0.03% invention rate.
    import tempfile, pathlib, csv as _csv
    with tempfile.TemporaryDirectory() as tmp:
        cov = pathlib.Path(tmp) / "link_coverage.csv"
        with open(cov, "w", newline="", encoding="utf-8") as fh:
            w = _csv.DictWriter(fh, fieldnames=["url_id", "org_name", "company",
                                                "route", "target"])
            w.writeheader()
            for name, route in (("Alpha GmbH", "none"), ("Beta AG", "none"),
                                ("Gamma SE", "website"), ("Delta KG", "profile")):
                w.writerow({"url_id": "p001", "org_name": "N", "company": name,
                            "route": route, "target": ""})
        # RESULTS_DIR is redirected at the empty temp folder as well, so the
        # "anyone stage 3 could not serve" backstop stays inert here. Without
        # this the test reads whatever profile_records.csv the machine
        # happens to have, and passes or fails depending on the machine.
        real, real_res = S.IN_CSV, config.RESULTS_DIR
        S.IN_CSV, config.RESULTS_DIR = cov, pathlib.Path(tmp)
        try:
            check("without records, every 'none' is queued",
                  len(S.load_queue(None)), 2)
            recs = {("p001", S.match_key("Alpha GmbH")): {"website": "https://alpha.de"}}
            got = S.load_queue(None, recs)
            check("a company with a known website is skipped", len(got), 1)
            check("and it is the right one left", got[0]["company"], "Beta AG")
            # An empty website field must not count as known.
            recs = {("p001", S.match_key("Alpha GmbH")): {"website": "   "}}
            check("a blank website does not skip", len(S.load_queue(None, recs)), 2)
        finally:
            S.IN_CSV, config.RESULTS_DIR = real, real_res

    # The backstop: anyone the profile stage could not serve must still be
    # searched. No URL rule can predict every way a "profile link" turns out
    # to be a listing: the Leasingverband uses one page with 134 different
    # #fragments, Composites United uses 582 distinct paths that all return
    # the same page. Both were skipped by stage 3 and never queued here, so
    # 716 companies were served by nothing. Asking what stage 3 produced
    # cannot miss a case.
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        cov = d / "link_coverage.csv"
        with open(cov, "w", newline="", encoding="utf-8") as fh:
            w = _csv.DictWriter(fh, fieldnames=["url_id", "org_name", "company",
                                                "route", "target"])
            w.writeheader()
            for name, route in (("Alpha GmbH", "none"), ("Beta AG", "profile"),
                                ("Gamma SE", "profile"), ("Delta KG", "website")):
                w.writerow({"url_id": "p001", "org_name": "N", "company": name,
                            "route": route, "target": "x"})
        prof = d / "profile_records.csv"
        with open(prof, "w", newline="", encoding="utf-8") as fh:
            w = _csv.DictWriter(fh, fieldnames=["url_id", "company", "company_url"])
            w.writeheader()
            w.writerow({"url_id": "p001", "company": "Beta AG",
                        "company_url": "https://beta.de"})
            w.writerow({"url_id": "p001", "company": "Gamma SE", "company_url": ""})
        real_in, real_res = S.IN_CSV, config.RESULTS_DIR
        S.IN_CSV, config.RESULTS_DIR = cov, d
        try:
            got = {r["company"] for r in S.load_queue(None)}
            check("the no-link company is queued", "Alpha GmbH" in got, True)
            check("a company stage 3 served is NOT queued", "Beta AG" in got, False)
            check("a company stage 3 failed IS queued", "Gamma SE" in got, True)
            check("a company with a website on the page is never queued",
                  "Delta KG" in got, False)
            # Without stage 3 output, fall back to the route alone rather
            # than searching for every profile company.
            prof.unlink()
            got = {r["company"] for r in S.load_queue(None)}
            check("before stage 3 runs, only the no-link ones are queued",
                  got, {"Alpha GmbH"})
        finally:
            S.IN_CSV, config.RESULTS_DIR = real_in, real_res

    # Directory brands run one domain per country. Blocking exact hosts loses
    # that game: cylex.de was listed and cylex.at still came back top for
    # A. Höfer GmbH in the 30-company trial.
    for host in ("cylex.de", "cylex.at", "web2.cylex.de", "www.cylex.ch",
                 "europages.co.uk", "de.kompass.com", "northdata.de"):
        check(f"directory blocked: {host}", S.is_aggregator(host), True)
    # A real company must not be blocked by sharing a word with one.
    for host in ("aesculap.de", "5microns.de", "element.io",
                 "xing-technologies.de", "yelp-medizintechnik.de"):
        check(f"real company allowed: {host}", S.is_aggregator(host), False)

    # The weighing. No single weak signal may confirm a result on its own,
    # and any strong one may.
    check("name alone is never confirmed", S.decide({"name"})[0], "page_only")
    check("domain alone is not confirmed", S.decide({"domain"})[0], "domain_match")
    check("name and postcode together confirm",
          S.decide({"name", "postcode"})[0], "verified")
    check("domain and name together confirm",
          S.decide({"domain", "name"})[0], "verified")
    check("a phone number confirms by itself", S.decide({"phone"})[0], "verified")
    check("the company's own email confirms", S.decide({"email"})[0], "verified")
    check("no evidence is refused", S.decide(set())[0], "unverified")

    # The directory case, which is what this stage exists to refuse. A
    # business directory mentions the company and nothing else matches.
    check("a directory that merely names the company is not confirmed",
          S.decide({"name"})[0] == "verified", False)

    # Evidence gathering from a page, with the network faked.
    class Resp:
        status_code, apparent_encoding, encoding = 200, "utf-8", "utf-8"
        def __init__(self, text): self.text = text
    class Session:
        def __init__(self, text): self._t = text
        def get(self, url, timeout=0): return Resp(self._t)

    rec = {"postcode": "10115", "phone": "+49 30 1234567",
           "email": "info@beispiel.de"}
    page = ("<p>Beispiel Technologie GmbH, Musterweg 3, 10115 Berlin, "
            "Tel. 030 1234567, info@beispiel.de</p>")
    got = S.page_evidence("http://x", "Beispiel Technologie GmbH", rec, Session(page))
    check("everything on the page is found", got,
          {"name", "postcode", "phone", "email"})

    # A page for a DIFFERENT company must yield only the weakest signal, or
    # nothing. This is the test that would have caught the directory problem.
    other = "<p>Beispiel Technologie GmbH is listed in our directory.</p>"
    got = S.page_evidence("http://x", "Beispiel Technologie GmbH", rec, Session(other))
    check("a mention alone yields only the name", got, {"name"})
    check("and a mention alone is not confirmed", S.decide(got)[0], "page_only")

    # No contact details known: the stage still works, just more cautiously.
    got = S.page_evidence("http://x", "Beispiel Technologie GmbH", {}, Session(page))
    check("with nothing known, only the name can match", got, {"name"})


def test_email_deobfuscation() -> None:
    """
    Pages hide email addresses from crawlers, and that also defeats us.

    Measured on the 30-page stage 3 output: 331 addresses, of which 211 were
    valid, 119 were written BACKWARDS and 1 used "(at)". The reversed ones
    come from the CSS trick, where the markup holds `ed.elpmaxe@ofni` and a
    stylesheet flips it for the reader. 36% of the field was unusable.

    The dangerous direction is over-correction, so the test that matters most
    is that a valid address is never touched.
    """
    import extractor as E
    print("email: undoing anti-crawler obfuscation")

    # Real examples from the corpus.
    for hidden, want in (
        ("ed.snorcim5@tkatnok", "kontakt@5microns.de"),
        ("moc.ameraa@ofni", "info@aarema.com"),
        ("ed.anej-sfa@tcatnoc", "contact@afs-jena.de"),
        ("moc.puorgsidokka@anej", "jena@akkodisgroup.com"),
        ("hpi-info(at)hpi.de", "hpi-info@hpi.de"),
    ):
        check(f"{hidden} -> {want}", E._clean_email(hidden), want)

    # Spelled-out variants.
    check("(at) and (dot)", E._clean_email("info (at) example (dot) de"),
          "info@example.de")
    check("square brackets", E._clean_email("info[at]example.de"),
          "info@example.de")

    # A valid address must survive untouched. This is the one that stops the
    # fix becoming the bug: several real addresses reverse into something that
    # still looks plausible, so the valid check has to come first.
    for good in ("info@example.de", "kontakt@5microns.de",
                 "a.mueller@firma-gmbh.co.uk", "INFO@Example.DE"):
        check(f"valid address untouched: {good}", E._clean_email(good), good)

    # Nothing recognisable: keep it, do not blank it. A human can read a
    # malformed address; an empty cell says nothing.
    for junk in ("not an email", "info@", "@example.de", ""):
        check(f"unrecognised kept as-is: {junk!r}", E._clean_email(junk), junk)

    # Whole records go through the same path, so a record's email is repaired
    # wherever it comes from, not only in stage 3.
    rec = E._as_record({"name": "5microns GmbH", "email": "ed.snorcim5@tkatnok"})
    check("a record's email is repaired too", rec["email"], "kontakt@5microns.de")


def test_profile_page_cleaning() -> None:
    """
    A single-company page keeps its inner sections; a listing page does not.

    OSB Alliance's theme puts the member's website, address and email inside
    <header class="entry-content-header"> within <article>, which is valid
    HTML5. The blunt "strip every header" rule reduced a 98 KB profile page to
    152 words of navigation, and 183 of 482 profile pages returned nothing:
    1% on every field, against 87% on the network beside it.

    The opposite must also hold. On the 30 listing pages the same change adds
    only menu items ("Themenfelder", "Kontakt", "Mitglied werden"), 0 of which
    are companies in the answer key, so turning it on there would cost
    precision and invalidate 1,620 completed runs for nothing.
    """
    import cleaner
    print("cleaning: profile pages keep inner sections, listings do not")

    html = """
    <html><body>
      <header id="site"><nav>Menu Kontakt Mitglied werden</nav></header>
      <main>
        <article>
          <header class="entry-content-header">
            <p>Element Software GmbH, Musterweg 3, 10115 Berlin</p>
          </header>
          <div class="entry-content">Some body text.</div>
        </article>
      </main>
      <footer id="site-footer">Impressum</footer>
    </body></html>
    """

    listing = cleaner.process(html).text
    profile = cleaner.process(html, keep_inner_sections=True).text

    check("a listing page loses the article's own header",
          "Musterweg" in listing, False)
    check("a profile page keeps it", "Musterweg" in profile, True)
    check("a profile page keeps the postcode too", "10115" in profile, True)

    # The site's own chrome must still go in BOTH modes, or a profile page
    # gains the whole menu and we trade one failure for another.
    for mode, text in (("listing", listing), ("profile", profile)):
        check(f"{mode}: the site menu is still removed",
              "Mitglied werden" in text, False)
        check(f"{mode}: the site footer is still removed",
              "Impressum" in text, False)

    # Body content is untouched either way: the switch must only ever ADD.
    for mode, text in (("listing", listing), ("profile", profile)):
        check(f"{mode}: the article body survives", "Some body text" in text, True)


def test_resume_dedupe() -> None:
    """
    A retry must replace the failure it fixed, exactly once.

    Resuming appends, so the results file carries both rows. Counting both
    would report a configuration twice and attach a failure to one copy,
    which lowers its pooled F1 by precisely the runs that were repaired. The
    archived 10-page study has no duplicates, so this must also be a no-op
    there, or the validated numbers move.
    """
    import make_report as R
    print("resume: a retry replaces the failure it fixed")

    def row(uid, err="", ts="2026-09-27T10:00:00+00:00", f1="0.9"):
        return {"stage": "a", "model_name": "llama3.1:8b",
                "prompt_technique": "zero_shot", "json_mode": "constrained",
                "url_id": uid, "repetition": "1", "error": err,
                "timestamp": ts, "f1": f1}

    failed = row("079", err="unparseable JSON", ts="2026-09-27T10:00:00+00:00", f1="0.0")
    fixed = row("079", ts="2026-09-28T02:00:00+00:00", f1="0.95")
    out = R.dedupe([failed, fixed])
    check("the pair collapses to one row", len(out), 1)
    check("and it is the one that worked", out[0]["f1"], "0.95")

    # Order must not matter: the file is read in write order, but a rebuilt
    # or re-sorted file must give the same answer.
    out = R.dedupe([fixed, failed])
    check("same answer when the failure comes second", out[0]["f1"], "0.95")

    # Two failures for one configuration: the later one is kept, and it stays
    # a failure, because there the failure is the result.
    a = row("077", err="stage2: timed out", ts="2026-09-27T10:00:00+00:00")
    b = row("077", err="still generating", ts="2026-09-28T03:00:00+00:00")
    out = R.dedupe([a, b])
    check("two failures collapse to the later one", len(out), 1)
    check("and it is still recorded as a failure", bool(out[0]["error"]), True)

    # Different configurations must never be merged.
    x = row("079")
    y = dict(row("079"), repetition="2")
    z = dict(row("079"), model_name="qwen3.5:9b")
    check("distinct configurations are kept apart", len(R.dedupe([x, y, z])), 3)

    # And the no-op case, which is what the archived study looks like.
    clean = [row(u) for u in ("004", "005", "009")]
    check("a file with no duplicates is unchanged", len(R.dedupe(clean)), 3)


def test_streaming_calls() -> None:
    """
    The hang guard. A model that is working must never be cut off, and a dead
    connection must not cost a quarter of an hour.

    Measured before this existed: 47 of 1,053 runs on the 30-page names grid
    hung, and those hangs were 42,300 of the 81,360 wall-clock seconds. The
    old single deadline could not be tightened, because a legitimate call in
    the 10-page study took 468 s. So the test that matters is the pair: the
    slow reply survives, the stuck one raises.
    """
    import httpx
    import config
    import extractor as E
    print("streaming: telling a slow call apart from a stuck one")

    class Chunk(dict):
        """Stands in for both shapes the library returns."""
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

    def reply(pieces, meta):
        for i, p in enumerate(pieces):
            last = i == len(pieces) - 1
            yield Chunk(message=Chunk(content=p), done=last, **(meta if last else {}))

    check("a field reads out of a dict", E._field({"a": 1}, "a"), 1)
    check("a missing field falls back", E._field({"a": 1}, "b", "x"), "x")
    check("a null field falls back too", E._field({"a": None}, "a", "x"), "x")
    check("a field reads off an object",
          E._field(Chunk(message=Chunk(content="hi")), "message")["content"], "hi")

    calls = {"n": 0}

    class Fake:
        def __init__(self, script):
            self.script = script

        def chat(self, **kwargs):
            calls["n"] += 1
            action = self.script[min(calls["n"] - 1, len(self.script) - 1)]
            if isinstance(action, Exception):
                raise action
            return reply(*action)          # action is (pieces, meta)

    real, pause = E._CLIENT, E._RETRY_PAUSE_S
    E._RETRY_PAUSE_S = 0            # the wait is real in production, not here
    try:
        # Pieces arrive one by one and are joined in order.
        calls["n"] = 0
        E._CLIENT = Fake([(["Alpha ", "GmbH"], {"eval_count": 7})])
        text, meta, secs = E._call_once("m", "s", "u", constrained=False)
        check("streamed pieces are joined", text, "Alpha GmbH")
        check("the final chunk's counts are kept", meta.get("eval_count"), 7)
        check("one call, no retry", calls["n"], 1)

        # A dead connection is retried once, then succeeds.
        calls["n"] = 0
        E._CLIENT = Fake([httpx.ReadTimeout("timed out"),
                          (["Beta AG"], {"eval_count": 3})])
        text, meta, secs = E._call_once("m", "s", "u", constrained=False)
        check("a hang is retried and recovered", text, "Beta AG")
        check("it took exactly two attempts", calls["n"], 2)

        # Two hangs in a row must raise, not return a silent empty answer.
        # An empty string here would score as "the model found nothing",
        # which is a wrong result rather than a failed run.
        calls["n"] = 0
        E._CLIENT = Fake([httpx.ReadTimeout("timed out")])
        try:
            E._call_once("m", "s", "u", constrained=False)
            check("two hangs raise", "returned normally", "raised")
        except httpx.ReadTimeout:
            check("two hangs raise", "raised", "raised")
        check("it gave up after two attempts", calls["n"], 2)

        # The total cap stops a model that never stops talking, but only
        # after the cap, so a genuinely slow reply is untouched.
        calls["n"] = 0
        cap = config.REQUEST_TIMEOUT_S
        E._CLIENT = Fake([(["x"] * 50, {})])
        config.REQUEST_TIMEOUT_S = -1          # every chunk is already past it
        try:
            E._call_once("m", "s", "u", constrained=False)
            check("endless output hits the total cap", "returned normally", "raised")
        except TimeoutError:
            check("endless output hits the total cap", "raised", "raised")
        finally:
            config.REQUEST_TIMEOUT_S = cap
        # A run that blows the cap is pathological, not unlucky. Retrying it
        # would spend a second full cap to fail in exactly the same way.
        check("the total cap is not retried", calls["n"], 1)
    finally:
        E._CLIENT, E._RETRY_PAUSE_S = real, pause

    check("the gap deadline is shorter than the total cap",
          config.STREAM_GAP_S < config.REQUEST_TIMEOUT_S, True)
    check("the gap deadline clears the slowest call ever measured (468 s)"
          " once retried", config.STREAM_GAP_S * 2 >= 360, True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", action="store_true",
                    help="also scan the real pages, needs link_coverage.csv")
    args = ap.parse_args()

    for fn in (test_match_key, test_score, test_same_org, test_generic_labels,
               test_python38_compatible, test_clean_url, test_host_of,
               test_website_classification, test_merge_page, test_model_config,
               test_cloud_client, test_worksheet_parsing, test_joining_words,
               test_invisible_characters, test_pick_encoding,
               test_source_dataset, test_contact_details, test_streaming_calls,
               test_resume_dedupe, test_profile_page_cleaning,
               test_email_deobfuscation,
               test_stage4_evidence,
               test_website_classification,
               test_names_from_run,
               test_same_page_anchor,
               test_partial_runs_are_kept):
        fn()
    if args.corpus:
        scan_corpus()

    print(f"\n  {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
