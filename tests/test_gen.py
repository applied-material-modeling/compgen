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

"""Tests for structure generation utilities and stochastic generator outputs."""

import numpy as np
import pytest

from compgen.gen import (
    RandomGenerator,
    SpinodalGenerator,
    TwoPointGenerator,
    Reconstruction2D,
)


@pytest.mark.parametrize(
    "shape,vf",
    [
        ([128], 0.25),
        ([64, 64], 0.3),
        ([32, 32, 32], 0.1),
    ],
)
def test_random_generator_shape_and_vf(shape, vf):
    """Test that the RandomGenerator produces images of the correct shape and
    approximate volume fraction."""
    gen = RandomGenerator(shape, vf, random_seed=123)
    img = gen.sample()

    assert img.shape == tuple(shape)

    total = int(np.prod(shape))
    expected = int(total * vf)
    assert int(img.sum()) == expected


@pytest.mark.parametrize(
    "shape,vf,l,bandwidth",
    [
        ([128], 0.35, 16.0, 0.4),
        ([64, 64], 0.4, 12.0, 0.35),
        ([32, 32, 32], 0.3, 10.0, 0.3),
    ],
)
def test_spinodal_generator_shape_and_vf(shape, vf, l, bandwidth):
    """Test that the SpinodalGenerator produces images of the correct shape and
    approximate volume fraction."""
    gen = SpinodalGenerator(shape, vf, l, bandwidth, random_seed=321)
    img = gen.sample()

    assert img.shape == tuple(shape)

    frac = img.mean()
    assert np.isclose(frac, vf, atol=0.05)


def test_two_point_generator_shape_and_vf():
    """Test that the TwoPointGenerator produces images of the correct shape and
    approximate volume fraction."""
    rng = np.random.default_rng(7)
    reference_image = rng.random((48, 48)) > 0.65
    gen = TwoPointGenerator([48, 48], reference_image, random_seed=11)

    img = gen.sample()
    assert img.shape == reference_image.shape

    ref_vf = reference_image.mean()
    assert np.isclose(img.mean(), ref_vf, atol=0.1)


@pytest.mark.parametrize(
    "path,descriptors",
    [
        (
            "demos/complete/reconstruction/demo_microstructures/ms_0.npy",
            {"Variation": 10.0, "Correlations": 1.0},
        ),
        (
            "demos/complete/reconstruction/demo_microstructures",
            {"VolumeFractions": 1.0, "TwoPointCorrelations": 1.0},
        ),
    ],
)
def test_reconstruction_generator_shape_and_vf(path, descriptors):
    """Test that the Reconstruction2D generator produces images of the
    correct shape and approximate volume fraction."""
    final_shape = (48, 48)
    limit_to = 4
    gen = Reconstruction2D(
        N=final_shape,
        target_path=path,
        descriptors=descriptors,
        limit_to=limit_to,
        random_seed=42,
    )
    img = gen.sample()

    assert img.shape == final_shape
    assert np.isclose(img.mean(), gen.target_vf, atol=0.25)
