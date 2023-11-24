"""
Find statistics about the length of monster descriptions (not including stat blocks).
"""

import itertools
import logging
import pathlib
import sys
from collections import Counter

sys.path.append("..")

from calypso.gamedata import GamedataRepository
from calypso.cogs.encounters.ai import creature_desc

PROJECT_ROOT = pathlib.Path(__file__).parents[1]


def run():
    lens = []
    lens_with_ability = []
    GamedataRepository.reload()
    for monster in GamedataRepository.monsters:
        desc = creature_desc(monster)
        desc_len = len(desc.split())
        lens.append(desc_len)
        ability_len = sum(
            len(f.name.split()) + len(f.desc.split())
            for f in itertools.chain(
                monster.traits,
                monster.actions,
                monster.bonus_actions,
                monster.reactions,
                monster.legactions,
                monster.mythic_actions,
            )
        )
        lens_with_ability.append(desc_len + ability_len)
    lens_counter = Counter(lens)

    print(f"avg len (words): {sum(lens) / len(lens)}")
    print(f"min len (words): {min(lens)}")
    print(f"max len (words): {max(lens)}")

    print(f"ability avg len (words): {sum(lens_with_ability) / len(lens_with_ability)}")
    print(f"ability min len (words): {min(lens_with_ability)}")
    print(f"ability max len (words): {max(lens_with_ability)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
