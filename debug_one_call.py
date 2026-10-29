"""
Ask one model one question again, and print what it actually replied.

Needed because the benchmark saves the names it parsed, not the text the
model typed:

    "raw": result.companies,

So when a reply fails to parse there is nothing left to look at. Every
conclusion about WHY a model failed is then inference from token counts,
which is how a wrong explanation gets written down. This re-runs a single
call and shows the reply, so the explanation comes from the text.

Written for the qwen3.5:9b failures on the 30-page names grid: 84 runs
returned unreadable output, all of them on five pages (005, 050, 079, 082,
088), every strategy and every mode, while llama handled the same pages.
Token counts ruled out the context window (about 5,400 per call against a
limit of 8,192), so the cause is the shape of the reply.

Run it when nothing else is using the GPU: it loads a model.

    .venv/bin/python debug_one_call.py 050 qwen3.5:9b
    .venv/bin/python debug_one_call.py 050 qwen3.5:9b --strategy few_shot_schema
    .venv/bin/python debug_one_call.py 050 llama3.1:8b --json-mode prompt_only
"""

from __future__ import annotations

import argparse
import csv

import cleaner
import config
import extractor
import fetcher
import prompts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url_id")
    ap.add_argument("model")
    ap.add_argument("--strategy", default="zero_shot")
    ap.add_argument("--json-mode", default="constrained",
                    choices=["constrained", "prompt_only"])
    ap.add_argument("--chunk", type=int, default=0,
                    help="only this chunk (1-based); default is all of them")
    ap.add_argument("--chars", type=int, default=600,
                    help="how much of an unreadable reply to print from each end")
    args = ap.parse_args()

    with open(config.URLS_CSV, encoding="utf-8") as fh:
        row = {r["id"]: r for r in csv.DictReader(fh)}[args.url_id]
    html = fetcher.cache_path(row["url"]).read_text(encoding="utf-8", errors="ignore")
    page = cleaner.process(html, row["url"])

    constrained = (args.json_mode == "constrained"
                   and args.strategy not in prompts.INCOMPATIBLE_WITH_CONSTRAINED)
    schema = (config.COMPANY_RECORD_SCHEMA
              if args.strategy in prompts.RECORD_STRATEGIES
              else config.COMPANY_LIST_SCHEMA)

    print(f"  {args.url_id}  {row['org_name']}")
    print(f"  {page.n_chunks} chunks, {page.word_count} words")
    print(f"  {args.model} / {args.strategy} / {args.json_mode}"
          f"{'' if constrained else '  (constrained not applicable)'}\n")

    for i, chunk in enumerate(page.chunks, start=1):
        if args.chunk and i != args.chunk:
            continue
        system, user = prompts.build(args.strategy, chunk)
        text, meta, secs = extractor._call_once(
            args.model, system, user, constrained=constrained, schema=schema)
        names, repaired = extractor._salvage_json(text)

        state = "UNREADABLE" if names is None else ("repaired" if repaired else "clean")
        print(f"  --- chunk {i} of {page.n_chunks}: {state}")
        print(f"      {secs:.0f}s, {len(text)} characters, "
              f"read {meta.get('prompt_eval_count')} wrote {meta.get('eval_count')} tokens")
        # A truncated reply and a reply in the wrong shape look identical in
        # the counts and completely different in the text, so print both ends:
        # truncation shows as a reply that simply stops mid-token.
        if names is None:
            print(f"\n      FIRST {args.chars} CHARACTERS")
            print(text[:args.chars])
            print(f"\n      LAST {args.chars} CHARACTERS")
            print(text[-args.chars:])
            print(f"\n      ends with: {text[-1]!r}   "
                  f"balanced braces: {text.count('{') == text.count('}')}   "
                  f"balanced brackets: {text.count('[') == text.count(']')}")
        else:
            print(f"      {len(names)} names, first: {names[0]}")
        print()


if __name__ == "__main__":
    main()
