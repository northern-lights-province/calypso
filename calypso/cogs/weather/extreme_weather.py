EXTREME_COLD = (
    "Whenever the temperature is at or below 0 degrees Fahrenheit, a creature exposed to the cold must succeed on a DC"
    " 10 Constitution saving throw at the end of each hour or gain one level of exhaustion. Creatures with resistance"
    " or immunity to cold damage automatically succeed on the saving throw, as do creatures wearing cold weather gear"
    " (thick coats, gloves, and the like) and creatures naturally adapted to cold climates."
)

EXTREME_HEAT = (
    "When the temperature is at or above 100 degrees Fahrenheit, a creature exposed to the heat and without access to"
    " drinkable water must succeed on a Constitution saving throw at the end of each hour or gain one level of"
    " exhaustion. The DC is 5 for the first hour and increases by 1 for each additional hour. Creatures wearing medium"
    " or heavy armor, or who are clad in heavy clothing, have disadvantage on the saving throw. Creatures with"
    " resistance or immunity to fire damage automatically succeed on the saving throw, as do creatures naturally"
    " adapted to hot climates."
)

STRONG_WIND = (
    "A strong wind imposes disadvantage on ranged weapon attack rolls and Wisdom (Perception) checks that rely on"
    " hearing. A strong wind also extinguishes open flames, disperses fog, and makes flying by nonmagical means nearly"
    " impossible. A flying creature in a strong wind must land at the end of its turn or fall.\n\nA strong wind in a"
    " desert can create a sandstorm that imposes disadvantage on Wisdom (Perception) checks that rely on sight."
)

HEAVY_PRECIPITATION = (
    "Everything within an area of heavy rain or heavy snowfall is lightly obscured, and creatures in the area have"
    " disadvantage on Wisdom (Perception) checks that rely on sight. Heavy rain also extinguishes open flames and"
    " imposes disadvantage on Wisdom (Perception) checks that rely on hearing."
)

LIGHTLY_OBSCURED = (
    "In a lightly obscured area, such as dim light, patchy fog, or moderate foliage, creatures have disadvantage on"
    " Wisdom (Perception) checks that rely on sight."
)


def is_heavy_precipitation(weather_detail: int):
    # see client for descriptions of weather codes
    return weather_detail in {202, 221, 314, 503, 504, 522, 531, 602, 616, 622, 771, 781}


def is_lightly_obscured(weather_detail: int):
    return weather_detail in {701, 711, 731, 741, 751, 761, 762}
