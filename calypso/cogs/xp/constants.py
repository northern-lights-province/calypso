XP_PER_MESSAGE = 7
XP_COOLDOWN_SECS = 540  # 9 minutes
IGNORE_PREFIX = "!"
MIN_MESSAGE_LEN = 11

NO_XP_ROLE = 1075198949348085891
LEVEL_UP_CHANNEL = 1043969117834715187
LEVEL_UP_TEMPLATE = (
    "Congrats, {member_mention}. You've reached level {new_level}!\nYou may level up during your next long rest, or"
    " keep your current level and level up at any later long rest."
)

# level, xp
LEVEL_THRESHOLDS = [
    (5, 1067),
    (6, 1661),
    (7, 2387),
    (8, 3245),
    (9, 4235),
    (10, 5357),
    (11, 6611),
    (12, 7997),
    (13, 9515),
    (14, 11165),
    (15, 12947),
    (16, 14861),
    (17, 16907),
    (18, 19085),
    (19, 21395),
    (20, 23837),
]
LEVEL_THRESHOLDS_BY_LEVEL = dict(LEVEL_THRESHOLDS)

# level, role_id - get this role when reaching this level, remove if falling below
ROLE_THRESHOLDS = [
    (1, 1054066224310534265),  # Tier 1
    (5, 1054066226458013839),  # Tier 2
    (11, 1054066228727124099),  # Tier 3
    (17, 1054066230740398220),  # Tier 4
]
