"""Tests for filters."""

import pytest
import numpy as np
from compgen.filters import mean_filter, make_orthogonal, make_periodic, defeature


@pytest.mark.parametrize("periodic", [False, True])
def test_mean_filter_periodic_parameter(periodic):
    """
    A single bright pixel in the top-left corner should affect the far-right edge
    only when periodic wrapping is enabled.
    """

    img = np.zeros((7, 7), dtype=bool)
    img[0, 0] = True

    out = mean_filter(img, radius=1, periodic=periodic)

    assert out.shape == img.shape

    if periodic:
        assert out[0, -1] > 0
    else:
        assert out[0, -1] == 0


def test_mean_filter_rejects_non_2d_or_3d():
    """
    Verify that mean_filter raises a ValueError when given input
    with unsupported dimensionality.
    """
    img = np.zeros((2, 2, 2, 2), dtype=bool)

    with pytest.raises(ValueError, match="only supports 2D and 3D images"):
        mean_filter(img)


def test_make_orthogonal_tiles_and_flips():
    """Test that make_orthogonal correctly creates a larger image by tiling
    and flipping the input."""
    img = np.array([[1, 2, 3], [4, 5, 6]])
    out = make_orthogonal(img)

    top = np.hstack([img, np.fliplr(img)])
    expected = np.vstack([top, np.flipud(top)])

    assert out.shape == expected.shape
    assert np.array_equal(out, expected)


def test_defeature_removes_small_island():
    """A small interior island is reassigned to the surrounding phase."""
    img = np.zeros((20, 20), dtype=bool)
    img[5:7, 5:7] = True  # 4-cell island
    out = defeature(img, min_size=5)
    assert out.sum() == 0


def test_defeature_keeps_large_feature():
    """A feature at/above the threshold survives."""
    img = np.zeros((20, 20), dtype=bool)
    img[2:8, 2:8] = True  # 36-cell feature
    out = defeature(img, min_size=5)
    assert out.sum() == img.sum()


def test_defeature_noop_when_min_size_zero():
    """min_size=0 is a no-op."""
    img = np.random.rand(16, 16) > 0.5
    out = defeature(img, min_size=0)
    assert np.array_equal(out, img)


def test_defeature_periodic_wrapping_island():
    """An island split across opposite edges is one component when periodic.

    Size 6 split 3+3 across the x-seam: periodic keeps it (>= min_size 5),
    non-periodic sees two size-3 pieces and removes both.
    """
    img = np.zeros((20, 20), dtype=bool)
    img[5, [0, 1, 2]] = True
    img[5, [17, 18, 19]] = True

    assert defeature(img, min_size=5, periodic=True).sum() == 6
    assert defeature(img, min_size=5, periodic=False).sum() == 0


def test_defeature_periodic_roll_invariant():
    """defeature(roll(img)) == roll(defeature(img)) for periodic mode."""
    rng = np.random.default_rng(0)
    img = rng.random((40, 40)) > 0.6
    shift = (7, 13)
    lhs = defeature(np.roll(img, shift, (0, 1)), min_size=4, periodic=True)
    rhs = np.roll(defeature(img, min_size=4, periodic=True), shift, (0, 1))
    assert np.array_equal(lhs, rhs)


def test_defeature_3d():
    """defeature works on 3D images."""
    img = np.zeros((12, 12, 12), dtype=bool)
    img[5:7, 5:7, 5:7] = True  # 8-cell island
    assert defeature(img, min_size=9).sum() == 0
    assert defeature(img, min_size=4).sum() == 8


@pytest.mark.parametrize("margin", [1, 2, 10])
def test_make_periodic_margins(margin):
    """Test that make_periodic correctly creates equal margins."""
    img = np.random.rand(48, 48, 48) > 0.65
    out = make_periodic(img, margin)

    assert np.array_equal(out[:margin, :, :], out[-margin:, :, :])
    assert np.array_equal(out[:, :margin, :], out[:, -margin:, :])
    assert np.array_equal(out[:, :, :margin], out[:, :, -margin:])
