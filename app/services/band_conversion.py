"""
Official IELTS raw score to band score conversion tables.
Source: IELTS public score reporting system.
"""

# Listening: raw score (0-40) → band score
_LISTENING_TABLE: dict[int, float] = {
    39: 9.0, 40: 9.0,
    37: 8.5, 38: 8.5,
    35: 8.0, 36: 8.0,
    32: 7.5, 33: 7.5, 34: 7.5,
    30: 7.0, 31: 7.0,
    26: 6.5, 27: 6.5, 28: 6.5, 29: 6.5,
    23: 6.0, 24: 6.0, 25: 6.0,
    18: 5.5, 19: 5.5, 20: 5.5, 21: 5.5, 22: 5.5,
    16: 5.0, 17: 5.0,
    13: 4.5, 14: 4.5, 15: 4.5,
    10: 4.0, 11: 4.0, 12: 4.0,
    8:  3.5, 9:  3.5,
    6:  3.0, 7:  3.0,
    4:  2.5, 5:  2.5,
    2:  2.0, 3:  2.0,
    1:  1.0,
    0:  0.0,
}

# Reading Academic: raw score (0-40) → band score
_READING_ACADEMIC_TABLE: dict[int, float] = {
    39: 9.0, 40: 9.0,
    37: 8.5, 38: 8.5,
    35: 8.0, 36: 8.0,
    33: 7.5, 34: 7.5,
    30: 7.0, 31: 7.0, 32: 7.0,
    27: 6.5, 28: 6.5, 29: 6.5,
    23: 6.0, 24: 6.0, 25: 6.0, 26: 6.0,
    19: 5.5, 20: 5.5, 21: 5.5, 22: 5.5,
    15: 5.0, 16: 5.0, 17: 5.0, 18: 5.0,
    13: 4.5, 14: 4.5,
    10: 4.0, 11: 4.0, 12: 4.0,
    8:  3.5, 9:  3.5,
    6:  3.0, 7:  3.0,
    4:  2.5, 5:  2.5,
    2:  2.0, 3:  2.0,
    1:  1.0,
    0:  0.0,
}

# Reading General Training: raw score (0-40) → band score
_READING_GENERAL_TABLE: dict[int, float] = {
    40: 9.0,
    39: 8.5,
    37: 8.0, 38: 8.0,
    36: 7.5,
    34: 7.0, 35: 7.0,
    32: 6.5, 33: 6.5,
    30: 6.0, 31: 6.0,
    27: 5.5, 28: 5.5, 29: 5.5,
    23: 5.0, 24: 5.0, 25: 5.0, 26: 5.0,
    19: 4.5, 20: 4.5, 21: 4.5, 22: 4.5,
    15: 4.0, 16: 4.0, 17: 4.0, 18: 4.0,
    12: 3.5, 13: 3.5, 14: 3.5,
    9:  3.0, 10: 3.0, 11: 3.0,
    6:  2.5, 7:  2.5, 8:  2.5,
    4:  2.0, 5:  2.0,
    1:  1.0, 2:  1.0, 3:  1.0,
    0:  0.0,
}


def _prorate_to_40(raw: int, total_questions: int) -> int:
    """
    Convert a raw correct count from a partial exam to the equivalent score
    on a standard 40-question test, so the official band tables apply.

    Example: 8 correct out of 12 → round(8 * 40 / 12) = 27 (equivalent to
    27/40 on a full test). Returns 0 if total_questions is 0.
    """
    if total_questions <= 0:
        return 0
    raw = max(0, min(total_questions, raw))
    return round(raw * 40 / total_questions)


def listening_band(raw: int, total_questions: int) -> float:
    """
    Convert Listening raw score to IELTS band, accounting for partial tests.

    total_questions: number of questions actually in the section. For a
    standard 40-question section this is a no-op; for shorter sections the
    raw count is prorated to the 40-question equivalent before lookup.
    """
    prorated = _prorate_to_40(raw, total_questions)
    for threshold in sorted(_LISTENING_TABLE.keys(), reverse=True):
        if prorated >= threshold:
            return _LISTENING_TABLE[threshold]
    return 0.0


def reading_band(raw: int, total_questions: int, exam_type: str = "ACADEMIC") -> float:
    """
    Convert Reading raw score to IELTS band, accounting for partial tests.

    total_questions: number of questions actually in the section. The raw
    count is prorated to the 40-question equivalent before lookup so the
    official conversion table applies regardless of test length.
    """
    prorated = _prorate_to_40(raw, total_questions)
    table = _READING_ACADEMIC_TABLE if exam_type == "ACADEMIC" else _READING_GENERAL_TABLE
    for threshold in sorted(table.keys(), reverse=True):
        if prorated >= threshold:
            return table[threshold]
    return 0.0


def overall_band(section_bands: list[float]) -> float:
    """
    Compute IELTS Overall Band Score from up to 4 section bands.
    Each section is equally weighted; result rounds to nearest 0.5.
    """
    if not section_bands:
        return 0.0
    avg = sum(section_bands) / len(section_bands)
    # Round to nearest 0.5
    return round(avg * 2) / 2


def writing_band_from_criteria(task_response: float, coherence: float, lexical: float, grammar: float) -> float:
    """Average four Writing criteria, rounded to nearest 0.5."""
    avg = (task_response + coherence + lexical + grammar) / 4
    return round(avg * 2) / 2
