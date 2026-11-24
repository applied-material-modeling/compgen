# Copyright 2026, UChicago Argonne, LLC
# All Rights Reserved
# Software Name: compgen
# By: Argonne National Laboratory
# OPEN SOURCE LICENSE (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""Tests for fixed and random material property generator behavior."""

import math
import random

import pytest

from compgen.materials import (
    ContrastMaterialGenerator,
    FilteredMaterialGenerator,
    FixedMaterialGenerator,
    RandomMaterialGenerator,
    bulk_shear_to_engineering,
    lame_to_engineering,
    resolve_elastic_constants,
    sample_contrast_pair,
)


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


def test_random_material_generator_degenerate_interval_keeps_random_stream():
    """Test that a zero-width interval still consumes one draw, so the properties
    sampled after it match plain `random.uniform` draws, as on main."""
    random.seed(11)
    props = RandomMaterialGenerator(
        poissons_ratio=[0.3, 0.3], youngs_modulus=[1.0, 50.0]
    ).next()

    random.seed(11)
    random.uniform(0.3, 0.3)
    expected = random.uniform(1.0, 50.0)

    assert props["poissons_ratio"] == 0.3
    assert props["youngs_modulus"] == expected


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


def test_lame_to_engineering_round_trip():
    """Lame parameters computed from E/nu convert back to the same E/nu."""
    E, nu = 100000.0, 0.3
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E / (2 * (1 + nu))
    E2, nu2 = lame_to_engineering(lam, mu)
    assert E2 == pytest.approx(E)
    assert nu2 == pytest.approx(nu)


def test_lame_to_engineering_rejects_unphysical():
    """Non-positive shear or bulk modulus is rejected."""
    with pytest.raises(ValueError, match="positive shear and bulk"):
        lame_to_engineering(1.0, 0.0)
    with pytest.raises(ValueError, match="positive shear and bulk"):
        lame_to_engineering(-2.0, 1.0)


def test_resolve_elastic_constants():
    """Lame props gain E/nu; other props are returned untouched."""
    props = {"lame_lambda": 57692.3, "lame_mu": 38461.5, "density": 2.7}
    resolved = resolve_elastic_constants(props)
    assert resolved["youngs_modulus"] == pytest.approx(100000.0, rel=1e-5)
    assert resolved["poissons_ratio"] == pytest.approx(0.3, rel=1e-5)
    assert resolved["lame_lambda"] == props["lame_lambda"]
    assert "youngs_modulus" not in props  # input not mutated

    eng = {"youngs_modulus": 1.0, "poissons_ratio": 0.2}
    assert resolve_elastic_constants(eng) is eng
    thermal = {"conductivity": 1.0}
    assert resolve_elastic_constants(thermal) is thermal


@pytest.mark.parametrize("cls", [FixedMaterialGenerator, RandomMaterialGenerator])
def test_generators_reject_mixed_elastic_constants(cls):
    """E/nu and Lame parameters are mutually exclusive, and Lame needs both entries."""
    with pytest.raises(ValueError, match="only one"):
        cls(youngs_modulus=[1.0, 2.0], lame_mu=[1.0, 2.0])
    with pytest.raises(ValueError, match="missing lame_mu"):
        cls(lame_lambda=[1.0, 2.0])


def test_random_generator_samples_lame():
    """Lame parameters are sampled like any other property."""
    props = RandomMaterialGenerator(lame_lambda=[1.0, 2.0], lame_mu=[3.0, 4.0]).next()
    assert 1.0 <= props["lame_lambda"] <= 2.0
    assert 3.0 <= props["lame_mu"] <= 4.0


@pytest.mark.parametrize("alpha", [0.0, 0.5, 1.0])
def test_sample_contrast_pair_in_bounds(alpha):
    """Both values stay in the interval and contrasts span both signs."""
    random.seed(1)
    pairs = [sample_contrast_pair(1.0, 1.0e4, alpha) for _ in range(2000)]
    assert all(1.0 <= a <= 1.0e4 and 1.0 <= b <= 1.0e4 for a, b in pairs)
    assert any(a > b for a, b in pairs) and any(a < b for a, b in pairs)


def test_sample_contrast_pair_alpha_zero_log_uniform_contrast():
    """With alpha = 0 the log-contrast is uniform on [-L, L]."""
    random.seed(2)
    L = math.log(1.0e4)
    c = [
        math.log(a / b)
        for a, b in (sample_contrast_pair(1.0, 1.0e4, 0.0) for _ in range(20000))
    ]
    # Uniform on [-L, L]: mean 0, mean |c| = L/2.
    assert abs(sum(c) / len(c)) < 0.05 * L
    assert sum(abs(x) for x in c) / len(c) == pytest.approx(L / 2, rel=0.03)


def test_sample_contrast_pair_degenerate_interval():
    """A zero-width interval returns the bound for both phases."""
    assert sample_contrast_pair(5.0, 5.0) == (5.0, 5.0)


def test_contrast_generator_pairs():
    """Contrast, random and fixed per-phase properties all land in the right phase."""
    random.seed(3)
    gen = ContrastMaterialGenerator(
        contrast={"youngs_modulus": {"interval": [1.0e3, 1.0e6], "alpha": 0.0}},
        A={"poissons_ratio": [0.2, 0.4]},
        B={"poissons_ratio": 0.3, "density": 2.0},
    )
    a, b = next(gen)
    assert set(a) == {"youngs_modulus", "poissons_ratio"}
    assert set(b) == {"youngs_modulus", "poissons_ratio", "density"}
    assert 1.0e3 <= a["youngs_modulus"] <= 1.0e6
    assert 1.0e3 <= b["youngs_modulus"] <= 1.0e6
    assert 0.2 <= a["poissons_ratio"] <= 0.4
    assert b["poissons_ratio"] == 0.3 and b["density"] == 2.0


def test_contrast_generator_validation():
    """Bad specifications are rejected at construction."""
    with pytest.raises(ValueError, match="strictly positive"):
        ContrastMaterialGenerator(contrast={"k": [0.0, 1.0]})
    with pytest.raises(ValueError, match="alpha"):
        ContrastMaterialGenerator(contrast={"k": {"interval": [1.0, 2.0], "alpha": -1}})
    with pytest.raises(ValueError, match="Unknown key"):
        ContrastMaterialGenerator(contrast={"k": {"interval": [1.0, 2.0], "beta": 1}})
    with pytest.raises(ValueError, match="both as a contrast"):
        ContrastMaterialGenerator(contrast={"k": [1.0, 2.0]}, A={"k": 1.0})
    with pytest.raises(ValueError, match="only one"):
        ContrastMaterialGenerator(
            contrast={"youngs_modulus": [1.0, 2.0]},
            B={"lame_mu": 1.0, "lame_lambda": 1.0},
        )


def test_sample_contrast_pair_max_contrast_log_uniform():
    """With alpha = 0 and max_contrast, |log contrast| is uniform on [0, log(max)]."""
    random.seed(4)
    M = math.log(1.0e3)
    pairs = [sample_contrast_pair(1.0e-3, 5.0e5, 0.0, 1.0e3) for _ in range(20000)]
    c = [abs(math.log(a / b)) for a, b in pairs]
    assert max(c) <= M * (1 + 1e-12)
    assert sum(c) / len(c) == pytest.approx(M / 2, rel=0.03)
    assert all(1.0e-3 <= v <= 5.0e5 for pair in pairs for v in pair)


def test_sample_contrast_pair_max_contrast_narrowed():
    """A max_contrast the interval can't reach narrows to high / low."""
    random.seed(5)
    pairs = [sample_contrast_pair(0.5, 23.0, 0.0, 1.0e3) for _ in range(5000)]
    assert all(0.5 <= v <= 23.0 for pair in pairs for v in pair)
    c = [abs(math.log(a / b)) for a, b in pairs]
    assert max(c) <= math.log(46.0) * (1 + 1e-12)
    assert sum(c) / len(c) == pytest.approx(math.log(46.0) / 2, rel=0.05)


def test_contrast_generator_rejects_bad_max_contrast():
    """max_contrast must be a number >= 1."""
    with pytest.raises(ValueError, match="max_contrast"):
        ContrastMaterialGenerator(
            contrast={"k": {"interval": [1.0, 2.0], "max_contrast": 0.5}}
        )


def test_bulk_shear_to_engineering_round_trip():
    """Bulk/shear moduli computed from E/nu convert back to the same E/nu."""
    E, nu = 100000.0, 0.3
    K = E / (3 * (1 - 2 * nu))
    G = E / (2 * (1 + nu))
    E2, nu2 = bulk_shear_to_engineering(K, G)
    assert E2 == pytest.approx(E)
    assert nu2 == pytest.approx(nu)


def test_bulk_shear_to_engineering_rejects_unphysical():
    """Non-positive bulk or shear modulus is rejected."""
    with pytest.raises(ValueError, match="must be positive"):
        bulk_shear_to_engineering(0.0, 1.0)
    with pytest.raises(ValueError, match="must be positive"):
        bulk_shear_to_engineering(1.0, -1.0)


def test_resolve_elastic_constants_bulk_shear():
    """Bulk/shear props gain E/nu and keep the given entries."""
    props = {"bulk_modulus": 83333.3333, "shear_modulus": 38461.5385}
    resolved = resolve_elastic_constants(props)
    assert resolved["youngs_modulus"] == pytest.approx(100000.0, rel=1e-6)
    assert resolved["poissons_ratio"] == pytest.approx(0.3, rel=1e-6)
    assert resolved["bulk_modulus"] == props["bulk_modulus"]


@pytest.mark.parametrize(
    "props,match",
    [
        (
            {"bulk_modulus": 1.0, "shear_modulus": 1.0, "youngs_modulus": 1.0},
            "only one",
        ),
        ({"bulk_modulus": 1.0, "shear_modulus": 1.0, "lame_mu": 1.0}, "only one"),
        ({"bulk_modulus": 1.0}, "missing shear_modulus"),
    ],
)
def test_generators_reject_bad_bulk_shear(props, match):
    """Bulk/shear is exclusive with the other pairs and must be complete."""
    with pytest.raises(ValueError, match=match):
        FixedMaterialGenerator(**props)
    with pytest.raises(ValueError, match=match):
        RandomMaterialGenerator(**{k: [v, v] for k, v in props.items()})


_KG_CONTRAST = {
    "type": "materials.ContrastMaterialGenerator",
    "params": {
        "contrast": {
            "shear_modulus": {"interval": [1.0e-3, 5.0e5], "alpha": 0.0, "max_contrast": 1.0e3},
            "bulk_modulus": {"interval": [10.0, 3.0e5], "alpha": 0.0, "max_contrast": 1.0e3},
        }
    },
}


def test_filtered_generator_bounds_poissons_ratio_of_pairs():
    """Pairs sampled as bulk/shear moduli are redrawn until both phases have nu <= 0.45."""
    random.seed(7)
    gen = FilteredMaterialGenerator(
        generator=_KG_CONTRAST, bounds={"poissons_ratio": [None, 0.45]}
    )
    for _ in range(200):
        a, b = next(gen)
        for p in (a, b):
            nu = bulk_shear_to_engineering(p["bulk_modulus"], p["shear_modulus"])[1]
            assert nu <= 0.45
    # The unfiltered distribution violates the bound often, so some draws were rejected
    assert gen.accepted == 200 and gen.attempts > gen.accepted


def test_filtered_generator_single_dicts_and_two_sided_bounds():
    """Single-phase generators are filtered too, with both ends of the bound applied."""
    random.seed(8)
    gen = FilteredMaterialGenerator(
        generator={
            "type": "materials.RandomMaterialGenerator",
            "params": {"youngs_modulus": [1.0, 10.0], "poissons_ratio": [-0.5, 0.5]},
        },
        bounds={"poissons_ratio": [0.0, 0.3], "youngs_modulus": [2.0, None]},
    )
    for _ in range(100):
        p = next(gen)
        assert 0.0 <= p["poissons_ratio"] <= 0.3 and p["youngs_modulus"] >= 2.0


def test_filtered_generator_validation_and_give_up():
    """Bad specifications are rejected, and impossible bounds fail after max_attempts."""
    fixed = {"type": "materials.FixedMaterialGenerator",
             "params": {"youngs_modulus": 1.0, "poissons_ratio": 0.49}}
    with pytest.raises(ValueError, match="generator"):
        FilteredMaterialGenerator(bounds={"poissons_ratio": [None, 0.45]})
    with pytest.raises(ValueError, match="at least one bound"):
        FilteredMaterialGenerator(generator=fixed)
    with pytest.raises(ValueError, match=r"\[min, max\]"):
        FilteredMaterialGenerator(generator=fixed, bounds={"poissons_ratio": 0.45})
    with pytest.raises(ValueError, match="min > max"):
        FilteredMaterialGenerator(generator=fixed, bounds={"poissons_ratio": [0.4, 0.3]})
    gen = FilteredMaterialGenerator(
        generator=fixed, bounds={"poissons_ratio": [None, 0.45]}, max_attempts=5
    )
    with pytest.raises(RuntimeError, match="after 5 draws"):
        next(gen)
    gen = FilteredMaterialGenerator(generator=fixed, bounds={"density": [0.0, 1.0]})
    with pytest.raises(KeyError, match="density"):
        next(gen)
