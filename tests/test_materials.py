"""Tests for fixed and random material property generator behavior."""

import random

import pytest

from compgen.materials import FixedMaterialGenerator, RandomMaterialGenerator


def test_fixed_material_generator_returns_same_values_each_time():
    """Test that the FixedMaterialGenerator returns the same properties on each call."""
    gen = FixedMaterialGenerator(thermal_conductivity=12.5, youngs_modulus=210.0)

    first = gen.next()
    second = gen.next()

    assert first == {"thermal_conductivity": 12.5, "youngs_modulus": 210.0}
    assert second == {"thermal_conductivity": 12.5, "youngs_modulus": 210.0}


def test_fixed_material_generator_iterator_protocol_returns_fixed_values():
    """Test that the FixedMaterialGenerator iterator protocol returns the same properties
    on each call."""
    gen = FixedMaterialGenerator(alpha=1.2, beta=3.4)

    value = next(gen)

    assert value == {"alpha": 1.2, "beta": 3.4}


def test_random_material_generator_values_stay_within_ranges():
    """Test that the RandomMaterialGenerator produces values within the specified ranges."""
    ranges = {
        "thermal_conductivity": (5.0, 20.0),
        "youngs_modulus": (100.0, 250.0),
        "poisson_ratio": (0.2, 0.4),
    }
    gen = RandomMaterialGenerator(**ranges)

    for _ in range(500):
        sample = gen.next()
        assert set(sample.keys()) == set(ranges.keys())
        for prop, (min_value, max_value) in ranges.items():
            assert min_value <= sample[prop] <= max_value


def test_random_material_generator_loguniform_spreads_across_decades():
    """Test that the loguniform distribution puts roughly equal weight on each decade,
    unlike the uniform distribution which concentrates samples in the top decade."""
    random.seed(20250810)
    gen = RandomMaterialGenerator(
        conductivity={"interval": [1.0, 1000.0], "distribution": "loguniform"}
    )

    samples = [gen.next()["conductivity"] for _ in range(5000)]

    assert all(1.0 <= value <= 1000.0 for value in samples)

    # A log-uniform sample over three decades lands below 10 a third of the time and
    # below 100 two thirds of the time. Under uniform sampling these would be 0.009 and
    # 0.099, so the band is wide enough to be stable yet still fail loudly.
    below_ten = sum(value < 10.0 for value in samples) / len(samples)
    below_hundred = sum(value < 100.0 for value in samples) / len(samples)

    assert below_ten == pytest.approx(1.0 / 3.0, abs=0.05)
    assert below_hundred == pytest.approx(2.0 / 3.0, abs=0.05)


@pytest.mark.parametrize("distribution", ["loguniform", "log-uniform", "log_uniform"])
def test_random_material_generator_accepts_loguniform_aliases(distribution):
    """Test that the alternate spellings of the loguniform distribution are accepted."""
    gen = RandomMaterialGenerator(
        conductivity={"interval": [1.0, 50.0], "distribution": distribution}
    )

    for _ in range(100):
        assert 1.0 <= gen.next()["conductivity"] <= 50.0


def test_random_material_generator_mixes_spec_forms():
    """Test that a dict specification and a plain interval coexist in one generator."""
    gen = RandomMaterialGenerator(
        youngs_modulus={"interval": [1.0, 100.0], "distribution": "loguniform"},
        poissons_ratio=[-0.2, 0.49],
    )

    for _ in range(500):
        sample = gen.next()
        assert set(sample.keys()) == {"youngs_modulus", "poissons_ratio"}
        assert 1.0 <= sample["youngs_modulus"] <= 100.0
        assert -0.2 <= sample["poissons_ratio"] <= 0.49


def test_random_material_generator_dict_without_distribution_matches_plain_interval():
    """Test that omitting the distribution key is identical to a plain interval."""
    random.seed(7)
    from_interval = RandomMaterialGenerator(conductivity=[1.0, 50.0]).next()

    random.seed(7)
    from_dict = RandomMaterialGenerator(conductivity={"interval": [1.0, 50.0]}).next()

    assert from_interval == from_dict


def test_random_material_generator_degenerate_loguniform_interval_is_exact():
    """Test that a zero-width loguniform interval returns its bound exactly, with no
    floating point drift from an exp(log(x)) round trip."""
    gen = RandomMaterialGenerator(
        youngs_modulus={"interval": [3.7, 3.7], "distribution": "loguniform"}
    )

    for _ in range(10):
        assert gen.next()["youngs_modulus"] == 3.7


def test_random_material_generator_rejects_nonpositive_loguniform_interval():
    """Test that a loguniform interval reaching zero or below is rejected."""
    with pytest.raises(ValueError, match="poissons_ratio.*strictly positive"):
        RandomMaterialGenerator(
            poissons_ratio={"interval": [-0.2, 0.49], "distribution": "loguniform"}
        )


def test_random_material_generator_rejects_unknown_distribution():
    """Test that an unrecognized distribution name is rejected rather than silently
    falling back to uniform sampling."""
    with pytest.raises(ValueError, match="Unknown distribution.*conductivity"):
        RandomMaterialGenerator(
            conductivity={"interval": [1.0, 50.0], "distribution": "lognormal"}
        )


def test_random_material_generator_rejects_unknown_spec_key():
    """Test that a misspelled specification key is rejected, so a typo cannot silently
    sample the wrong distribution for a whole sweep."""
    with pytest.raises(ValueError, match="Unknown key.*'distirbution'.*conductivity"):
        RandomMaterialGenerator(
            conductivity={"interval": [1.0, 50.0], "distirbution": "loguniform"}
        )


def test_random_material_generator_rejects_missing_interval():
    """Test that a specification dict without an interval is rejected."""
    with pytest.raises(ValueError, match="conductivity.*missing.*'interval'"):
        RandomMaterialGenerator(conductivity={"distribution": "loguniform"})


@pytest.mark.parametrize("interval", [[1.0], [1.0, 2.0, 3.0], ["a", "b"], 5.0])
def test_random_material_generator_rejects_malformed_interval(interval):
    """Test that intervals which are not a pair of numbers are rejected."""
    with pytest.raises(ValueError, match="conductivity"):
        RandomMaterialGenerator(conductivity={"interval": interval})


def test_random_material_generator_rejects_inverted_interval():
    """Test that an interval whose minimum exceeds its maximum is rejected."""
    with pytest.raises(ValueError, match="conductivity.*min <= max"):
        RandomMaterialGenerator(conductivity=[50.0, 1.0])


def test_random_material_generator_rejects_non_sequence_spec():
    """Test that a bare scalar is not accepted as a property specification."""
    with pytest.raises(ValueError, match="conductivity.*list of two numbers or a dict"):
        RandomMaterialGenerator(conductivity=12.5)
