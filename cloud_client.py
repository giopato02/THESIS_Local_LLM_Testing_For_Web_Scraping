"""
Cloud models through the Constructor Model API, as a drop-in for Ollama.

A model name starting with "constructor/" is sent here instead of to Ollama:

    constructor/gemini-3.6-flash
    constructor/claude-haiku-4-5
    constructor/llama3.1:8b-instruct-q4_K_M    the same llama as the local runs

Everything around the call stays identical (prompts, cleaning, chunking,
scoring), so cloud and local results compare directly.

Needs two environment variables. Never write them into code or commit them:

    CONSTRUCTOR_API_KEY   created under Model > API Keys in Constructor Learn
    CONSTRUCTOR_KM_ID     the knowledge model requests go through;
                          `constructor_setup.py km` finds or creates one

What the API does differently from Ollama, measured on 2026-09-15:

  * Every answer arrives twice, concatenated: {...}{...}, with stream set to
    false as well. An exact repeat is removed here. Left in, the JSON repair
    step would recover the first copy but mark every cloud answer as
    repaired, which would misreport the cloud models' JSON reliability.
  * Token counts are always 0, so the token and tokens-per-second columns
    stay 0 for cloud runs. Wall-clock time is still measured.
  * Schema-constrained output (response_format json_schema) was accepted for
    an OpenAI model, rejected for Claude, and accepted for Gemini, whose
    answer still came wrapped in a markdown fence. Use --json-mode
    prompt_only for anything that is not an OpenAI model.
  * temperature 0 is accepted. Whether it is applied is not verified; the
    three repetitions per configuration will show it.
"""

from __future__ import annotations

import os
import time

import config

PREFIX = "constructor/"
API_URL = os.environ.get("CONSTRUCTOR_API_URL",
                         "https://constructor.app/api/platform-kmapi/v1")

# Rate limits and brief outages are worth waiting for. Any other failure is a
# real error and is recorded on the run instead of being retried.
RETRY_STATUS = {429, 500, 502, 503, 504}
RETRY_WAITS_S = (5, 20, 60)


class CloudError(RuntimeError):
    """A cloud request that failed for a reason retrying will not fix."""


def is_cloud(model: str) -> bool:
    return model.startswith(PREFIX)


def missing_settings() -> list[str]:
    return [name for name in ("CONSTRUCTOR_API_KEY", "CONSTRUCTOR_KM_ID")
            if not os.environ.get(name)]


def thinking_off(model: str) -> bool:
    """
    True for cloud models that reason before answering unless told not to.

    The Ollama path switches this off with `think: False`, which has no
    equivalent on an OpenAI-compatible endpoint. Qwen's documented soft
    switch is the token `/no_think` in the prompt, so that is what is used
    here. It is the same instruction by a different route, and it is applied
    to exactly the models config.THINKING_MODEL_PREFIXES already names, so
    local and cloud runs stay comparable.
    """
    name = model[len(PREFIX):] if is_cloud(model) else model
    # Hosted names carry the publishing org: "Qwen/Qwen3.5-9B", not the
    # "qwen3.5:9b" Ollama uses. Match on the last path segment, or every
    # Qwen model would be missed because the name starts with the org.
    name = name.rsplit("/", 1)[-1].lower()
    prefixes = tuple(getattr(config, "THINKING_MODEL_PREFIXES", ()))
    return bool(prefixes) and name.startswith(tuple(p.lower() for p in prefixes))


def build_body(model: str, system: str, user: str, constrained: bool,
               schema: dict | None = None) -> dict:
    """The request body. The key is sent as a header and never appears here."""
    if thinking_off(model) and getattr(config, "CLOUD_NO_THINK", True):
        # Appended rather than prepended: the instruction has to survive a
        # long system prompt, and Qwen reads the switch anywhere in it.
        system = system + "\n\n/no_think"

    body = {
        "model": model[len(PREFIX):] if is_cloud(model) else model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "temperature": config.TEMPERATURE,
        # The Ollama path sets num_predict explicitly; without the equivalent
        # here the provider applies its own default, commonly 1024 or 4096.
        # Long answers were then cut off mid-JSON. Measured on the first cloud
        # grid: 270 of 540 runs failed with "unparseable JSON", and the three
        # strategies that failed 100% were the three with the longest output,
        # for BOTH claude-haiku and Qwen3.5. A quieter form of the same bug
        # closed the JSON validly after too few companies, which scored as
        # poor recall rather than as an error.
        "max_tokens": getattr(config, "NUM_PREDICT", 4096),
    }
    seed = getattr(config, "SEED", None)
    if seed is not None:
        body["seed"] = seed
    if constrained:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "company_list",
                            "schema": schema or config.COMPANY_LIST_SCHEMA},
        }
    return body


def undouble(text: str) -> tuple[str, bool]:
    """
    Remove an exact repeat: "AA" or "A A" becomes "A".

    Only an identical second copy is removed. Two different answers are left
    alone, so a genuine second JSON object is never silently dropped here.
    """
    s = text.strip()
    n = len(s)
    for gap in (0, 1, 2):
        if n <= gap or (n - gap) % 2:
            continue
        half = (n - gap) // 2
        if s[:half] == s[half + gap:] and not s[half:half + gap].strip():
            return s[:half], True
    return text, False


def call(model: str, system: str, user: str, constrained: bool,
         schema: dict | None = None) -> tuple[str, dict, float]:
    """One round trip. Same return shape as extractor._call_once."""
    import requests  # only cloud runs need it

    missing = missing_settings()
    if missing:
        raise CloudError("set the environment variable(s) " + ", ".join(missing))

    url = (f"{API_URL}/knowledge-models/{os.environ['CONSTRUCTOR_KM_ID']}"
           f"/chat/completions")
    headers = {"X-KM-AccessKey": "Bearer " + os.environ["CONSTRUCTOR_API_KEY"],
               "Content-Type": "application/json"}
    body = build_body(model, system, user, constrained, schema)
    timeout = getattr(config, "REQUEST_TIMEOUT_S", 900)

    last = ""
    for attempt, wait in enumerate((0,) + RETRY_WAITS_S):
        if wait:
            time.sleep(wait)
        # Timed per attempt, so waiting between retries is not reported as
        # the model's latency.
        start = time.perf_counter()
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=timeout)
        except requests.RequestException as exc:
            last = type(exc).__name__
            continue
        elapsed = time.perf_counter() - start

        if resp.status_code in RETRY_STATUS:
            # Keep the body. A 500 that repeats on every attempt is not a
            # transient outage, it is that model's deployment failing, and
            # the body is the only thing that says why. Discarding it left
            # "HTTP 500" as the entire diagnosis.
            detail = (resp.text or "").strip().replace("\n", " ")[:200]
            last = f"HTTP {resp.status_code}" + (f": {detail}" if detail else "")
            continue
        if resp.status_code != 200:
            raise CloudError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        text = data["choices"][0]["message"].get("content") or ""
        text, doubled = undouble(text)
        usage = data.get("usage") or {}
        meta = {
            "prompt_eval_count": usage.get("prompt_tokens", 0) or 0,
            "eval_count": usage.get("completion_tokens", 0) or 0,
            "eval_duration": 0,
            "answer_was_doubled": doubled,
            "retries": attempt,
        }
        return text, meta, elapsed

    raise CloudError(f"no answer after {len(RETRY_WAITS_S) + 1} attempts ({last})")
