"""
Use this script to manually generate some prompts.
"""

import pathlib
import random
import sys

from rapidfuzz import fuzz, process

sys.path.append("..")

from calypso.cogs.encounters import ai
from calypso.gamedata import GamedataRepository
from calypso.utils import natural_join

PROJECT_ROOT = pathlib.Path(__file__).parents[1]


class RolledEncounterDuck:
    biome_name = "BIOME_NAME"
    biome_text = "BIOME_TEXT"

    def __init__(self, monsters):
        self.rendered_text_nolinks = natural_join([m.name for m in monsters], "and")


def run():
    GamedataRepository.reload()
    all_mnames = [m.name for m in GamedataRepository.monsters]
    while True:
        names = input("Enter monsters, comma separated: ")
        if names:
            names = names.split(",")
            monsters = []
            for mname in names:
                choice, score, idx = process.extractOne(mname.strip(), all_mnames, scorer=fuzz.ratio)
                monsters.append(GamedataRepository.monsters[idx])
        else:
            n = random.randrange(4)
            monsters = random.sample(GamedataRepository.monsters, n)
        print("===== PROMPT =====")
        # noinspection PyTypeChecker
        print(ai.summary_prompt_2(RolledEncounterDuck(monsters), monsters))
        print("==================\n")


if __name__ == "__main__":
    run()
