import json
from functools import partial

import disnake.ui

from calypso import constants, db, gamedata, models
from . import queries

SUMMARY_HYPERPARAMS = dict(
    model="text-davinci-003",
    temperature=0.9,
    max_tokens=256,
    top_p=0.95,
    frequency_penalty=1,
    presence_penalty=1,
)


class ButtonWithCallback(disnake.ui.Button):
    def __init__(self, callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.callback = partial(callback, self)


class EncounterHelperController(disnake.ui.View):
    def __init__(
        self,
        owner: disnake.User,
        encounter: models.RolledEncounter,
        monsters: list[gamedata.Monster],
        embed: disnake.Embed,
        *,
        timeout=900,
    ):
        super().__init__(timeout=timeout)
        self.owner = owner
        self.encounter = encounter
        self.monsters = monsters
        self.embed = embed
        self.summary_field_idx = None
        self.summary_id = None
        # buttons
        self._b_generate_summary = ButtonWithCallback(
            self.generate_summary,
            label="Help me understand the monsters",
            emoji="\U0001f916",  # :robot:
            style=disnake.ButtonStyle.primary,
            row=0,
        )
        self._b_summary_feedback_pos = ButtonWithCallback(
            self.summary_feedback_pos,
            label="The summary was helpful!",
            emoji="\U0001f604",  # :grin:
            style=disnake.ButtonStyle.success,
            row=0,
        )
        self._b_summary_feedback_neg = ButtonWithCallback(
            self.summary_feedback_neg,
            label="The summary wasn't that helpful.",
            emoji="\U0001f615",  # :confused:
            style=disnake.ButtonStyle.danger,
            row=0,
        )
        # buttons in initial state
        self.add_item(self._b_generate_summary)

    # ==== d.py overrides and helpers ====
    async def interaction_check(self, interaction: disnake.Interaction) -> bool:
        if interaction.user.id == self.owner.id:
            return True
        await interaction.response.send_message("You are not the controller of this menu.", ephemeral=True)
        return False

    async def refresh_content(self, interaction: disnake.Interaction, **kwargs):
        """Refresh the interaction's message with the current state of the menu."""
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self, **kwargs)
        else:
            await interaction.response.edit_message(view=self, **kwargs)

    # ==== summary ====
    # ---- generation ----
    async def generate_summary(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        # this will take a while, edit in a loading field and disable the button
        if self.summary_field_idx is None:
            self.embed.add_field(name="Encounter Summary", value=constants.TYPING_EMOJI, inline=False)
            self.summary_field_idx = len(self.embed.fields) - 1
        else:
            self.embed.set_field_at(
                self.summary_field_idx, name="Encounter Summary", value=constants.TYPING_EMOJI, inline=False
            )
        button.disabled = True
        await self.refresh_content(interaction, embed=self.embed)

        # generate the summary
        prompt = summary_prompt(self.encounter, self.monsters)
        # noinspection PyUnresolvedReferences
        completion = await interaction.bot.openai.create_completion(
            prompt=prompt, user=str(interaction.author.id), **SUMMARY_HYPERPARAMS
        )
        summary = completion.text.strip()

        # save it to db
        async with db.async_session() as session:
            summary_obj = models.EncounterAISummary(
                encounter_id=self.encounter.id,
                prompt=prompt,
                generation=summary,
                hyperparams=json.dumps(SUMMARY_HYPERPARAMS),
            )
            session.add(summary_obj)
            await session.commit()
            self.summary_id = summary_obj.id

        # add it to embed
        self.embed.set_field_at(self.summary_field_idx, name="Encounter Summary", value=summary, inline=False)

        # button wrangling
        self.remove_item(button)
        self.add_item(self._b_summary_feedback_pos)
        self.add_item(self._b_summary_feedback_neg)
        await self.refresh_content(interaction, embed=self.embed)

        # log it to staff chat
        log_channel = interaction.bot.get_channel(constants.STAFF_LOG_CHANNEL_ID)
        await log_channel.send(
            f"<@{self.encounter.author_id}>'s encounter was updated with an AI-generated summary:",
            embed=self.embed,
            allowed_mentions=disnake.AllowedMentions.none(),
        )

    # ---- feedback ----
    async def summary_feedback_pos(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        async with db.async_session() as session:
            summary = await queries.get_summary_by_id(session, self.summary_id)
            summary.feedback = 1
            await session.commit()
        button.disabled = True
        self._b_summary_feedback_neg.disabled = False
        await self.refresh_content(interaction)
        await interaction.send("Thanks for the feedback!", ephemeral=True)

    async def summary_feedback_neg(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        async with db.async_session() as session:
            summary = await queries.get_summary_by_id(session, self.summary_id)
            summary.feedback = -1
            await session.commit()
        button.disabled = True
        self._b_summary_feedback_pos.disabled = False
        await self.refresh_content(interaction)
        await interaction.send("Thanks for the feedback!", ephemeral=True)

    # ==== inspiration ====


# ==== prompts ====
def summary_prompt(encounter: models.RolledEncounter, monsters: list[gamedata.Monster]) -> str:
    # https://platform.openai.com/playground/p/TgTWenUG110KIdvqvocnzTYW
    creature_info_parts = []
    for monster in monsters:
        # meta
        ac = str(monster.ac) + (f" ({monster.armortype})" if monster.armortype else "")
        hp = f"{monster.hp} ({monster.hitdice})"
        part = (
            f"{monster.name}\n"
            f"{'-' * len(monster.name)}\n"
            f"Armor Class: {ac}\n"
            f"Hit Points: {hp}\n"
            f"Speed: {monster.speed}\n"
            f"{monster.ability_scores}\n"
        )
        if str(monster.saves):
            part += f"Saving Throws: {monster.saves}\n"
        if str(monster.skills):
            part += f"Skills: {monster.skills}\n"
        part += f"Senses: {monster.get_senses_str()}\n"
        if monster.display_resists.vuln:
            part += f"Vulnerabilities: {', '.join(str(r) for r in monster.display_resists.vuln)}\n"
        if monster.display_resists.resist:
            part += f"Resistances: {', '.join(str(r) for r in monster.display_resists.resist)}\n"
        if monster.display_resists.immune:
            part += f"Damage Immunities: {', '.join(str(r) for r in monster.display_resists.immune)}\n"
        if monster.condition_immune:
            part += f"Condition Immunities: {', '.join(monster.condition_immune)}\n"
        if monster.languages:
            part += f"Languages: {', '.join(monster.languages)}\n"

        # desc
        monster_desc = gamedata.GamedataRepository.get_desc_for_monster(monster)
        desc_parts = []
        if monster_desc.characteristics:
            desc_parts.append(monster_desc.characteristics)
        if monster_desc.long:
            desc_parts.append(monster_desc.long)
        desc_part = "\n\n".join(desc_parts)

        creature_info_parts.append(f"{part.strip()}\n\n{desc_part}".strip())
    creature_info = "\n\n".join(creature_info_parts)

    prompt = (
        "Summarize the following D&D setting and monsters for a Dungeon Master's notes without mentioning game"
        " stats.\n\n"
        "Setting\n"
        "=======\n"
        f"{encounter.biome_name}\n"
        f"{encounter.biome_text}\n\n"
        "Creatures\n"
        "=========\n"
        f"{creature_info}\n\n"
        "Summary\n"
        "=======\n"
    )
    return prompt
