"""Stratified sampling of urban centres is a reproducible command, not a judgement call."""

from shadecast.corpus.draw import Draw
from shadecast.corpus.sampling import sample, strata
from shadecast.corpus.urban_centre import UrbanCentre


def _centre(
    centre_id: int, koppen: str | None, income: str | None, population_2025: int
) -> UrbanCentre:
    return UrbanCentre(
        id=centre_id,
        name=f"City {centre_id}",
        names=(f"City {centre_id}",),
        slug=f"city{centre_id}",
        country="Nowhere",
        population_2025=population_2025,
        area_km2=100,
        income=income,
        koppen_code=None,
        koppen=koppen,
        lon=0.0,
        lat=0.0,
    )


CENTRES = [
    _centre(1, "Aw", "LM", 5_000_000),
    _centre(2, "Aw", "LM", 2_000_000),
    _centre(3, "Aw", "LM", 400_000),
    _centre(4, "Aw", "LM", 50_000),
    _centre(5, "Cfb", "H", 9_000_000),
    _centre(6, "Cfb", "H", 800_000),
    _centre(7, "BWh", "L", 7_000_000),
    _centre(8, None, "UM", 3_000_000),
    _centre(9, "Dfa", None, 3_000_000),
]


def test_strata_pair_koppen_with_income_and_skip_unknowns():
    assert strata(CENTRES) == {("Aw", "LM"): 4, ("BWh", "L"): 1, ("Cfb", "H"): 2}


def test_sample_draws_up_to_k_per_stratum():
    drawn = sample(CENTRES, Draw(per_stratum=2, min_population_2025=300_000, seed=0))
    assert strata(drawn) == {("Aw", "LM"): 2, ("BWh", "L"): 1, ("Cfb", "H"): 2}


def test_sample_respects_the_population_floor():
    drawn = sample(CENTRES, Draw(per_stratum=2, min_population_2025=300_000, seed=0))
    assert all(c.population_2025 >= 300_000 for c in drawn)
    assert {c.id for c in drawn} <= {1, 2, 3, 5, 6, 7}


def test_sample_is_deterministic_for_a_seed():
    draw = Draw(per_stratum=1, min_population_2025=0, seed=3)
    assert [c.id for c in sample(CENTRES, draw)] == [c.id for c in sample(CENTRES, draw)]


def test_sample_changes_with_the_seed():
    draws = {
        tuple(c.id for c in sample(CENTRES, Draw(per_stratum=1, min_population_2025=0, seed=s)))
        for s in range(12)
    }
    assert len(draws) > 1


def test_sample_orders_by_stratum_then_population():
    drawn = sample(CENTRES, Draw(per_stratum=3, min_population_2025=0, seed=1))
    keys = [(c.koppen, c.income) for c in drawn]
    assert keys == sorted(keys)
    aw = [c.population_2025 for c in drawn if c.koppen == "Aw"]
    assert aw == sorted(aw, reverse=True)
