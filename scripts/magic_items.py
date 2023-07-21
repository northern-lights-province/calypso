import csv
import json
import re

RARITY_RE = re.compile("\Wvery\Wrare\W")


def rarity_filter():
    with open("../data/magic-items.json") as f:
        items = json.load(f)
    for item in items:
        if item["isLegacy"]:
            continue
        if RARITY_RE.search(item["meta"]):
            print(f'"{item["name"]}"; {item["source"]}')


def csv_to_json():
    default_cost = 50
    default_days = 5
    out = []
    with open("../data/Magic Items - Common.csv") as f:
        reader = csv.DictReader(f, ("name", "source", "cost", "days", "restrictions", "comment"))
        next(reader)
        for item in reader:
            item["cost"] = int(item["cost"] or default_cost)
            item["days"] = int(item["days"] or default_days)
            item["restrictions"] = item["restrictions"] or None
            item["comment"] = item["comment"] or None
            if item["restrictions"] in ("Banned", "Restricted", "Community Goal"):
                continue
            out.append(item)
    with open("../data/crafting-magic-items-common.json", "w") as f:
        json.dump(out, f)


if __name__ == "__main__":
    rarity_filter()
