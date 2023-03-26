import asyncio
import json
import random
from functools import partial

import disnake.ui

from calypso import constants, db, gamedata, models, utils
from . import queries

SUMMARY_HYPERPARAMS = dict(
    model="text-davinci-003",
    temperature=0.8,
    max_tokens=256,
    top_p=0.95,
    frequency_penalty=0.5,
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
        prompt_version = 2
        if prompt_version == 1:
            prompt = summary_prompt_1(self.encounter, self.monsters)
        else:
            prompt = summary_prompt_2(self.encounter, self.monsters)

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
                prompt_version=prompt_version,
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
        await interaction.send(
            (
                "Glad I could help! If you have a moment and would like to help me learn, you can give more detailed"
                " feedback by clicking the button."
            ),
            ephemeral=True,
            view=FeedbackView(summary),
        )

    async def summary_feedback_neg(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        async with db.async_session() as session:
            summary = await queries.get_summary_by_id(session, self.summary_id)
            summary.feedback = -1
            await session.commit()
        button.disabled = True
        self._b_summary_feedback_pos.disabled = False
        await self.refresh_content(interaction)
        await interaction.send(
            (
                "Sorry about that! If you have a moment and would like to help me learn, you can give more detailed"
                " feedback by clicking the button."
            ),
            ephemeral=True,
            view=FeedbackView(summary),
        )

    # ==== inspiration ====


# ==== feedback ====
class FeedbackView(disnake.ui.View):
    def __init__(self, summary: models.EncounterAISummary, **kwargs):
        super().__init__(**kwargs)
        self.summary = summary

    @disnake.ui.button(label="More Feedback", emoji="\U0001f4dd")  # :pencil:
    async def give_feedback(self, _: disnake.ui.Button, inter: disnake.Interaction):
        # modal
        await inter.response.send_modal(
            title="Encounter Helper Feedback",
            custom_id=str(inter.id),
            components=[
                disnake.ui.TextInput(
                    label="Generation (for reference, don't edit)",
                    custom_id="__generation",
                    style=disnake.TextInputStyle.paragraph,
                    placeholder="The generation is here for your reference. Anything you type here will be ignored.",
                    value=self.summary.generation,
                    required=False,
                ),
                disnake.ui.TextInput(
                    label="How to Improve (1-2 sentences)",
                    custom_id="edit",
                    style=disnake.TextInputStyle.paragraph,
                    placeholder="Write instructions for a bot describing how it could improve this summary.",
                    value=(
                        "Write instructions for a bot describing how it could improve this summary."
                        " [Example: This summary should be no longer than 3 sentences long. Leave out the backstory"
                        " about the elf mage]"
                    ),
                    required=False,
                ),
                disnake.ui.TextInput(
                    label="Other Comments (Optional)",
                    custom_id="feedback",
                    style=disnake.TextInputStyle.paragraph,
                    placeholder="Anything else you'd like to add?",
                    required=False,
                ),
            ],
        )
        try:
            modal_inter: disnake.ModalInteraction = await inter.bot.wait_for(
                "modal_submit", check=lambda mi: mi.custom_id == str(inter.id), timeout=1200
            )
        except asyncio.TimeoutError:
            await inter.author.send(
                "Sorry, your feedback form timed out. If you have feedback about the encounter helper please ping Zhu!"
            )
            return

        # save to db
        feedback = modal_inter.text_values["feedback"]
        edit = modal_inter.text_values["edit"]
        async with db.async_session() as session:
            feedback_obj = models.EncounterAISummaryFeedback(summary_id=self.summary.id, feedback=feedback, edit=edit)
            session.add(feedback_obj)
            await session.commit()

        # user feedback
        await modal_inter.send("Thanks! Your feedback was recorded.", ephemeral=True)


# ==== prompts ====
def creature_meta(monster: gamedata.Monster) -> str:
    ac = str(monster.ac) + (f" ({monster.armortype})" if monster.armortype else "")
    hp = f"{monster.hp} ({monster.hitdice})"
    meta = (
        f"{monster.name}\n"
        f"{'-' * len(monster.name)}\n"
        f"Armor Class: {ac}\n"
        f"Hit Points: {hp}\n"
        f"Speed: {monster.speed}\n"
        f"{monster.ability_scores}\n"
    )
    if str(monster.saves):
        meta += f"Saving Throws: {monster.saves}\n"
    if str(monster.skills):
        meta += f"Skills: {monster.skills}\n"
    meta += f"Senses: {monster.get_senses_str()}\n"
    if monster.display_resists.vuln:
        meta += f"Vulnerabilities: {', '.join(str(r) for r in monster.display_resists.vuln)}\n"
    if monster.display_resists.resist:
        meta += f"Resistances: {', '.join(str(r) for r in monster.display_resists.resist)}\n"
    if monster.display_resists.immune:
        meta += f"Damage Immunities: {', '.join(str(r) for r in monster.display_resists.immune)}\n"
    if monster.condition_immune:
        meta += f"Condition Immunities: {', '.join(monster.condition_immune)}\n"
    if monster.languages:
        meta += f"Languages: {', '.join(monster.languages)}\n"
    return meta.strip()


def creature_desc(monster: gamedata.Monster) -> str:
    monster_desc = gamedata.GamedataRepository.get_desc_for_monster(monster)
    desc_parts = []
    if monster_desc.characteristics:
        desc_parts.append(monster_desc.characteristics)
    if monster_desc.long:
        desc_parts.append(monster_desc.long)
    return "\n\n".join(desc_parts).strip()


def summary_prompt_1(encounter: models.RolledEncounter, monsters: list[gamedata.Monster]) -> str:
    # https://platform.openai.com/playground/p/TgTWenUG110KIdvqvocnzTYW
    creature_info_parts = []
    for monster in monsters:
        creature_info_parts.append(f"{creature_meta(monster)}\n\n{creature_desc(monster)}".strip())
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


def summary_prompt_2(encounter: models.RolledEncounter, monsters: list[gamedata.Monster]) -> str:
    # https://platform.openai.com/playground/p/dRKGQXUoSPveva0MP5fcik3h
    creature_info_parts = []
    for monster in monsters:
        desc = creature_desc(monster)
        if not desc:
            n = random.randint(2, 4)
            chosen_sources = random.sample(("folklore", "common sense", "mythology", "culture"), n)
            random_sources = utils.natural_join(chosen_sources, "and")
            desc = (
                f"Calypso, please provide the DM with information about the {monster.name} using information from"
                f" {random_sources}."
            )
        creature_info_parts.append(f"{creature_meta(monster)}\n\n{desc}".strip())
    creature_info = "\n\n".join(creature_info_parts)

    prompt = (
        "Your name is Calypso, and your job is to help the Dungeon Master with an encounter.\n"
        "Your task is to help the DM understand the setting and creatures as a group, focusing mainly on appearance and"
        " how they act.\n"
        "Especially focus on what makes each creature stand out.\n"
        "Avoid mentioning game stats.\n"
        "You may use information from common sense, mythology, and culture.\n"
        "If there are multiple creatures, conclude by mentioning how they interact.\n\n"
        f"Encounter: {encounter.rendered_text_nolinks}\n\n"
        "Setting\n"
        "=======\n"
        f"{encounter.biome_name}\n"
        f"{encounter.biome_text}\n\n"
        "Creatures\n"
        "=========\n"
        f"{creature_info}\n\n"
        "Calypso's Help\n"
        "==============\n"
    )
    return prompt
