"""
One-time setup for cloud runs through the Constructor Model API.

    python constructor_setup.py models    list the model names you can use
    python constructor_setup.py km        find or create the knowledge model
                                          and print its ID

Needs CONSTRUCTOR_API_KEY in the environment. Never prints the key.
Then check one model before a whole grid:

    python check_model.py constructor/gemini-3.6-flash
"""

from __future__ import annotations

import os
import sys

import cloud_client

KM_NAME = "neohub-extraction"


def _session():
    import requests
    if not os.environ.get("CONSTRUCTOR_API_KEY"):
        sys.exit("Set CONSTRUCTOR_API_KEY first (see READ_ME_FIRST.md).")
    s = requests.Session()
    s.headers["X-KM-AccessKey"] = "Bearer " + os.environ["CONSTRUCTOR_API_KEY"]
    return s


def _get(s, path: str) -> dict:
    r = s.get(cloud_client.API_URL + path, timeout=60)
    if r.status_code != 200:
        sys.exit(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def list_models() -> None:
    results = _get(_session(), "/language_models")["results"]
    seen = set()
    for m in results:
        if m["alias"] in seen:
            continue
        seen.add(m["alias"])
        print(f"  {m['hosted_by']['name']:<12} {cloud_client.PREFIX}{m['alias']}")
    print(f"\n{len(seen)} models. Use the name in the second column with "
          f"--models, e.g. {cloud_client.PREFIX}gemini-3.6-flash")


def knowledge_model() -> None:
    s = _session()
    existing = [km for km in _get(s, "/knowledge-models")["results"]
                if km.get("name") == KM_NAME]
    if existing:
        km_id = existing[0]["id"]
        print(f"found knowledge model '{KM_NAME}'")
    else:
        r = s.post(cloud_client.API_URL + "/knowledge-models", timeout=60,
                   json={"name": KM_NAME, "shared_type": "private"})
        if r.status_code not in (200, 201):
            sys.exit(f"HTTP {r.status_code}: {r.text[:300]}")
        km_id = r.json()["id"]
        print(f"created knowledge model '{KM_NAME}'")

    # A knowledge model can carry its own instructions, which would be added to
    # every prompt and make the comparison with the local models unfair.
    settings = _get(s, f"/knowledge-models/{km_id}/settings")
    if settings.get("system_message"):
        print("WARNING: this knowledge model has its own system message:")
        print(f"  {settings['system_message']}")

    print(f"\nID: {km_id}\n")
    print("Set it in the same terminal before running anything:")
    print(f'  Windows PowerShell:  $env:CONSTRUCTOR_KM_ID = "{km_id}"')
    print(f'  macOS / Linux:       export CONSTRUCTOR_KM_ID="{km_id}"')


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "models":
        list_models()
    elif command == "km":
        knowledge_model()
    else:
        print(__doc__)
