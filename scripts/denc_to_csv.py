import csv
import re
from typing import List, Optional

import gspread
from pydantic import BaseModel


class DEncTableEntry(BaseModel):
    max: int
    name: str
    text: str
    code: Optional[str]
    rolls: Optional[str]  # comma-seperated
    xp: Optional[str]


class DEncTier(BaseModel):
    tier: int
    table: List[DEncTableEntry]


class DEncEncounter(BaseModel):
    source: str
    shortSource: str
    loc: str
    minTier: int
    maxTier: int
    tiers: List[DEncTier]


class DEncLibrary(BaseModel):
    purpose: str
    encounter: List[DEncEncounter]


class OutputModel(BaseModel):
    text: str
    weight: int


def convert_table_entry(entry: DEncTableEntry) -> str:
    text = entry.text
    if entry.rolls is None:
        return text
    rolls = entry.rolls.split(",")
    for match in re.finditer(r"#(\d+)#", text):
        roll_idx = int(match.group(1)) - 1
        roll_text = rolls[roll_idx]
        try:
            roll_text = f"`{int(roll_text)}`"
        except ValueError:
            roll_text = f"{{{roll_text}}}"
        text = text.replace(match.group(0), roll_text)
    return text


def convert_file(fp):
    wrote_files = []
    print(f"Reading {fp}")
    denc_data = DEncLibrary.parse_file(fp)
    for encounter in denc_data.encounter:
        for tier in encounter.tiers:
            outname = f"{encounter.loc} - {tier.tier}.csv"
            out = []

            last_roll = 0
            for entry in tier.table:
                weight = entry.max - last_roll
                last_roll = entry.max
                text = convert_table_entry(entry)
                out.append(OutputModel(text=text, weight=weight))

            with open(outname, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(("Encounter", "Weight"))
                writer.writerows(((m.text, m.weight) for m in out))

            print(f"Wrote {outname}")
            wrote_files.append(outname)
    return wrote_files


def upload_to_gsheet(fp):
    name, _ = fp.rsplit(".", 1)
    with open(fp, "r", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    gc = gspread.service_account()
    spreadsheet = gc.open("Random Encounters")
    sheet = spreadsheet.add_worksheet(title=name, rows=len(rows), cols=2)
    sheet.insert_rows(rows)
    print(f"Uploaded {fp} to spreadsheet")


def main():
    out = []
    out.extend(convert_file("output.json"))
    out.extend(convert_file("output2.json"))
    out.extend(convert_file("output3.json"))
    # for f in out:
    #     upload_to_gsheet(f)


if __name__ == "__main__":
    main()
