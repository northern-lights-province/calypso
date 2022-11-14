import asyncio
import itertools
import logging
import re
from typing import List

import gspread
from pydantic import BaseModel

from calypso import config, constants

log = logging.getLogger(__name__)


class Encounter(BaseModel):
    text: str
    weight: float


class Tier(BaseModel):
    biome: str
    tier: int
    encounters: List[Encounter]

    @property
    def encounter_cum_weights(self) -> List[float]:
        return list(itertools.accumulate(e.weight for e in self.encounters))

    @property
    def encounter_weights(self) -> List[float]:
        return list(e.weight for e in self.encounters)


class EncounterRepository:
    tiers: List[Tier] = []


class EncounterClient:
    def __init__(self):
        self.google_client = gspread.service_account(filename=config.GOOGLE_SERVICE_ACCOUNT_PATH)
        self._refresh_lock = asyncio.Lock()

    def _do_refresh(self):
        sheet = self.google_client.open_by_key(constants.RANDOM_ENCOUNTER_SHEET_ID)
        worksheets = sheet.worksheets()
        query = []  # (name, tier, A1 notation)
        for worksheet in worksheets:
            if not (match := re.match(r"(.+?)\s*-\s*(\d+)", worksheet.title)):
                continue
            name = match.group(1)
            tier = match.group(2)
            query.append((name, tier, f"{worksheet.title}!A2:B"))  # get 1st 2 columns of worksheet, from row 2 down

        # why do you not wrap this, gspread >:c
        ranges = [q[2] for q in query]
        data = sheet.values_batch_get(ranges, {"majorDimension": "ROWS", "valueRenderOption": "UNFORMATTED_VALUE"})
        result_ranges = data["valueRanges"]
        assert len(result_ranges) == len(query)

        # pair all the queries w/ the data results
        all_tiers = []

        for ((name, tier, _), result_range) in zip(query, result_ranges):
            encounters = []
            for text, weight in result_range["values"]:
                encounters.append(Encounter(text=text, weight=weight))
            all_tiers.append(Tier(biome=name, tier=tier, encounters=encounters))

        EncounterRepository.tiers = all_tiers

    async def refresh_encounters(self):
        async with self._refresh_lock:
            log.info("Refreshing encounters from google sheet...")
            await asyncio.get_event_loop().run_in_executor(None, self._do_refresh)
        n_encounters = sum(len(t.encounters) for t in EncounterRepository.tiers)
        n_tiers = len(EncounterRepository.tiers)
        log.info(f"Refreshed encounters - loaded {n_encounters} encounters across {n_tiers} biome-tiers")
