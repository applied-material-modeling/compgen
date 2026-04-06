"""Tests for filters."""

import pytest
import numpy as np
from compgen.filters import mean_filter, make_orthogonal, make_periodic


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


@pytest.mark.parametrize("margin", [1, 2, 10])
def test_make_periodic_margins(margin):
    """Test that make_periodic correctly creates equal margins."""
    img = np.random.rand(48, 48, 48) > 0.65
    out = make_periodic(img, margin)

    assert np.array_equal(out[:margin, :, :], out[-margin:, :, :])
    assert np.array_equal(out[:, :margin, :], out[:, -margin:, :])
    assert np.array_equal(out[:, :, :margin], out[:, :, -margin:])
