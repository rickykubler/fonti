"""Text normalization used to compare quotes with document text."""

import re
import unicodedata

_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "«": '"', "»": '"'})
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """NFKC, straight quotes, lowercase and single spaces."""
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES).lower()
    return _SPACES.sub(" ", text).strip()
