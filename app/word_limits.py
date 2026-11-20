import re


def english_word_limits(prompt: str, minimum: int, maximum: int) -> tuple[int, int, str]:
    """Read the writing instruction even for questions imported with older scoring limits."""
    span = re.search(r"\b(\d+)\s*[-–—~～]\s*(\d+)\s+words?\b", prompt, re.I)
    if span:
        low, high = map(int, span.groups())
        if low <= high:
            return low, high, f"{low}～{high} 词"
    about = re.search(r"\b(?:about|around|approximately)\s+(\d+)\s+words?\b", prompt, re.I)
    if about:
        target = int(about[1])
        # A default for another essay length gives no basis for a penalty.
        if minimum > target or (maximum and maximum < target):
            minimum, maximum = 0, 0
        return minimum, maximum, f"约 {target} 词"
    if minimum and maximum:
        label = f"{minimum}～{maximum} 词"
    elif minimum:
        label = f"不少于 {minimum} 词"
    elif maximum:
        label = f"不超过 {maximum} 词"
    else:
        label = ""
    return minimum, maximum, label


def short_answer_limits(prompt: str, minimum: int, maximum: int) -> tuple[int, int]:
    """优先使用题干明确给出的字数上下限，兼容已入库的旧题。"""
    span = re.search(r"(\d+)\s*字?\s*[~～—–－至到-]\s*(\d+)\s*字", prompt)
    if span:
        return int(span[1]), int(span[2])
    upper = re.search(r"(?:不超过|不多于|至多)\s*(\d+)\s*字|(\d+)\s*字以内", prompt)
    lower = re.search(r"(?:不少于|不低于|至少)\s*(\d+)\s*字|(\d+)\s*字以上", prompt)
    if upper or lower:
        return (
            int(lower[1] or lower[2]) if lower else 0,
            int(upper[1] or upper[2]) if upper else 0,
        )
    return minimum, maximum
