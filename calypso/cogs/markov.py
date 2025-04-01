import json
import random
import re

import disnake
import markovify
from disnake.ext import commands

from calypso.gamedata import DATA_DIR


class SpellText(markovify.Text):
    def sentence_split(self, text):
        return re.split(r"\s*\n\n\n\n\s*", text)


class NameText(markovify.Text):
    def sentence_split(self, text):
        return re.split(r"\s*\n\s*", text)

    def word_split(self, sentence):
        return list(sentence)

    def word_join(self, words):
        return "".join(words)


class Markov(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.spell_names = []
        self.spell_times = []
        self.spell_ranges = []
        self.spell_durations = []
        self.spell_corpus = []
        self.higher_corpus = []
        self.spell_levels = (
            "cantrip",
            "1st level",
            "2nd level",
            "3rd level",
            "4th level",
            "5th level",
            "6th level",
            "7th level",
            "8th level",
            "9th level",
        )
        self.spell_schools = (
            "abjuration",
            "evocation",
            "enchantment",
            "illusion",
            "divination",
            "necromancy",
            "transmutation",
            "conjuration",
        )
        # items
        self.item_text = None
        self.item_name_text = None
        self.item_metas = []
        # feats
        self.feat_text = None
        self.feat_name_text = None
        self.feat_prereqs = []

        # spells
        with open(DATA_DIR / "spells.json") as f:
            spells = json.load(f)
        for spell in spells:
            self.spell_corpus.append(spell["description"])
            if spell["higherlevels"]:
                self.higher_corpus.append(spell["higherlevels"])
            self.spell_names.append(spell["name"])
            self.spell_times.append(spell["casttime"])
            self.spell_ranges.append(spell["range"])
            self.spell_durations.append(spell["duration"])
        self.spell_text = SpellText("\n\n\n\n".join(self.spell_corpus))
        self.spell_name_text = NameText("\n".join(self.spell_names), state_size=3)

        # items
        with open(DATA_DIR / "magic-items.json") as f:
            items = json.load(f)
        for item in items:
            self.item_metas.append(item["meta"])
        self.item_text = SpellText("\n\n\n\n".join(s["desc"] for s in items))
        self.item_name_text = NameText("\n".join(s["name"] for s in items), state_size=3)

        # feats
        with open(DATA_DIR / "feats.json") as f:
            feats = json.load(f)
        for feat in feats:
            self.feat_prereqs.append(feat["prerequisite"])
        self.feat_text = SpellText("\n\n\n\n".join(s["description"] for s in feats))
        self.feat_name_text = NameText("\n".join(s["name"] for s in feats), state_size=3)

    # generate
    def generate_name(self, name_text):
        title = None
        while not title:
            title = name_text.make_short_sentence(25)
        return title

    def generate_text(self, text, max_len=280):
        sentence = None
        while not sentence:
            sentence = text.make_short_sentence(max_len)
        return sentence

    # commands
    @commands.slash_command(name="markov", description="Markov shenanigans")
    async def markov(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @markov.sub_command(name="spell")
    async def markov_spell(self, inter: disnake.ApplicationCommandInteraction):
        """Markov chain a spell."""
        title = self.generate_name(self.spell_name_text)
        time = random.choice(self.spell_times)
        range_ = random.choice(self.spell_ranges)
        duration = random.choice(self.spell_durations)
        level = random.choice(self.spell_levels)
        school = random.choice(self.spell_schools)
        meta = (
            f"**{title}**\n*{level} {school}*\n**Casting Time**: {time}\n**Range**: {range_}\n**Duration**: {duration}"
        )
        text = self.generate_text(self.spell_text, max_len=512)
        await inter.send(f"{meta}\n\n{text}")

    @markov.sub_command(name="item")
    async def markov_item(self, inter: disnake.ApplicationCommandInteraction):
        """Markov chain a magic item."""
        title = self.generate_name(self.item_name_text)
        meta = random.choice(self.item_metas)
        top = f"**{title}**\n{meta}"
        text = self.generate_text(self.item_text, max_len=512)
        await inter.send(f"{top}\n\n{text}")

    @markov.sub_command(name="feat")
    async def markov_feat(self, inter: disnake.ApplicationCommandInteraction):
        """Markov chain a feat."""
        title = self.generate_name(self.feat_name_text)
        prereq = random.choice(self.feat_prereqs)
        meta = f"**{title}**\n*Prerequisite: {prereq}*"
        text = self.generate_text(self.feat_text, max_len=512)
        await inter.send(f"{meta}\n\n{text}")


def setup(bot):
    bot.add_cog(Markov(bot))
