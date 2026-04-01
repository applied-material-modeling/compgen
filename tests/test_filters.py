"""Tests for filters."""

import pytest
import numpy as np
from compgen.filters import mean_filter


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
