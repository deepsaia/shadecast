"""The H3 and H4 rules: does one intervention type win, and does it win everywhere?"""

from shadecast.experiments.factorial import verdict


def _cell(city: str, kind: str, budget: float, efficiency: float) -> dict:
    return {
        "city": city,
        "kind": kind,
        "budget_usd": budget,
        "units": 100,
        "efficiency": efficiency,
    }


def _corpus(rio_tree: float = 40.0, rio_shade: float = 12.0) -> list[dict]:
    return [
        _cell("ahmedabad", "tree", 5e5, 60.0),
        _cell("ahmedabad", "shade", 5e5, 19.0),
        _cell("lagos", "tree", 5e5, 130.0),
        _cell("lagos", "shade", 5e5, 41.0),
        _cell("rio", "tree", 5e5, rio_tree),
        _cell("rio", "shade", 5e5, rio_shade),
    ]


def test_one_type_winning_everywhere_supports_both():
    """The finding this guards: trees win on cooling per dollar in every city."""
    result = verdict(_corpus())
    assert result["h3_supported"]
    assert result["h4_supported"]
    assert result["tree_wins"] == result["comparisons"] == 3
    assert result["advantage_ratio"]["mean"] > 1.0


def test_one_city_flipping_falsifies_h4():
    """A ranking that changes by city is not a ranking anyone should publish."""
    result = verdict(_corpus(rio_tree=10.0, rio_shade=30.0))
    assert result["h4_falsified"]
    assert not result["h4_supported"]
    assert result["h3_falsified"]


def test_types_within_twenty_percent_trip_the_abandonment_criterion():
    """If type barely matters, that is the finding, and it was written down in advance."""
    rows = [_cell("ahmedabad", "tree", 5e5, 20.0), _cell("ahmedabad", "shade", 5e5, 19.0)]
    assert verdict(rows)["types_indistinguishable"]


def test_a_single_type_gives_no_comparison():
    """One arm cannot rank against itself, and must not be reported as if it had."""
    result = verdict([_cell("ahmedabad", "tree", 5e5, 20.0)])
    assert result["comparisons"] == 0


def test_verdict_is_inconclusive_when_nothing_was_placed():
    assert not verdict([{"city": "x", "kind": "tree", "units": 0}])["conclusive"]
