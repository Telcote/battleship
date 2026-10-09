import os
import sys
import time

import httpx

ARENA_URL = os.environ.get("ARENA_URL", "http://localhost:8100")
HONEST_URL = os.environ.get("HONEST_URL", "http://app:8000")
ROGUE_URL = os.environ.get("ROGUE_URL", "http://rogue:8200")

EXPECTED = {
    "honest": "fleet_destroyed",
    "liar": "lie",
    "nonsense": "unavailable",
    "slow": "timeout",
    "drip": "timeout",
    "crash": "unavailable",
    "malformed": "unavailable",
    "touching": "invalid_placement",
    "garbage": "invalid_shot",
    "repeat": "invalid_shot",
}
POLL_SECONDS = 60


def main() -> int:
    arena = httpx.Client(base_url=ARENA_URL, timeout=5)
    matches = {}
    for mode in EXPECTED:
        body = {"players": [{"base_url": HONEST_URL}, {"base_url": f"{ROGUE_URL}/{mode}"}]}
        response = arena.post("/match", json=body)
        response.raise_for_status()
        matches[mode] = response.json()["match_id"]

    deadline = time.monotonic() + POLL_SECONDS
    results = {}
    while matches.keys() - results.keys() and time.monotonic() < deadline:
        for mode, match_id in matches.items():
            if mode not in results:
                match = arena.get(f"/match/{match_id}").json()
                if match["status"] == "finished":
                    results[mode] = match
        time.sleep(0.5)

    failures = 0
    for mode, expected in EXPECTED.items():
        match = results.get(mode)
        if match is None:
            print(f"FAIL  {mode:<10} match did not finish in {POLL_SECONDS}s")
            failures += 1
            continue
        result = match["result"]
        rogue = match["players"][1]["address"]
        ok = result["reason"] == expected and (mode == "honest" or result["loser"] == rogue)
        failures += not ok
        detail = result["detail"].splitlines()[0]
        print(f"{'ok' if ok else 'FAIL':<5} {mode:<10} {result['reason']:<18} {detail}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
