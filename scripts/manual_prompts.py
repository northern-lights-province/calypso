"""
Use this script to manually generate some prompts.
"""
import pathlib
import sys

from rapidfuzz import fuzz, process

sys.path.append("..")

from calypso.cogs.encounters import ai
from calypso.gamedata import GamedataRepository

PROJECT_ROOT = pathlib.Path(__file__).parents[1]


class RolledEncounterDuck:
    biome_name = "BIOME_NAME"
    biome_text = "BIOME_TEXT"


def run():
    GamedataRepository.reload()
    all_mnames = [m.name for m in GamedataRepository.monsters]
    while True:
        names = input("Enter monsters, comma separated: ").split(",")
        monsters = []
        for mname in names:
            choice, score, idx = process.extractOne(mname.strip(), all_mnames, scorer=fuzz.ratio)
            monsters.append(GamedataRepository.monsters[idx])
        print("===== PROMPT =====")
        # noinspection PyTypeChecker
        print(ai.summary_prompt(RolledEncounterDuck(), monsters))
        print("==================\n")


if __name__ == "__main__":
    run()
