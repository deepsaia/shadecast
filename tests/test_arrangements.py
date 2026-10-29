"""Arrangements name what a person chooses; design families name what the physics ran."""

import pytest

from shadecast.service.arrangements import ARRANGEMENTS
from shadecast.service.arrangements import arrangement_of
from shadecast.service.arrangements import family_of
from shadecast.service.unknown_arrangement import UnknownArrangement


def test_every_arrangement_has_a_family_and_the_family_names_it_back():
    for arrangement in ARRANGEMENTS:
        assert arrangement_of(f"{family_of(arrangement)}_0105") == arrangement


def test_scattered_is_the_random_uniform_family():
    assert family_of("scattered") == "random_uniform"
    assert arrangement_of("random_uniform_0201") == "scattered"


def test_a_probe_is_not_a_plan_and_an_unknown_arrangement_is_refused():
    assert arrangement_of("sparse_probe_0000") == ""
    with pytest.raises(UnknownArrangement, match="orchard"):
        family_of("orchard")
