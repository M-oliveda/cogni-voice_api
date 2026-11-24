# SPDX-License-Identifier: GPL-2.0-or-later
"""TOON encoding for data sent to the LLM (MASTERPLAN.md §9.2).

Structured data placed in a prompt or returned by an agent tool is encoded in
TOON (<https://github.com/toon-format/toon>) instead of JSON because it uses
fewer tokens, especially for uniform arrays such as lists of interactions. This
module is the only place that touches the ``toon-format`` package. Model output
is still JSON validated with Pydantic, and the REST API stays JSON.
"""

from typing import Any

import toon_format


class ToonEncodingError(ValueError):
    """Raised when a value cannot be represented in TOON."""


class ToonDecodingError(ValueError):
    """Raised when a string is not valid TOON."""


def encode(data: Any) -> str:
    """Encode JSON-compatible data as TOON for an LLM prompt.

    Dates, times and UUIDs are written as strings, as in JSON. Keys keep their
    insertion order so prompts stay stable between calls.

    Args:
        data: A JSON-compatible value (dict, list, str, int, float, bool or
            ``None``), possibly nested.

    Returns:
        The TOON text.

    Raises:
        ToonEncodingError: When ``data`` contains a value TOON cannot encode.
    """
    try:
        return toon_format.encode(data)
    except TypeError as error:
        raise ToonEncodingError(str(error)) from error


def decode(text: str) -> Any:
    """Decode TOON text strictly (declared lengths and indentation are checked).

    Args:
        text: The TOON text.

    Returns:
        The decoded JSON-compatible value.

    Raises:
        ToonDecodingError: When ``text`` is not valid TOON.
    """
    try:
        return toon_format.decode(text, strict=True)
    except toon_format.ToonDecodeError as error:
        raise ToonDecodingError(str(error)) from error
