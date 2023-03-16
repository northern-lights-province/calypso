"""
For each encounter in the random encounter tables, find the monster IDs associated with them.
"""
import logging
import pathlib
import sys

sys.path.append("..")

from calypso.cogs.encounters.client import EncounterClient, EncounterRepository
from calypso.cogs.encounters.matcha import extract_monsters
from calypso.gamedata import GamedataRepository

PROJECT_ROOT = pathlib.Path(__file__).parents[1]


class Matcha:  # 🍵
    def __init__(self):
        self.eclient = EncounterClient()
        self.monsters = []

    def load_data(self):
        self.eclient.refresh_encounters_sync()
        GamedataRepository.reload()

    def match(self):
        # for each encounter, fuzzy match on monster names
        for encounter in EncounterRepository.all_encounters():
            extract_monsters(encounter.text)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    matcher = Matcha()
    matcher.load_data()
    matcher.match()
