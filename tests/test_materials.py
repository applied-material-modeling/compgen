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
