"""
Phase 2 -- run a cleaned page through a local model via Ollama.

The details in here are what make the benchmark trustworthy:

  * num_ctx is set EXPLICITLY. Ollama defaults to 4096 and truncates the
    prompt past that without raising anything. A page cleaning to 39,000
    tokens would silently become its first 10%, the model would return a
    short list, and the numbers would look plausible and be worthless.
  * temperature=0 and a fixed seed, so a re-run reproduces a run.
  * Ollama's own prompt_eval_count / eval_count / durations are captured
    alongside wall-clock time. Tokens-per-second is the comparable figure;
    raw seconds are not, when one model reads 8k tokens and the other 3k.
  * Chunked pages are extracted chunk by chunk and unioned, with latency
    summed, so a big page reports its true total cost.

Run standalone to sanity-check one page:
    .venv/bin/python extractor.py results/html_cache/<hash>.html qwen2.5-coder:7b
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

import httpx
import ollama

import cloud_client
import config
import prompts

# Shared client so the deadline applies to every call in the pipeline. Ollama's
# module-level functions use a default client with no deadline. The timeout is
# the GAP between pieces of a streamed reply, not the length of the call: see
# config.STREAM_GAP_S and _chat_streaming below.
_CLIENT = ollama.Client(timeout=getattr(config, "STREAM_GAP_S", 180))

# A hang is nearly always the connection dying rather than the work being hard,
# so one retry recovers the data point instead of losing the run to an error.
# Deliberately NOT the total cap (TimeoutError from _chat_streaming): a model
# still generating after half an hour is pathological, and retrying it would
# just spend another half hour to fail the same way.
_RETRY_ERRORS = (httpx.TimeoutException, httpx.TransportError)
_RETRY_PAUSE_S = 5


def _field(obj, name: str, default=None):
    """
    Read one field from an Ollama reply, whether it is a dict or a model.

    The library returns plain dicts in older versions and pydantic objects in
    newer ones. Streaming touches every chunk, so this is the one place that
    difference would otherwise turn into a crash halfway through a long grid.
    """
    try:
        value = obj[name]
    except (KeyError, TypeError, AttributeError):
        value = getattr(obj, name, default)
    return default if value is None else value


def _chat_streaming(kwargs: dict) -> tuple[str, dict]:
    """
    Read the reply as it is produced, so a stuck call is told apart from a slow one.

    The client deadline applies to each read, which under streaming is the gap
    between pieces of text. Before this, one deadline had to cover both cases,
    so it was either tight enough to kill real work or loose enough that every
    hang cost a quarter of an hour. Streaming does not change what the model
    generates: temperature, seed and num_ctx are untouched.
    """
    parts: list[str] = []
    final: dict = {}
    started = time.perf_counter()
    for chunk in _CLIENT.chat(**kwargs, stream=True):
        parts.append(_field(_field(chunk, "message", {}), "content", "") or "")
        if _field(chunk, "done", False):
            final = dict(chunk)
        if time.perf_counter() - started > config.REQUEST_TIMEOUT_S:
            raise TimeoutError(
                f"still generating after the {config.REQUEST_TIMEOUT_S}s total cap")
    return "".join(parts), final


@dataclass
class ExtractionResult:
    """Everything one (page, model, prompt, json_mode) run produces."""
    # Plain names, kept as strings so scoring and the Neovation filter are
    # unchanged across every prompt strategy.
    companies: list[str] = field(default_factory=list)
    # Full records for the strategies that return them; same order and
    # length as `companies`. Strategies returning only names leave every
    # optional field empty.
    records: list[dict] = field(default_factory=list)
    raw_output: str = ""
    latency_seconds: float = 0.0
    prompt_eval_count: int = 0
    eval_count: int = 0
    eval_duration_s: float = 0.0
    json_parse_ok: bool = False
    json_repair_used: bool = False
    n_chunks: int = 1
    error: str = ""

    @property
    def tokens_per_second(self) -> float:
        """Generation throughput -- the model-comparable speed measure."""
        if self.eval_duration_s <= 0:
            return 0.0
        return round(self.eval_count / self.eval_duration_s, 2)


# --------------------------------------------------------------------------
# JSON recovery
# --------------------------------------------------------------------------

def _salvage_json(text: str) -> tuple[list[dict] | None, bool]:
    """
    Recover a company list from imperfect model output.

    Returns (records, repair_was_needed). Small models wrap JSON in prose,
    fence it in markdown, or emit a bare array instead of the object we asked
    for -- all recoverable, and how often recovery is needed is a result we
    report rather than hide.
    """
    # Happy path: the whole response parses.
    try:
        return _coerce(json.loads(text)), False
    except (json.JSONDecodeError, TypeError):
        pass

    candidates: list[str] = []

    # ```json ... ``` fences
    candidates += re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)

    # CoT format: everything after ANSWER:
    if "ANSWER:" in text:
        candidates.append(text.split("ANSWER:", 1)[1])

    # First balanced {...} or [...] in the response.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    candidates.append(text[start:i + 1])
                    break

    for cand in candidates:
        try:
            return _coerce(json.loads(cand.strip())), True
        except (json.JSONDecodeError, TypeError):
            continue

    return None, True


# Fields the full-record schema may return. `name` is required; the rest are
# optional and default to an empty string.
RECORD_FIELDS = ("name", "url", "street", "postcode", "city", "phone", "email")


# Markdown link syntax the model sometimes wraps a URL in, and the angle
# brackets that annotate_links() writes into the page text. Observed live on
# profile pages: "[www.centech.de](https://www.centech.de)" was returned as the
# url field, which fails every downstream check and would reach the deliverable
# as unusable text. The model is copying the shape of what it was shown rather
# than making anything up, so this is cleaned rather than rejected.
_MD_LINK = re.compile(r"^\[([^\]]*)\]\(\s*([^)\s]+)\s*\)$")


def _clean_url(value: str) -> str:
    """Reduce whatever the model returned to a bare URL, or "" if it is not one."""
    v = value.strip().strip("<>").strip()
    m = _MD_LINK.match(v)
    if m:
        # Prefer the target; fall back to the label when the target is empty.
        v = (m.group(2) or m.group(1)).strip()
    v = v.strip("<>\"'` ").rstrip(".,;")
    if not v:
        return ""
    if v.startswith("//"):
        v = "https:" + v
    elif not v.startswith(("http://", "https://")):
        # "www.example.de" and "example.de" are both common; anything without
        # a dot is not a URL at all.
        if "." not in v.split("/")[0] or " " in v:
            return ""
        v = "https://" + v
    return v


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,10}$", re.I)

# "info (at) example (dot) de" and its bracketed variants. Written this way to
# keep an address out of a spam crawler's reach, which is also what defeats a
# plain text extractor.
_AT = re.compile(r"\s*[\(\[\{]\s*(?:at|ät)\s*[\)\]\}]\s*|\s+at\s+", re.I)
_DOT = re.compile(r"\s*[\(\[\{]\s*(?:dot|punkt)\s*[\)\]\}]\s*", re.I)


def _clean_email(value: str) -> str:
    """
    Undo the ways a page hides an email address from crawlers.

    Measured on the 30-page stage 3 output: of 331 addresses, 211 were
    already valid, **119 were written backwards** and 1 used "(at)". The
    reversed ones are the CSS trick, where the markup holds
    `ed.elpmaxe@ofni` and a stylesheet flips it so a reader sees
    `info@example.de`. The model reported exactly what the page contained,
    so this is a page convention to undo rather than a model error:

        ed.snorcim5@tkatnok   ->  kontakt@5microns.de
        moc.ameraa@ofni       ->  info@aarema.com
        hpi-info(at)hpi.de    ->  hpi-info@hpi.de

    Order matters. A valid address is returned untouched, so nothing that
    already works can be broken by this, and only a string that does not
    parse is ever rewritten.
    """
    s = (value or "").strip()
    if not s or _EMAIL.match(s):
        return s

    flipped = s[::-1]
    if _EMAIL.match(flipped):
        return flipped

    spelled = _DOT.sub(".", _AT.sub("@", s)).strip()
    if _EMAIL.match(spelled):
        return spelled

    # Reversal and spelling-out can be combined.
    spelled_flipped = _DOT.sub(".", _AT.sub("@", flipped)).strip()
    if _EMAIL.match(spelled_flipped):
        return spelled_flipped

    # Unrecognised: keep it rather than discard it. A human can still read a
    # malformed address; a blank cell tells nobody anything.
    return s


def _as_record(item) -> dict | None:
    """
    Normalise one returned entry into a record dict.

    Three shapes occur across the prompt strategies and must all be accepted,
    because the strategies are compared against each other and a parsing
    difference would show up as an accuracy difference:

        "Robert Bosch GmbH"                          bare string
        {"name": ..., "url": ...}                    name + website
        {"name": ..., "url": ..., "city": ..., ...}  full record
    """
    if isinstance(item, str):
        name = item.strip()
        return {"name": name} if name else None

    if not isinstance(item, dict):
        return None

    name = ""
    for key in ("name", "company", "Name", "company_name", "companyName"):
        if isinstance(item.get(key), str) and item[key].strip():
            name = item[key].strip()
            break
    if not name:
        return None

    rec = {"name": name}
    aliases = {
        "url": ("url", "website", "web", "homepage", "site"),
        "street": ("street", "address", "strasse", "straße"),
        "postcode": ("postcode", "zip", "plz", "postal_code", "postalCode"),
        "city": ("city", "ort", "town"),
        "phone": ("phone", "telephone", "tel", "telefon"),
        "email": ("email", "mail", "e_mail"),
    }
    for field, keys in aliases.items():
        for k in keys:
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                if field == "url":
                    value = _clean_url(v)
                elif field == "email":
                    value = _clean_email(v)
                else:
                    value = v.strip()
                if value:
                    rec[field] = value
                break
    return rec


def _coerce(obj) -> list[dict]:
    """Accept {"companies": [...]} or a bare [...] and normalise to records."""
    if isinstance(obj, dict):
        for key in ("companies", "Companies", "company_names", "names", "result"):
            if key in obj and isinstance(obj[key], list):
                obj = obj[key]
                break
        else:
            raise TypeError("no recognised list key in object")
    if not isinstance(obj, list):
        raise TypeError(f"expected list, got {type(obj).__name__}")

    out: list[dict] = []
    for item in obj:
        rec = _as_record(item)
        if rec:
            out.append(rec)
    return out


# --------------------------------------------------------------------------
# Inference
# --------------------------------------------------------------------------

def _thinking_off(model: str) -> bool:
    """True for models that must be told not to reason before answering."""
    return model.startswith(tuple(getattr(config, "THINKING_MODEL_PREFIXES", ())))


def _call_once(model: str, system: str, user: str, constrained: bool,
               schema: dict | None = None) -> tuple[str, dict, float]:
    """One model round trip. Returns (text, timing metadata, wall seconds)."""
    # "constructor/<model>" goes to the Constructor Model API, everything else
    # to Ollama. Prompts, schema and temperature are the same either way.
    if cloud_client.is_cloud(model):
        return cloud_client.call(model, system, user, constrained, schema)
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {
            "temperature": config.TEMPERATURE,
            "seed": config.SEED,
            "num_ctx": config.NUM_CTX,   # never rely on the 4096 default
            # Backstop against a repetition loop. Far above any honest reply
            # measured here, so it only ever truncates garbage.
            "num_predict": getattr(config, "NUM_PREDICT", 4096),
        },
        "keep_alive": config.KEEP_ALIVE,
    }
    if constrained:
        kwargs["format"] = schema or config.COMPANY_LIST_SCHEMA
    # Only for models that have a thinking mode. The other models' requests
    # stay byte-for-byte what they were when their results were measured.
    if _thinking_off(model):
        kwargs["think"] = False

    # A request with no deadline can wait forever. Observed live: a 16,000-word
    # profile page stalled a run for 19 minutes, the model unloaded underneath
    # it, and the client kept waiting on a connection that was never going to
    # answer. A hang is indistinguishable from slow work, which is the worst
    # property a long-running job can have, so _chat_streaming separates them.
    #
    # The clock starts fresh on the retry: latency_seconds is meant to be the
    # cost of the model's work, and a dead connection is not that. The retry is
    # printed rather than swallowed, so the log still shows it happened.
    for attempt in (1, 2):
        start = time.perf_counter()
        try:
            text, meta = _chat_streaming(kwargs)
            return text, meta, time.perf_counter() - start
        except _RETRY_ERRORS as exc:
            if attempt == 2:
                raise
            print(f"    ! {type(exc).__name__} after {time.perf_counter() - start:.0f}s"
                  f" on {model}, retrying once", flush=True)
            time.sleep(_RETRY_PAUSE_S)


def _run_multi_stage(chunk: str, model: str, constrained: bool,
                     result: ExtractionResult, strategy: str = "generic_multi_stage",
                     schema: dict | None = None) -> list[dict]:
    """
    Drive the three-call generic multi-stage strategy (guideline P3).

    locate -> extract -> validate. Timings from all three calls accumulate
    into `result`, so the reported latency is the true cost of the strategy
    rather than one call of it.
    """
    # -- Stage 1: locate the list -------------------------------------------
    hint = ""
    system, user = prompts.multi_stage_locate(chunk)
    try:
        text, meta, elapsed = _call_once(model, system, user, constrained=False)
        result.latency_seconds += elapsed
        result.prompt_eval_count += meta.get("prompt_eval_count", 0) or 0
        result.eval_count += meta.get("eval_count", 0) or 0
        result.eval_duration_s += (meta.get("eval_duration", 0) or 0) / 1e9
        hint = text.strip()[:500]
    except Exception as exc:
        # Locating is advisory; extraction can still proceed without it.
        result.error = f"stage1: {type(exc).__name__}"[:120]

    # -- Stage 2: extract ---------------------------------------------------
    # The record variant differs only here; locating and validating are
    # unchanged, so the two multi-stage strategies stay comparable.
    if strategy in prompts.RECORD_STRATEGIES:
        system, user = prompts.multi_stage_extract_record(chunk, hint)
    else:
        system, user = prompts.multi_stage_extract(chunk, hint)
    try:
        text, meta, elapsed = _call_once(model, system, user, constrained, schema)
    except Exception as exc:
        result.error = f"stage2: {exc}"[:300]
        return []

    result.latency_seconds += elapsed
    result.prompt_eval_count += meta.get("prompt_eval_count", 0) or 0
    result.eval_count += meta.get("eval_count", 0) or 0
    result.eval_duration_s += (meta.get("eval_duration", 0) or 0) / 1e9

    names, repaired = _salvage_json(text)
    if names is None:
        result.error = result.error or "stage2: unparseable JSON"
        return []
    result.json_parse_ok = True
    result.json_repair_used = result.json_repair_used or repaired

    if not names:
        return []

    # -- Stage 3: validate --------------------------------------------------
    system, user = prompts.multi_stage_validate(names)
    try:
        text, meta, elapsed = _call_once(model, system, user, constrained)
        result.latency_seconds += elapsed
        result.prompt_eval_count += meta.get("prompt_eval_count", 0) or 0
        result.eval_count += meta.get("eval_count", 0) or 0
        result.eval_duration_s += (meta.get("eval_duration", 0) or 0) / 1e9

        validated, repaired = _salvage_json(text)
        if validated is not None:
            result.json_repair_used = result.json_repair_used or repaired
            # Validation may only remove, never invent: anything the third
            # stage "adds" is a hallucination, so intersect with stage 2.
            # Filter the stage-2 records by what validation approved, rather
            # than returning validation's own output. Stage 3 is asked for
            # names only, so returning its records would silently discard the
            # website and address fields stage 2 found.
            allowed = {v["name"].casefold() for v in validated}
            kept = [r for r in names if r["name"].casefold() in allowed]
            return kept or names
    except Exception as exc:
        result.error = result.error or f"stage3: {type(exc).__name__}"[:120]

    return names


def extract(
    chunks: list[str],
    model: str,
    strategy: str = "few_shot_schema",
    json_mode: str = "constrained",
) -> ExtractionResult:
    """
    Extract company names from one page's chunks.

    `chunks` comes from cleaner.process(...).chunks -- a single-element list
    for pages that fit the context window.
    """
    result = ExtractionResult(n_chunks=len(chunks))

    # CoT needs to emit prose before its JSON; constrained decoding would
    # forbid that and silently degrade it into a slower zero-shot.
    constrained = (
        json_mode == "constrained"
        and strategy not in prompts.INCOMPATIBLE_WITH_CONSTRAINED
    )
    # A record-returning strategy needs the object schema; forcing the plain
    # string schema on it would discard every field except the name.
    schema = (config.COMPANY_RECORD_SCHEMA
              if strategy in prompts.RECORD_STRATEGIES
              else config.COMPANY_LIST_SCHEMA)

    seen: set[str] = set()
    raw_parts: list[str] = []

    for chunk in chunks:
        # Multi-stage needs three calls per chunk, so it takes its own path.
        if strategy in prompts.MULTI_STAGE:
            for rec in _run_multi_stage(chunk, model, constrained, result,
                                        strategy, schema):
                key = rec["name"].casefold()
                if key not in seen:
                    seen.add(key)
                    result.companies.append(rec["name"])
                    result.records.append(rec)
            continue

        system, user = prompts.build(strategy, chunk)

        try:
            text, meta, elapsed = _call_once(model, system, user, constrained,
                                             schema)
        except ollama.ResponseError as exc:
            result.error = f"ollama: {exc}"[:300]
            continue
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"[:300]
            continue

        result.latency_seconds += elapsed
        result.prompt_eval_count += meta.get("prompt_eval_count", 0) or 0
        result.eval_count += meta.get("eval_count", 0) or 0
        # Ollama reports durations in nanoseconds.
        result.eval_duration_s += (meta.get("eval_duration", 0) or 0) / 1e9
        raw_parts.append(text)

        companies, repaired = _salvage_json(text)
        if companies is None:
            result.error = (result.error or "unparseable JSON")
            continue

        result.json_parse_ok = True
        result.json_repair_used = result.json_repair_used or repaired

        # Union across chunks; the overlap window means duplicates are normal.
        for rec in companies:
            key = rec["name"].casefold()
            if key not in seen:
                seen.add(key)
                result.companies.append(rec["name"])
                result.records.append(rec)

    result.latency_seconds = round(result.latency_seconds, 3)
    result.raw_output = json.dumps(raw_parts, ensure_ascii=False)[:20000]
    return result


if __name__ == "__main__":
    import sys
    from pathlib import Path

    import cleaner

    path = Path(sys.argv[1])
    model = sys.argv[2] if len(sys.argv) > 2 else config.MODELS[0]
    strategy = sys.argv[3] if len(sys.argv) > 3 else "few_shot_schema"

    page = cleaner.process(path.read_text(encoding="utf-8", errors="ignore"))
    print(f"page: {page.word_count} words, ~{page.est_tokens} tokens, "
          f"{page.n_chunks} chunk(s)")

    res = extract(page.chunks, model, strategy)
    print(f"model={model} strategy={strategy}")
    print(f"latency={res.latency_seconds}s  tok/s={res.tokens_per_second}  "
          f"parsed={res.json_parse_ok} repaired={res.json_repair_used}")
    print(f"found {len(res.companies)}:")
    for rec in res.records[:40]:
        extra = "  ".join(f"{k}={rec[k]}" for k in
                          ("url", "street", "postcode", "city", "phone", "email")
                          if rec.get(k))
        print(f"    {rec['name'][:44]:<46}{extra[:70]}")
    if res.error:
        print("error:", res.error)
