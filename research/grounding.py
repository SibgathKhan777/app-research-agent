"""Quote grounding: does the evidence quote actually appear in the page it cites?

This is the first verification loop. A model can invent a plausible quote; this
check catches it mechanically, without trusting the model.
"""
from __future__ import annotations

import re

_TRANS = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})


def norm(s: str) -> str:
    s = (s or "").translate(_TRANS).lower()
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)  # markdown links -> text
    s = re.sub(r"[`*_#>\[\]|]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def quote_in_page(quote: str, page_text: str, min_words: int = 4) -> bool:
    """True if the quote (or every '...'-separated piece of it) occurs verbatim in the page.

    Pieces shorter than `min_words` words are ignored, but at least one piece
    must qualify, so a two-word quote can never count as grounded.
    """
    page = norm(page_text)
    pieces = [norm(p) for p in re.split(r"\.\.\.|…", quote or "")]
    pieces = [p for p in pieces if len(p.split()) >= min_words]
    return bool(pieces) and all(p in page for p in pieces)
