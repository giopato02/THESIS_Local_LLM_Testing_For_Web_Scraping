"""
Check a model before giving it a whole grid.

Three things that each wasted hours when they went unchecked:

  1. Is it on the GPU? Ollama falls back to CPU silently.
  2. Is thinking really off? A qwen3.x model that reasons before answering is
     slow, and the reasoning would be timed as extraction.
  3. Does it answer a tiny extraction request correctly, and how fast?

It sends the same request through extractor._call_once that the benchmark
uses, so a pass here means the benchmark's own call path works.

Run:  .venv/bin/python check_model.py qwen3.5:9b
"""

from __future__ import annotations

import subprocess
import sys

import extractor

SYSTEM = "You extract company names from web pages. Answer with JSON only."
PAGE = ("Mitglieder\n"
        "Alpha Maschinenbau GmbH\n12345 Berlin\nWeb <https://www.alpha.de>\n"
        "Beta Sensorik AG\n80331 München\nWeb <https://www.beta-sensorik.de>\n")
USER = ('Return {"companies": [{"name": "..."}]} listing every member company '
        "on this page:\n\n" + PAGE)
EXPECTED = ("Alpha Maschinenbau GmbH", "Beta Sensorik AG")


def thinking_text(meta: dict) -> str:
    msg = meta.get("message")
    if msg is None:
        return ""
    if isinstance(msg, dict):
        return msg.get("thinking") or ""
    return getattr(msg, "thinking", None) or ""


def main() -> None:
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.5:9b"
    off = extractor._thinking_off(model)
    print(f"model: {model}   thinking switched off by the pipeline: {off}")

    problems = []
    for label in ("first call (includes loading the model)", "second call (warm)"):
        text, meta, secs = extractor._call_once(model, SYSTEM, USER,
                                                constrained=False)
        thought = thinking_text(meta)
        print(f"\n{label}: {secs:.1f} s, {meta.get('eval_count')} output tokens")
        print(f"  thinking returned: {len(thought)} characters"
              f"{'  <-- should be 0' if off and thought else ''}")
        print(f"  answer: {' '.join(text.split())[:220]}")
        if off and (thought or "<think>" in text):
            problems.append("the model is still thinking")
        missing = [n for n in EXPECTED if n not in text]
        if missing:
            problems.append(f"answer is missing {missing}")

    import cloud_client
    if cloud_client.is_cloud(model):
        where = "reachable in the cloud"
        print("\ncloud model: it runs on Constructor's servers, no GPU to check")
    else:
        where = "on the GPU"
        ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout
        print("\n" + ps.strip())
        line = next((ln for ln in ps.splitlines() if ln.startswith(model)), "")
        if "100% GPU" not in line:
            problems.append("ollama ps does not show 100% GPU for this model")

    if problems:
        print("\nNOT READY:")
        for p in dict.fromkeys(problems):
            print(f"  - {p}")
        sys.exit(1)
    print(f"\nREADY: {where}, not thinking, correct answer.")


if __name__ == "__main__":
    main()
