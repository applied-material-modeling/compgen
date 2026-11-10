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
    ParticleGenerator,
    VoronoiGenerator,
    FromNumpyGenerator,
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


@pytest.mark.parametrize(
    "N,vf,kind,shape_params,buffer",
    [
        ([64, 64], 0.3, "disks", {"size_m": 0.1}, 1.0),
        (
            [64, 64],
            0.3,
            "ellipses",
            {"size_m": 0.1, "ratio_m": 2.0, "theta_m": 45.0},
            0.5,
        ),
        ([64, 64], 0.3, "ellipses", {"size_m": 0.05, "ratio_m": 10.0}, None),
        ([64, 64], 0.6, "laminae2", {"size_m": 0.1, "size_s": 0.05}, 0.4),
        ([32, 32, 32], 0.2, "spheres", {"size_m": 0.4}, 0.7),
        ([32, 32, 32], 0.1, "spheroids", {"size_m": 0.3, "ratio_m": 2.0}, 0.7),
        ([32, 32, 32], 0.4, "fibers", {"size_m": 0.2}, 0.6),
        ([32, 32, 32], 0.5, "laminae3", {"size_m": 0.1, "size_s": 0.05}, 1.0),
    ],
)
def test_particle_generator_shape_and_vf(N, vf, kind, shape_params, buffer):
    """Test that the ParticleGenerator produces images of the correct shape and
    approximate volume fraction."""
    gen = ParticleGenerator(
        N=N,
        vf=vf,
        kind=kind,
        shape_params=shape_params,
        buffer=buffer,
        random_seed=42,
    )
    img = gen.sample()
    assert img.shape == tuple(N)
    frac = img.mean()
    assert np.isclose(frac, vf, atol=0.1) or np.isclose(frac, 1.0 - vf, atol=0.1)


@pytest.mark.parametrize(
    "N,grain_size,thickness,lloyd_iter",
    [
        ([64, 64], 0.25, 0.03, 0),
        ([64, 64], [0.15, 0.25], 0.05, 0),
        ([64, 64], 0.2, 0.04, 5),
        ([32, 32, 32], 0.35, 0.05, 0),
        ([32, 32, 32], 0.4, 0.06, 3),
    ],
)
def test_voronoi_generator_shape_and_dtype(N, grain_size, thickness, lloyd_iter):
    """Test that the VoronoiGenerator produces bool images of the correct shape,
    containing both phases."""
    gen = VoronoiGenerator(
        N=N,
        grain_size=grain_size,
        thickness=thickness,
        lloyd_iter=lloyd_iter,
        random_seed=42,
    )
    img = gen.sample()
    assert img.shape == tuple(N)
    assert img.dtype == bool
    # Both grains and boundaries should be present for these parameters.
    assert img.any() and not img.all()


@pytest.mark.parametrize("dtype", [bool, np.uint8, np.int64, np.float32])
def test_from_numpy_generator_normalizes_dtype(tmp_path, dtype):
    """Whatever the file's dtype, the generator yields bool with content intact."""
    ref = np.random.default_rng(3).random((4, 16, 16)) > 0.5
    path = tmp_path / "structures.npy"
    np.save(path, ref.astype(dtype))

    gen = FromNumpyGenerator(str(path))
    for expected in ref:
        img = gen.sample()
        assert img.dtype == bool
        assert np.array_equal(img, expected)


def test_from_numpy_generator_binarizes_grayscale(tmp_path):
    """A grayscale file is thresholded at 0.5 rather than passed through."""
    data = np.random.default_rng(4).random((2, 16, 16))
    path = tmp_path / "grayscale.npy"
    np.save(path, data)

    img = FromNumpyGenerator(str(path)).sample()
    assert img.dtype == bool
    assert np.array_equal(img, data[0] > 0.5)


def test_all_generators_return_bool():
    """Every generator honours the bool contract in the base-class docstring."""
    rng = np.random.default_rng(5)
    generators = [
        RandomGenerator([32, 32], 0.4, random_seed=0),
        SpinodalGenerator([32, 32], 0.4, 8.0, 0.2, random_seed=0),
        TwoPointGenerator([32, 32], rng.random((32, 32)) > 0.6, random_seed=0),
        VoronoiGenerator([32, 32], 0.25, 0.2, random_seed=0),
        ParticleGenerator([32, 32], 0.3, "disks", {"size_m": 0.2}, random_seed=0),
        RandomGenerator([16, 16, 16], 0.4, random_seed=0),
        VoronoiGenerator([16, 16, 16], 0.4, 0.2, random_seed=0),
        ParticleGenerator([16, 16, 16], 0.3, "spheres", {"size_m": 0.3}, random_seed=0),
    ]
    for gen in generators:
        assert gen.sample().dtype == bool, type(gen).__name__
