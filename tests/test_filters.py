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

"""Tests for filters."""

import pytest
import numpy as np
from compgen.filters import (
    FilterInputError,
    NonBinaryImageError,
    mean_filter,
    make_orthogonal,
    make_periodic,
    defeature,
)

# (filter, kwargs) for the checks that must hold for every filter alike.
ALL_FILTERS = [
    (mean_filter, {"radius": 0.1}),
    (mean_filter, {"radius": 0.1, "method": "fft"}),
    (make_orthogonal, {}),
    (make_periodic, {"margin_cells": 2, "shift": False}),
    (defeature, {"min_size": 0.1}),
]


@pytest.mark.parametrize("filt,kwargs", ALL_FILTERS)
@pytest.mark.parametrize("shape", [(12, 12), (8, 8, 8)])
def test_filters_return_bool(filt, kwargs, shape):
    """Every filter returns bool, so a chain cannot change the image dtype."""
    img = np.random.default_rng(0).random(shape) > 0.5
    assert filt(img, **kwargs).dtype == np.bool_


@pytest.mark.parametrize("filt,kwargs", ALL_FILTERS)
@pytest.mark.parametrize("dtype", [np.uint8, np.int64, np.float64])
def test_filters_accept_zero_one_numeric(filt, kwargs, dtype):
    """0/1 numeric input is accepted and normalized to bool."""
    ref = np.random.default_rng(1).random((12, 12)) > 0.5
    out = filt(ref.astype(dtype), **kwargs)
    assert out.dtype == np.bool_
    assert np.array_equal(out, filt(ref, **kwargs))


@pytest.mark.parametrize("filt,kwargs", ALL_FILTERS)
def test_filters_reject_non_binary(filt, kwargs):
    """Grayscale input is rejected rather than silently coerced."""
    img = np.random.default_rng(2).random((12, 12))
    with pytest.raises(NonBinaryImageError):
        filt(img, **kwargs)


@pytest.mark.parametrize("method", ["rank", "fft"])
@pytest.mark.parametrize("periodic", [False, True])
def test_mean_filter_periodic_parameter(periodic, method):
    """
    A single bright pixel in the top-left corner should affect the far-right edge
    only when periodic wrapping is enabled.
    """

    img = np.zeros((7, 7), dtype=bool)
    img[0, 0] = True

    out = mean_filter(img, radius=0.1, periodic=periodic, method=method)  # 1 px

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


@pytest.mark.parametrize("periodic", [False, True])
@pytest.mark.parametrize("shape", [(40, 40), (16, 16, 16)])
def test_mean_filter_fft_matches_rank(shape, periodic):
    """At small radii (no uint8 ties) the FFT path reproduces rank.mean."""
    from scipy import ndimage

    noise = np.random.default_rng(4).random(shape)
    img = ndimage.gaussian_filter(noise, 2, mode="wrap") > 0.5
    ref = mean_filter(img, radius=0.1, periodic=periodic)
    out = mean_filter(img, radius=0.1, periodic=periodic, method="fft")
    assert np.array_equal(out, ref)


def test_mean_filter_fft_footprint_larger_than_image():
    """A footprint wider than the image wraps, like the rank path's wrap pad."""
    img = np.random.default_rng(5).random((6, 6)) > 0.5
    out = mean_filter(img, radius=1.0, method="fft")
    assert out.shape == img.shape


def test_mean_filter_rejects_unknown_method():
    with pytest.raises(FilterInputError, match="method"):
        mean_filter(np.zeros((8, 8), dtype=bool), method="median")


def test_make_orthogonal_tiles_and_flips():
    """Test that make_orthogonal correctly creates a larger image by tiling
    and flipping the input."""
    img = np.array([[1, 1, 0], [0, 1, 0]], dtype=bool)  # asymmetric on both axes
    out = make_orthogonal(img)

    top = np.hstack([img, np.fliplr(img)])
    expected = np.vstack([top, np.flipud(top)])

    assert out.shape == expected.shape
    assert np.array_equal(out, expected)


def test_defeature_removes_small_island():
    """A small interior island is reassigned to the surrounding phase."""
    img = np.zeros((20, 20), dtype=bool)
    img[5:7, 5:7] = True  # 4-cell island
    out = defeature(img, min_size=1.2 / 20)  # R = 1.2 px: ceil(pi R^2) = 5 cells
    assert out.sum() == 0


def test_defeature_keeps_large_feature():
    """A feature at/above the threshold survives."""
    img = np.zeros((20, 20), dtype=bool)
    img[2:8, 2:8] = True  # 36-cell feature
    out = defeature(img, min_size=1.2 / 20)
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

    assert defeature(img, min_size=1.2 / 20, periodic=True).sum() == 6
    assert defeature(img, min_size=1.2 / 20, periodic=False).sum() == 0


@pytest.mark.parametrize("shape,r_px,n_cells", [((20, 20), 1.2, 5), ((12, 12, 12), 1.27, 9)])
def test_defeature_threshold_from_radius(shape, r_px, n_cells):
    """The cell threshold is ceil(pi R^2) or ceil(4/3 pi R^3), R in pixels."""
    min_size = r_px / min(shape)
    for size, kept in ((n_cells - 1, False), (n_cells, True)):
        img = np.zeros(shape, dtype=bool)
        img.flat[:size] = True  # a line of `size` cells along the last axis
        assert defeature(img, min_size=min_size, periodic=False).any() == kept


def test_mean_filter_radius_rounds_up():
    """The radius rounds up to whole pixels; 0 is a no-op."""
    img = np.random.default_rng(3).random((20, 20)) > 0.5
    assert np.array_equal(mean_filter(img, radius=0.01), mean_filter(img, radius=0.05))
    assert np.array_equal(mean_filter(img, radius=0), img)


def test_defeature_periodic_roll_invariant():
    """defeature(roll(img)) == roll(defeature(img)) for periodic mode."""
    rng = np.random.default_rng(0)
    img = rng.random((40, 40)) > 0.6
    shift = (7, 13)
    lhs = defeature(np.roll(img, shift, (0, 1)), min_size=1.05 / 40, periodic=True)
    rhs = np.roll(defeature(img, min_size=1.05 / 40, periodic=True), shift, (0, 1))
    assert np.array_equal(lhs, rhs)


def test_defeature_3d():
    """defeature works on 3D images."""
    img = np.zeros((12, 12, 12), dtype=bool)
    img[5:7, 5:7, 5:7] = True  # 8-cell island
    assert defeature(img, min_size=1.27 / 12).sum() == 0
    assert defeature(img, min_size=0.95 / 12).sum() == 8


@pytest.mark.parametrize("margin", [1, 2, 10])
def test_make_periodic_margins(margin):
    """Test that make_periodic correctly creates equal margins."""
    img = np.random.rand(48, 48, 48) > 0.65
    out = make_periodic(img, margin)

    assert np.array_equal(out[:margin, :, :], out[-margin:, :, :])
    assert np.array_equal(out[:, :margin, :], out[:, -margin:, :])
    assert np.array_equal(out[:, :, :margin], out[:, :, -margin:])


def _margin_layers(ndim, ax, margin, center=False):
    """Index tuples of the master layer and the low/high margins along `ax`."""
    master, lo, hi = ([slice(None)] * ndim for _ in range(3))
    if center:
        master[ax] = slice(0, 1)
        lo[ax] = slice(1, margin + 1)
    else:
        master[ax] = slice(margin, margin + 1)
        lo[ax] = slice(0, margin)
    hi[ax] = slice(-margin, None)
    return tuple(master), tuple(lo), tuple(hi)


def _make_periodic_reference(img, margin, shift, center=False):
    """The original make_periodic: try every circular shift one by one."""
    arr = img.astype(int)
    for ax in range(arr.ndim):
        master, lo, hi = _margin_layers(arr.ndim, ax, margin, center)
        if shift:
            costs = []
            for i in range(arr.shape[ax]):
                a = np.roll(arr, shift=i, axis=ax)
                costs.append(
                    np.sum(np.abs(a[hi] - a[master]) + np.abs(a[lo] - a[master]))
                )
            arr = np.roll(arr, shift=int(np.argmin(costs)), axis=ax)
        arr[lo] = arr[master]
        arr[hi] = arr[master]
    return arr.astype(bool)


@pytest.mark.parametrize("shape", [(40, 52), (17, 24, 20)])
@pytest.mark.parametrize("margin", [1, 2, 5])
@pytest.mark.parametrize("shift", [False, True])
@pytest.mark.parametrize("center", [False, True])
def test_make_periodic_matches_reference(shape, margin, shift, center):
    """The vectorized shift search picks the same shift as trying every shift
    one by one, including ties (stripes and a blank image repeat costs)."""
    rng = np.random.default_rng(margin)
    stripes = np.zeros(shape, dtype=bool)
    stripes[::4] = True
    for img in (rng.random(shape) > 0.6, stripes, np.zeros(shape, dtype=bool)):
        out = make_periodic(img, margin_cells=margin, shift=shift, center=center)
        assert np.array_equal(out, _make_periodic_reference(img, margin, shift, center))


@pytest.mark.parametrize("shape", [(30, 34), (14, 16, 18)])
@pytest.mark.parametrize("center", [False, True])
def test_make_periodic_block(shape, center):
    """Each face gets 2 * margin + 1 identical layers (n - margin, ..., margin),
    copied from layer `margin`, or from the face layer 0 if center."""
    margin = 2
    img = np.random.default_rng(1).random(shape) > 0.5
    out = make_periodic(img, margin_cells=margin, center=center)
    src = 0 if center else margin
    for ax in range(img.ndim):
        n = img.shape[ax]
        ref = np.take(out, src, axis=ax)
        for i in [*range(n - margin, n), *range(margin + 1)]:
            assert np.array_equal(np.take(out, i, axis=ax), ref)
    # without shift, the copied layer of the first axis is the input's own
    sl = (slice(margin + 1, -margin),) * (img.ndim - 1)
    assert np.array_equal(out[(src, *sl)], img[(src, *sl)])


@pytest.mark.parametrize(
    "cells,refinement,layers", [(1, 0, 1), (7, 0, 7), (1.3, 0, 2), (2, 1, 4), (2.5, 2, 10)]
)
def test_make_periodic_margin_cells_are_mesh_cells(cells, refinement, layers):
    """margin_cells counts mesh cells: ceil(cells * 2**refinement) pixel layers."""
    img = np.random.default_rng(4).random((50, 60)) > 0.5
    out = make_periodic(img, margin_cells=cells, center=True, refinement=refinement)
    for i in [*range(1, layers + 1), *range(-layers, 0)]:
        assert np.array_equal(out[i], out[0])
    assert not np.array_equal(out[layers + 1], out[0])


def test_make_periodic_leaves_input_unchanged():
    """The filter works on a copy of a bool input."""
    img = np.random.default_rng(0).random((16, 16)) > 0.5
    before = img.copy()
    make_periodic(img, margin_cells=2, shift=True)
    assert np.array_equal(img, before)


@pytest.mark.parametrize(
    "filt,kwargs,img",
    [
        (mean_filter, {}, np.zeros((2, 2, 2, 2), dtype=bool)),
        (make_periodic, {}, np.zeros(8, dtype=bool)),
        (make_periodic, {"margin_cells": 0}, np.zeros((8, 8), dtype=bool)),
        (make_periodic, {"margin_cells": -1}, np.zeros((8, 8), dtype=bool)),
        (make_periodic, {"margin_cells": 99}, np.zeros((8, 8), dtype=bool)),
    ],
)
def test_deterministic_errors_are_filter_input_errors(filt, kwargs, img):
    """Shape/param rejections share one type so the runner can abort on them."""
    with pytest.raises(FilterInputError):
        filt(img, **kwargs)
