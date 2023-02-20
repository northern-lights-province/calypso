"""
For each encounter in the random encounter tables, find the monster IDs associated with them.
"""
import json
import logging
import pathlib
import re
import sys

sys.path.append("..")

from calypso.cogs.encounters.client import EncounterClient, EncounterRepository

PROJECT_ROOT = pathlib.Path(__file__).parents[1]


class Matcha:  # 🍵
    def __init__(self):
        self.eclient = EncounterClient()
        self.monsters = []

    def load_data(self):
        self.eclient.refresh_encounters_sync()

        with open(PROJECT_ROOT / "data/monsters.json") as f:
            monsters = json.load(f)
        self.monsters.clear()
        # remove legacy monsters and compile regex
        for m in monsters:
            if m.get("isLegacy"):
                continue
            m["name_re"] = re.compile(rf"\b{m['name']}", re.IGNORECASE)
            self.monsters.append(m)

    def match(self):
        # for each encounter, fuzzy match on monster names
        for encounter in EncounterRepository.all_encounters():
            self.extract_monsters(encounter.text)

    def extract_monsters(self, text):
        logging.debug(f"Finding monsters for encounter {text!r}")
        result_ids = set()

        # find the best match that is aligned with the start of a word, sorted by match length desc
        matches = self.find_matches(text)
        if not matches:
            logging.info(f"No matches found for {text!r}")
        while matches:
            monster, poses = matches[0]
            logging.debug(f"\tMatch: {monster['name']!r}")

            text = text.replace(monster["name"], " " * len(monster["name"]))  # to keep pos
            result_ids.add(monster["id"])

            logging.debug(f"\tNext iteration: {text!r}")
            matches = self.find_matches(text, result_ids)

    def find_matches(self, query: str, ignore: set[int] = None):
        """
        Find the monsters that are mentioned in `query`, whose ids are not in `ignore`
        -> [(monster, poses)], sorted by monster name length desc
        """
        if ignore is None:
            ignore = set()

        matches = []
        for monster in self.monsters:
            if monster["id"] in ignore:
                continue
            mon_matches = []
            for mon_match in monster["name_re"].finditer(query):
                mon_matches.append(mon_match.pos)
            if mon_matches:
                matches.append((monster, mon_matches))
        return sorted(matches, key=lambda pair: len(pair[0]["name"]), reverse=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    matcher = Matcha()
    matcher.load_data()
    matcher.match()
