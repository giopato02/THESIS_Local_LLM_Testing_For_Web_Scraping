"""
Central configuration for the NeoHub member-company extraction pipeline.

Everything tunable lives here so the other modules stay free of magic numbers,
and so the thesis can quote exact parameter values from a single file.

Author: Giorgi Pataridze <gpataridze@constructor.university>
Project: NeoHub / AP1 Unternehmensdatenbank (Neovation GmbH x Constructor University Bremen)
"""

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent      # .../Web_Scraping
THESIS_WORK = PROJECT_ROOT.parent                   # .../Thesis_work

DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
HTML_CACHE_DIR = RESULTS_DIR / "html_cache"
GROUND_TRUTH_DIR = DATA_DIR / "ground_truth"

# Which set of pages the pipeline is pointed at. Two exist and they answer
# different questions:
#
#   urls_73.csv          the research corpus, 30 of which are hand-labelled.
#                        Every accuracy number in the thesis comes from these.
#   urls_production.csv  the Finalv1 networks Neovation wants in the database.
#                        No answer keys; run once with the winning setup.
#
# Switched by environment variable rather than by editing this line, so a
# production run cannot silently become the default and quietly invalidate a
# later re-score of the research corpus:
#
#   NEOHUB_URLS=urls_production.csv .venv/bin/python benchmark.py --stage b ...
URLS_CSV = DATA_DIR / os.environ.get("NEOHUB_URLS", "urls_73.csv")
FETCH_MANIFEST_CSV = RESULTS_DIR / "fetch_manifest.csv"
BENCHMARK_CSV = RESULTS_DIR / "benchmark_results.csv"
COMPANIES_CSV = RESULTS_DIR / "extracted_companies.csv"

# The two upstream spreadsheets, exported to CSV by the team.
# 59 rows here carry a real member-list URL (collected by Diego).
SOURCE_VERBAENDE = THESIS_WORK / "Deutsche_technische_Verbaende_erweitert (1)(Verbände).csv"
# 14 rows here are marked Relevant? = Yes (collected by Yusif).
SOURCE_CLUBS = THESIS_WORK / "Private_funded_innovation_clubs_FINAL_200_directories(1)(First draft).csv"

for _d in (DATA_DIR, RESULTS_DIR, HTML_CACHE_DIR, GROUND_TRUTH_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# Fetching (Phase 1a)
# --------------------------------------------------------------------------

# Honest identification. We are a named research project, not an anonymous bot.
USER_AGENT = (
    "NeoHubResearchBot/1.0 (Constructor University Bremen bachelor thesis; "
    "Giorgi Pataridze; gpataridze@constructor.university) "
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

REQUEST_TIMEOUT = 30        # seconds
REQUEST_DELAY = 2.5         # baseline pause between requests to the same host
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0         # exponential: 2s, 4s, 8s

# Adaptive throttling, modelled on Scrapy's AUTOTHROTTLE as configured in
# Neovation's own scraperng. A fixed delay is either too slow for a fast server
# or too fast for a strained one; instead the delay tracks measured response
# time, so we stay gentle on slow hosts and do not crawl needlessly on quick
# ones. Bounded at both ends.
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_MIN_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 30.0
AUTOTHROTTLE_TARGET_LATENCY_RATIO = 1.0   # aim for delay ≈ observed latency

# Optional proxy rotation for hosts that refuse direct automated access.
# Five sites in this corpus answer 403 on the first request. Rayen uses
# scrapy-rotating-proxies with the same free list (meeting 2026-07-31), and
# considers it in scope because the data is public and could be copied by hand.
#
# OFF by default: free proxies are third-party machines of unknown operator, so
# traffic through them should be limited to fetching public pages, never
# anything authenticated. Results reported in the thesis were collected without
# proxies unless explicitly stated.
USE_PROXIES = False
PROXY_LIST_URL = ("https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list"
                  "@main/proxies/all/data.txt")
PROXY_LIST_PATH = RESULTS_DIR / "proxies.txt"
PROXY_MAX_ATTEMPTS = 8      # distinct proxies to try before giving up on a URL

# A page whose cleaned text falls below this is almost certainly a JS-rendered
# shell rather than a real member directory. Flagged, not silently accepted.
THIN_CONTENT_WORD_THRESHOLD = 150


# --------------------------------------------------------------------------
# Cleaning + chunking (Phase 1b)
# --------------------------------------------------------------------------

# Tags removed wholesale before text extraction.
STRIP_TAGS = [
    "script", "style", "noscript", "nav", "footer", "header",
    "img", "svg", "picture", "video", "audio", "iframe",
    "form", "input", "button", "select", "textarea",
    "aside", "canvas", "map", "template",
]

# Elements matching these get dropped too (cookie banners, menus, skip links).
STRIP_SELECTORS = [
    "[hidden]", '[aria-hidden="true"]', '[style*="display:none"]',
    '[style*="display: none"]', '[role="navigation"]', '[role="banner"]',
    ".cookie", ".cookies", "#cookie", ".sr-only", ".visually-hidden",
    ".breadcrumb", ".pagination", ".skip-link",
]

# German text is token-hungry: compound nouns split into many subword tokens.
# ~3 chars per token is a safer estimate than the usual English ~4.
# Write outbound link URLs into the cleaned text so the model can return a
# company website alongside its name. Off = names only (the Stage A setup).
PRESERVE_LINKS = True

CHARS_PER_TOKEN_ESTIMATE = 3

# Ollama silently truncates at num_ctx and never raises. Set it explicitly.
#
# Raised from 8192 on 2026-09-28, from measurement rather than a round number.
# Every chunk of all 30 ground-truth pages was prefilled with the largest
# prompt wrapper and its real token count read back:
#
#   largest chunk anywhere        8,123 tokens (page 079)
#   largest answer observed       1,760 tokens (198 companies, page 050)
#   room left at the old 8192     69 tokens on page 079
#
# At 8192 the five densest pages (005, 050, 079, 086, 088) had between 69 and
# 877 tokens for an answer needing about 1,760, so the reply was cut off mid
# name and arrived as unreadable JSON. That is what the 158 failures were: a
# setting, not a model. 16384 leaves 8,261 tokens of headroom on the worst
# page. Confirmed on the GPU: page 050 chunk 1 returns 198 complete names.
#
# Raised again to 32768 for the record arm (2026-09-28). The largest chunk is
# 8,123 tokens of input and the largest full-record answer about 15,840, and
# 16384 cannot hold both. Confirmed on the GPU at 24576: qwen3.5:9b was 6.3 GB
# and 100% GPU with a second model loaded beside it, so 32768 alone has room.
NUM_CTX = 32768
# Leave room for the prompt scaffold and the model's own JSON answer.
#
# NOTE this budget is an estimate of the PAGE TEXT only, at
# CHARS_PER_TOKEN_ESTIMATE, and the real prompt runs well over it: 6000 here
# produced a measured 8,123 tokens once the system prompt, the instructions
# and a German tokenizer were involved, a 35% underestimate. It is left at
# 6000 deliberately. Changing it would re-chunk every page, which changes the
# input to every call and invalidates the 1,462 completed runs. The window is
# the safe thing to move, because a run that never hit the limit generates
# exactly what it generated before.
CHUNK_TOKEN_BUDGET = 6000
CHUNK_OVERLAP_TOKENS = 200


# --------------------------------------------------------------------------
# Models + inference (Phase 2)
# --------------------------------------------------------------------------

# The ablation grid. qwen3.5:9b replaced gemma4:12b on 2026-09-15: the three
# are now in one size class (7-9B), so the comparison is between models rather
# than between parameter counts.
MODELS = ["qwen2.5-coder:7b", "llama3.1:8b", "qwen3.5:9b"]

# Retired from new runs. gemma4:12b's results on the first ten pages stay in the
# thesis as a measured negative finding (THESIS_NOTES 3.13); it was too slow to
# run again over thirty.
RETIRED_MODELS = ["gemma4:12b"]
OPTIONAL_MODELS = []

# Models that reason at length before answering unless told not to. Left on,
# the reasoning is slow and its tokens would be timed as extraction, so it is
# switched off for these. The other models have no such mode. Matched by
# prefix, so later qwen3.x tags are covered too.
THINKING_MODEL_PREFIXES = ("qwen3",)

TEMPERATURE = 0.0     # deterministic: this is an extraction task, not creative
SEED = 42
# Keep the model resident so we never time a cold reload. The benchmark loop
# MUST iterate model-outermost; on 16 GB the three models cannot coexist.
KEEP_ALIVE = "10m"

# Two deadlines, because "slow" and "stuck" are different failures and one
# number cannot separate them. Replies are read as they stream, so:
#
#   STREAM_GAP_S    how long we wait for the NEXT piece of text. A model that
#                   is working sends something every few seconds however long
#                   the total takes, so this catches a dead connection without
#                   ever cutting off genuine work.
#   REQUEST_TIMEOUT_S  total wall cap, for the opposite case: a model that
#                   keeps emitting text and never stops.
#
# Why this replaced a single 900 s deadline. On the 30-page names grid, 47 of
# 1,053 runs hung and each one sat on the full 900 s, which is 42,300 of the
# 81,360 wall-clock seconds: more than half the run spent waiting on dead
# connections. Tightening the single deadline instead was not safe, because a
# legitimate call in the 10-page study took 468 s.
STREAM_GAP_S = 180
REQUEST_TIMEOUT_S = 1800

# Stop a repetition loop by counting tokens rather than seconds.
#
# A model that has lost the thread keeps emitting text indefinitely, and a
# clock is a terrible way to notice: measured on the 2026-09-28 resume, 13
# runs consumed 6.9 of 7.7 hours waiting for the 1800 s cap to stop loops
# that were never going to finish, while the 28 runs that actually worked
# cost 44 minutes between them.
#
# Tokens separate the two cleanly, because the honest answers are not close
# to the limit. The largest real reply measured is 1,760 tokens (198
# companies, page 050 chunk 1); the next largest 1,550. At 4096 a loop is
# caught in roughly two minutes, and no honest reply is touched.
#
# This is a backstop, not a budget: hitting it means the reply is garbage and
# the run is recorded as failed, which is the correct outcome. A model that
# loops is a result worth reporting, just not one worth half an hour.
#
# Raised from 4096 for the record arm, again from measurement. A full record
# (name, website, street, postcode, city, phone, email) costs about **80
# tokens**, against 9 for a bare name: page 079 returned 96 records in 7,669
# tokens. The densest chunk, page 050 with 198 companies, therefore needs
# roughly 15,840 tokens, and at 8,192 it truncated at exactly the limit and
# failed to parse. 20,480 clears the worst chunk by about 29%.
#
# The cap still has to leave the loop guard meaningful, and it does: a loop
# runs unbounded, while the largest honest answer measured is 15,840.
NUM_PREDICT = 20480

JSON_MODES = ["constrained", "prompt_only"]

# JSON Schemas handed to Ollama's `format` parameter in constrained mode.
# Two are needed: constrained decoding forces the reply to match the schema
# exactly, so a name-only schema would strip the extra fields the full-record
# strategy is meant to return.
COMPANY_RECORD_SCHEMA = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "url": {"type": "string"},
                    "street": {"type": "string"},
                    "postcode": {"type": "string"},
                    "city": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["name"],
            },
        }
    },
    "required": ["companies"],
}

COMPANY_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
    "required": ["companies"],
}


# --------------------------------------------------------------------------
# Benchmark design (Phase 4)
# --------------------------------------------------------------------------

# Stage A: full ablation grid on the hand-labelled subset, repeated for
# latency variance. Stage B: winning configuration across all 73 URLs.
STAGE_A_REPETITIONS = 3
STAGE_B_REPETITIONS = 1
GROUND_TRUTH_SAMPLE_SIZE = 10

# The cloud path has no equivalent of Ollama's `think: False`. The switch
# below appends qwen's `/no_think` token to the system prompt instead.
#
# OFF by default, because the evidence says it is not needed on this endpoint:
# a direct check of constructor/Qwen/Qwen3.5-9B returned 0 characters of
# thinking and clean JSON, and still took 75.7 s against claude-haiku's 9.8 s
# on the byte-identical request. The latency is the endpoint, not reasoning.
#
# Turning it on modifies the prompt, which is the one thing that must stay
# identical between local and cloud for the comparison to mean anything. Only
# set True if a run actually shows <think> output or reasoning preamble.
CLOUD_NO_THINK = False
