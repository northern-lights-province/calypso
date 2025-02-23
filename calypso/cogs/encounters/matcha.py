"""
Helpers to extract mentioned monsters from rolled encounters and link them to gamedata entities.
🍵
"""

import logging
import re
from typing import NamedTuple

from calypso import gamedata

log = logging.getLogger(__name__)


class MonsterMatch(NamedTuple):
    monster: gamedata.Monster
    match: re.Match


def extract_monsters(text) -> list[MonsterMatch]:
    """
    Given a string possibly containing monster names, returns a list of pairs (monster, positions)
    where `positions` are the indexes of `text` where the monster name was found.
    Sorted by length of monster name, descending.
    """
    log.debug(f"Finding monsters for encounter {text!r}")

    matches = []

    potential_matches = find_potential_matches(text)
    if not potential_matches:
        log.info(f"No matches found for {text!r}")
    while potential_matches:
        best_match = potential_matches.pop(0)
        matches.append(best_match)
        re_match = best_match.match
        log.debug(f"\tMatch: {re_match[0]!r}")

        # replace matches with empty space to keep pos
        match_len = len(re_match[0])
        text = text[: re_match.start()] + " " * match_len + text[re_match.start() + match_len :]

        log.debug(f"\tNext iteration: {text!r}")
        # remove the matches that no longer match
        for match in reversed(potential_matches):
            if match.match.start() == re_match.start() and not match.monster.name_re.match(text, re_match.start()):
                potential_matches.remove(match)

    return matches


def find_potential_matches(query: str) -> list[MonsterMatch]:
    """
    Find all potential monsters mentioned in `query`
    Returns a list of MonsterMatches sorted by match length descending
    """
    matches = []
    for monster in gamedata.GamedataRepository.monsters:
        # if monster.is_legacy:
        #     continue
        for mon_match in monster.name_re.finditer(query):
            matches.append(MonsterMatch(monster, mon_match))
    return sorted(matches, key=lambda m: (len(m.match[0]), not m.monster.is_legacy), reverse=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    gamedata.GamedataRepository.reload()
    test_str = "an Ancient Red Dragon (2014) and an Ancient Red Dragon (2024) and 3 Skeletons and a Dire Wolf (2024)"
    referenced_monsters = extract_monsters(test_str)
    for mon, match in sorted(referenced_monsters, key=lambda p: p[1].start(), reverse=True):
        test_str = test_str[: match.start()] + f"[{match[0]}]({mon.url})" + test_str[match.end() :]
    print(test_str)
