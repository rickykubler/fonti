"""Text normalization used to compare quotes with document text."""

import re
import unicodedata

_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "«": '"', "»": '"', "|": " "})
_TABLE_RULES = re.compile(r"(?<![^\s:])[-:]{3,}(?![^\s:])")  # Markdown "---" separator cells
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """NFKC, straight quotes, lowercase and single spaces. Table pipes and separator rows are
    dropped, so a quote matches both flat text and a Markdown table."""
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES).lower()
    return _SPACES.sub(" ", _TABLE_RULES.sub(" ", text)).strip()
