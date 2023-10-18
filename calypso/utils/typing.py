"""
Typing helpers.
"""
from typing import TYPE_CHECKING, TypedDict, Union

import disnake

if TYPE_CHECKING:
    from calypso import Calypso


class Interaction(disnake.Interaction):
    bot: "Calypso"


class EmbedField(TypedDict):
    name: str
    value: str


InteractionChannel = Union[disnake.TextChannel, disnake.Thread, disnake.VoiceChannel, disnake.PartialMessageable]
