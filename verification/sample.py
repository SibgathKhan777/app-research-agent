"""Stratified review sample: 2 apps per category, fixed seed.

The sample is drawn from apps.yaml only (never from results), so it cannot be
biased toward apps the agent got right or wrong.

python -m verification.sample      -> writes verification/sample.json
"""
import json
import random
from collections import defaultdict

from research import config

SEED = 20261123
PER_CATEGORY = 2
OUT = config.ROOT / "verification" / "sample.json"


def draw() -> list[str]:
    by_cat = defaultdict(list)
    for a in config.load_apps():
        by_cat[a["category"]].append(a["id"])
    rng = random.Random(SEED)
    picked = []
    for cat in sorted(by_cat):
        picked += sorted(rng.sample(sorted(by_cat[cat]), PER_CATEGORY))
    return picked


if __name__ == "__main__":
    ids = draw()
    OUT.write_text(json.dumps({"seed": SEED, "per_category": PER_CATEGORY, "ids": ids}, indent=1))
    names = {a["id"]: (a["n"], a["name"], a["category"]) for a in config.load_apps()}
    for i in ids:
        print(*names[i], sep=" | ")
