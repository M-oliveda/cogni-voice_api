# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the TOON encoding helper."""

import datetime
import math
import uuid
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.ai import toon
from app.ai.toon import ToonDecodingError, ToonEncodingError

# JSON-compatible values. NaN and infinity are excluded because, as in JSON,
# TOON writes them as null.
json_scalars = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text()
)
json_values = st.recursive(
    json_scalars,
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=25,
)


def test_uniform_objects_are_encoded_as_a_table() -> None:
    data = {"interactions": [{"id": 1, "topic": "billing"}, {"id": 2, "topic": "app"}]}

    assert toon.encode(data) == "interactions[2]{id,topic}:\n  1,billing\n  2,app"


def test_values_with_delimiters_are_quoted() -> None:
    assert toon.encode({"summary": "slow, then broken"}) == (
        'summary: "slow, then broken"'
    )


def test_keys_keep_insertion_order() -> None:
    assert toon.encode({"b": 1, "a": 2}) == "b: 1\na: 2"


def test_dates_and_uuids_are_written_as_strings() -> None:
    identifier = uuid.UUID("00000000-0000-4000-8000-000000000001")
    data = {"day": datetime.date(2026, 1, 31), "id": identifier}

    assert toon.decode(toon.encode(data)) == {
        "day": "2026-01-31",
        "id": "00000000-0000-4000-8000-000000000001",
    }


@pytest.mark.parametrize(
    "data",
    [
        {},
        [],
        None,
        "plain text",
        {"nested": {"list": [1, 2.5, True, None]}},
        [[1, 2], [3]],
        {"text": 'quotes " and \n newlines'},
    ],
)
def test_round_trip_examples(data: Any) -> None:
    assert toon.decode(toon.encode(data)) == data


@given(json_values)
def test_round_trip_property(data: Any) -> None:
    assert toon.decode(toon.encode(data)) == data


def test_non_finite_floats_become_null() -> None:
    assert toon.decode(toon.encode({"score": math.inf})) == {"score": None}


@pytest.mark.parametrize("value", [object(), b"bytes"])
def test_encode_rejects_unsupported_values(value: object) -> None:
    with pytest.raises(ToonEncodingError, match="not TOON serializable"):
        toon.encode({"value": value})


def test_decode_is_strict_about_declared_lengths() -> None:
    with pytest.raises(ToonDecodingError, match="Declared length 3"):
        toon.decode("items[3]: a,b")
