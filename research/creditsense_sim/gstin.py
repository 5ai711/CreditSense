"""GSTIN structure and check-character validation for the compliance gate.

A GSTIN has 15 characters:
    2  state code (01-38)
    10 PAN of the business (5 letters, 4 digits, 1 letter)
    1  entity number for the same PAN in the state (1-9, A-Z)
    1  the letter 'Z' (reserved)
    1  check character, a Luhn mod-36 code over the first 14 characters
"""
from __future__ import annotations

import re

import numpy as np

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_INDEX = {c: i for i, c in enumerate(ALPHABET)}
SHAPE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
VALID_STATE_CODES = {f"{i:02d}" for i in range(1, 39)}
PAN_HOLDER_TYPES = "CPHFATBLJG"


def check_char(first14: str) -> str:
    total = 0
    for pos, ch in enumerate(first14):
        product = _INDEX[ch] * (1 if pos % 2 == 0 else 2)
        total += product // 36 + product % 36
    return ALPHABET[(36 - total % 36) % 36]


def valid_shape(gstin: str) -> bool:
    return bool(SHAPE.match(gstin))


def valid_full(gstin: str) -> bool:
    return (
        valid_shape(gstin)
        and gstin[:2] in VALID_STATE_CODES
        and gstin[5] in PAN_HOLDER_TYPES
        and check_char(gstin[:14]) == gstin[14]
    )


def random_valid(rng: np.random.Generator) -> str:
    letters = ALPHABET[10:]
    state = f"{rng.integers(1, 39):02d}"
    pan = (
        "".join(rng.choice(list(letters), 3))
        + rng.choice(list(PAN_HOLDER_TYPES))
        + rng.choice(list(letters))
        + "".join(rng.choice(list(ALPHABET[:10]), 4))
        + rng.choice(list(letters))
    )
    entity = rng.choice(list(ALPHABET[1:]))
    body = state + pan + entity + "Z"
    return body + check_char(body)


def substitute_same_class(g: str, rng: np.random.Generator) -> str:
    """Replace one character with a different one of the same class (digit/letter)."""
    pos = int(rng.integers(0, 15))
    pool = ALPHABET[:10] if g[pos].isdigit() else ALPHABET[10:]
    new = rng.choice([c for c in pool if c != g[pos]])
    return g[:pos] + new + g[pos + 1 :]


def transpose_adjacent(g: str, rng: np.random.Generator) -> str | None:
    """Swap two adjacent, unequal characters; None if every neighbour pair is equal."""
    candidates = [i for i in range(14) if g[i] != g[i + 1]]
    if not candidates:
        return None
    i = int(rng.choice(candidates))
    return g[:i] + g[i + 1] + g[i] + g[i + 2 :]


def fabricated(rng: np.random.Generator) -> str:
    """A well-shaped GSTIN whose last character is guessed rather than computed."""
    g = random_valid(rng)
    return g[:14] + rng.choice(list(ALPHABET))
