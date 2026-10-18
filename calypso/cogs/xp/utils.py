from . import constants as xp_constants


def level_from_xp(xp: int) -> int:
    """Return the current level given the raw XP."""
    return next((level for level, threshold in reversed(xp_constants.LEVEL_THRESHOLDS) if xp >= threshold), 0)


def progress_to_next_level(xp: int) -> str:
    """Return the amount of xp to the next level given the current XP, formatted in ``remaining/to_next``."""
    current_level = level_from_xp(xp)
    current_level_threshold = xp_constants.LEVEL_THRESHOLDS_BY_LEVEL.get(current_level, 0)
    if current_level == xp_constants.LEVEL_THRESHOLDS[-1][0]:
        return "Max level!"
    next_level, next_level_threshold = next(
        (level, threshold) for (level, threshold) in xp_constants.LEVEL_THRESHOLDS if threshold > xp
    )
    to_next_level = next_level_threshold - current_level_threshold
    progress = xp - current_level_threshold
    return f"{progress} / {to_next_level}"
