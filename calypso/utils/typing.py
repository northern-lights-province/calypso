"""
Typing helpers.
"""
from typing import TYPE_CHECKING, Union

import disnake

if TYPE_CHECKING:
    from calypso import Calypso


class Interaction(disnake.Interaction):
    bot: "Calypso"


InteractionChannel = Union[disnake.TextChannel, disnake.Thread, disnake.VoiceChannel, disnake.PartialMessageable]
