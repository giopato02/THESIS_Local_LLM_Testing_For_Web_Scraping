"""
Central configuration for the NeoHub member-company extraction pipeline.

Everything tunable lives here so the other modules stay free of magic numbers,
and so the thesis can quote exact parameter values from a single file.

Author: Giorgi Pataridze <gpataridze@constructor.university>
Project: NeoHub / AP1 Unternehmensdatenbank (Neovation GmbH x Constructor University Bremen)
"""

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

URLS_CSV = DATA_DIR / "urls_73.csv"
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
NUM_CTX = 8192
# Leave room for the prompt scaffold and the model's own JSON answer.
CHUNK_TOKEN_BUDGET = 6000
CHUNK_OVERLAP_TOKENS = 200


# --------------------------------------------------------------------------
# Models + inference (Phase 2)
# --------------------------------------------------------------------------

# The ablation grid. Both fit comfortably in 16 GB, so latency here measures
# inference rather than memory pressure.
MODELS = ["qwen2.5-coder:7b", "llama3.1:8b"]

# Larger models we want in the thesis but cannot afford across the full grid.
# gemma4:12b is 7.6 GB: with an 8k KV cache it pushes a 16 GB machine into
# swapping, so its wall-clock time reflects paging, not model speed. Running
# it over 300 ablation runs would take days. Run it on the WINNING
# configuration only, and report it as a separate scaling observation:
#     .venv/bin/python benchmark.py --stage a --models gemma4:12b \
#         --prompt <winner> --json-mode <winner>
OPTIONAL_MODELS = ["gemma4:12b"]

TEMPERATURE = 0.0     # deterministic: this is an extraction task, not creative
SEED = 42
# Keep the model resident so we never time a cold reload. The benchmark loop
# MUST iterate model-outermost; on 16 GB the three models cannot coexist.
KEEP_ALIVE = "10m"

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
