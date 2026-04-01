"""Tests for structure generation utilities and stochastic generator outputs."""

import numpy as np
import pytest

from compgen.gen import (
    RandomGenerator,
    SpinodalGenerator,
    TwoPointGenerator,
    Reconstruction2D,
    make_orthogonal,
    make_periodic,
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


def test_make_orthogonal_tiles_and_flips():
    """Test that make_orthogonal correctly creates a larger image by tiling
    and flipping the input."""
    img = np.array([[1, 2, 3], [4, 5, 6]])
    out = make_orthogonal(img)

    top = np.hstack([img, np.fliplr(img)])
    expected = np.vstack([top, np.flipud(top)])

    assert out.shape == expected.shape
    assert np.array_equal(out, expected)


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


@pytest.mark.parametrize("margin", [1, 2, 10])
def test_make_periodic_margins(margin):
    """Test that make_periodic correctly creates equal margins."""
    img = np.random.rand(48, 48, 48) > 0.65
    out = make_periodic(img, margin)

    assert np.array_equal(out[:margin, :, :], out[-margin:, :, :])
    assert np.array_equal(out[:, :margin, :], out[:, -margin:, :])
    assert np.array_equal(out[:, :, :margin], out[:, :, -margin:])
