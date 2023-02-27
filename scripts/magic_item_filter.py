import json
import re

RARITY_RE = re.compile("\Wcommon\W")


def run():
    with open("../data/magic-items.json") as f:
        items = json.load(f)
    for item in items:
        if item["isLegacy"]:
            continue
        if RARITY_RE.search(item["meta"]):
            print(f'{item["name"]}, {item["source"]}')


if __name__ == "__main__":
    run()
