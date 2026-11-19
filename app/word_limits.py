import re


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
