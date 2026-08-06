#!/usr/bin/env python3
"""
Dragoncon 2026 registration watcher.

Checks a few event pages on dragoncon.co.il for the sentence that appears
at the bottom of every event page while early registration hasn't opened:

    "הרישום המוקדם לכנס טרם התחיל, המתינו להודעות בנושא בקרוב."

No login is required to see this text. Once early registration opens,
this sentence disappears from the event pages.

To avoid a false alarm because a single page glitched, changed, or 404'd,
this script requires the marker to be missing on EVERY page it successfully
fetched before declaring registration "open". If it couldn't fetch any page
at all, it does nothing (fails safe).

State is persisted to state.json so we only fire the notification once,
on the transition from "closed" to "open".
"""

import json
import sys
import urllib.request

# A handful of different event pages, so one odd/removed page doesn't
# trigger a false positive.
EVENT_URLS = [
    "https://dragoncon.co.il/events/288",
    "https://dragoncon.co.il/events/305",
    "https://dragoncon.co.il/events/350",
]

MARKER = "הרישום המוקדם לכנס טרם התחיל"
STATE_FILE = "state.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DragonconWatcher/1.0)"}
TIMEOUT_SECONDS = 20


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return resp.read().decode("utf-8", errors="replace")


def marker_present(html: str) -> bool:
    return MARKER in html


def check_all() -> list[bool]:
    """Returns a list of booleans (marker present?) for every page that
    was fetched successfully. Pages that fail to fetch are skipped."""
    results = []
    for url in EVENT_URLS:
        try:
            html = fetch(url)
            present = marker_present(html)
            results.append(present)
            print(f"  {url} -> marker present: {present}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {url} -> FAILED to fetch ({exc}), skipping this page", file=sys.stderr)
    return results


def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"open": False}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main() -> None:
    state = load_state()
    print("Checking dragoncon.co.il event pages...")
    results = check_all()

    if not results:
        print("ERROR: could not fetch ANY event page this run. Skipping (fail-safe, no alert).")
        return

    # "Open" only if the marker is absent on every page we managed to check.
    currently_open = not any(results)
    print(f"Fetched {len(results)}/{len(EVENT_URLS)} page(s) successfully. "
          f"Registration currently open: {currently_open}")

    was_open = state.get("open", False)

    if currently_open and not was_open:
        print("NOTIFY_OPEN")  # picked up by the GitHub Actions workflow step
        state["open"] = True
        save_state(state)
    elif not currently_open and was_open:
        # Edge case: site reverted back (shouldn't normally happen). Reset state.
        print("Marker reappeared; resetting state to closed.")
        state["open"] = False
        save_state(state)
    else:
        save_state(state)


if __name__ == "__main__":
    main()
