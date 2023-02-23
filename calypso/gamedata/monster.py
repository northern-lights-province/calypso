import logging
import re
from functools import cached_property
from typing import Optional, Union

from automation_common.validation.models import AttackModel
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


# ==== monster description ====
class MonsterDescription(BaseModel):
    monster_id: int
    monster_name: str
    characteristics: Optional[str]
    long: Optional[str]
    long2: Optional[str]
    lair: Optional[str]


# ==== monster ====
class AbilityScores(BaseModel):
    prof_bonus: int
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    def __getitem__(self, item):
        return getattr(self, item)


class Skill(BaseModel):
    value: int
    prof: Optional[int]
    bonus: Optional[int]


class Saves(BaseModel):
    strengthSave: Skill
    dexteritySave: Skill
    constitutionSave: Skill
    intelligenceSave: Skill
    wisdomSave: Skill
    charismaSave: Skill

    def __getitem__(self, item) -> Skill:
        return getattr(self, item)


class Skills(BaseModel):
    acrobatics: Skill
    animalHandling: Skill
    arcana: Skill
    athletics: Skill
    deception: Skill
    history: Skill
    initiative: Skill
    insight: Skill
    intimidation: Skill
    investigation: Skill
    medicine: Skill
    nature: Skill
    perception: Skill
    performance: Skill
    persuasion: Skill
    religion: Skill
    sleightOfHand: Skill
    stealth: Skill
    survival: Skill
    strength: Skill
    dexterity: Skill
    constitution: Skill
    intelligence: Skill
    wisdom: Skill
    charisma: Skill

    def __getitem__(self, item) -> Skill:
        return getattr(self, item)


class Resistance(BaseModel):
    dtype: str
    unless: Optional[list[str]]
    only: Optional[list[str]]


class Resistances(BaseModel):
    resist: list[Union[str, Resistance]]
    immune: list[Union[str, Resistance]]
    vuln: list[Union[str, Resistance]]

    def __getitem__(self, item) -> list[Union[str, Resistance]]:
        return getattr(self, item)


class MonsterFeature(BaseModel):
    name: str
    desc: str


class SpellbookSpell(BaseModel):
    name: str
    strict: bool
    dc: Optional[int]
    sab: Optional[int]
    mod: Optional[int]


DailySpells = dict[str, int]


class Spellbook(BaseModel):
    slots: dict[str, int]
    max_slots: dict[str, int]
    spells: list[SpellbookSpell]
    dc: Optional[int]
    sab: Optional[int]
    caster_level: int
    spell_mod: Optional[int]
    at_will: list[str]
    daily: DailySpells


class Monster(BaseModel):
    id: int
    name: str
    size: str
    race: str
    alignment: str
    ac: int
    armortype: str
    hp: int
    hitdice: str
    speed: str
    ability_scores: AbilityScores
    saves: Saves
    skills: Skills
    senses: str
    passiveperc: int
    display_resists: Resistances
    condition_immune: list[str]
    languages: list[str]
    cr: str
    hide_cr: Optional[bool]
    xp: int
    traits: list[MonsterFeature]
    actions: list[MonsterFeature]
    reactions: list[MonsterFeature]
    legactions: list[MonsterFeature]
    mythic_actions: list[MonsterFeature] = []
    bonus_actions: list[MonsterFeature] = []
    la_per_round: int
    image_url: Optional[str]
    spellbook: Optional[Spellbook]
    resistances: Resistances
    token_free: Optional[str]
    token_sub: Optional[str]
    attacks: list[AttackModel]
    proper: bool

    source: str
    is_free: bool = Field(alias="isFree")
    page: Optional[int]
    url: Optional[str]
    entitlement_entity_type: Optional[str] = Field(alias="entitlementEntityType")
    entitlement_entity_id: Optional[int] = Field(alias="entitlementEntityId")
    is_legacy: bool = Field(False, alias="isLegacy")

    class Config:
        keep_untouched = (cached_property,)

    @cached_property
    def name_re(self) -> re.Pattern:
        return re.compile(rf"\b{re.escape(self.name)}", re.IGNORECASE)


def xp_by_cr(cr):
    return {
        "0": 10,
        "1/8": 25,
        "1/4": 50,
        "1/2": 100,
        "1": 200,
        "2": 450,
        "3": 700,
        "4": 1100,
        "5": 1800,
        "6": 2300,
        "7": 2900,
        "8": 3900,
        "9": 5000,
        "10": 5900,
        "11": 7200,
        "12": 8400,
        "13": 10000,
        "14": 11500,
        "15": 13000,
        "16": 15000,
        "17": 18000,
        "18": 20000,
        "19": 22000,
        "20": 25000,
        "21": 33000,
        "22": 41000,
        "23": 50000,
        "24": 62000,
        "25": 75000,
        "26": 90000,
        "27": 105000,
        "28": 120000,
        "29": 135000,
        "30": 155000,
    }.get(cr, 0)
