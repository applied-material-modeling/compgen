"""Image filtering utilities for preprocessing generated microstructures."""

import numpy as np
import skimage
from compgen import utils


def mean_filter(img, radius=3, periodic=True):
    """Apply a mean filter to an image.

    Args:
        img (np.ndarray): 2D or 3D image.
        radius (int): Radius of disk/ball footprint.
        periodic (bool): If True, use periodic wrapping at the boundaries.

    Returns:
        np.ndarray: Smoothed binary image.
    """
    ndim = img.ndim

    if ndim == 3:
        footprint = skimage.morphology.ball(radius)
    elif ndim == 2:
        footprint = skimage.morphology.disk(radius)
    else:
        raise ValueError("mean_filter only supports 2D and 3D images")

    def smooth(i):
        i_u8 = skimage.util.img_as_ubyte(i.astype(float))

        if periodic:
            pad_width = [(radius, radius)] * ndim
            i_u8 = np.pad(i_u8, pad_width=pad_width, mode="wrap")

        out = skimage.filters.rank.mean(i_u8, footprint=footprint)
        out = skimage.util.img_as_float(out)

        if periodic:
            slices = tuple(slice(radius, -radius) for _ in range(ndim))
            out = out[slices]

        return out

    return utils.binary_smoother(img, smooth)


def make_orthogonal(img):
    """Mirror and tile the input array to give it orthogonal periodicity.

    This works for arrays of arbitrary dimensionality by concatenating the
    array with its flipped version along each axis (processing axes from
    last to first).
    """
    arr = np.asarray(img)
    for axis in reversed(range(arr.ndim)):
        arr = np.concatenate([arr, np.flip(arr, axis=axis)], axis=axis)
    return arr


def make_periodic(img: np.ndarray, margin: int = 2) -> np.ndarray:
    """
    Make periodic for Sculpt/MOOSE workflow.

    Overwrite the first and last `margin` layers of each axis with the layer at
    index `margin`, for 2D or 3D arrays.

    A value `margin` = 2 seems to work consistently with Sculpt/MOOSE.
    """
    arr = np.array(img, copy=True)

    if arr.ndim not in (2, 3):
        raise RuntimeError(f"Expected 2D or 3D array, got {arr.ndim}D")

    if not isinstance(margin, int) or margin < 1:
        raise ValueError(f"margin must be a positive integer, got {margin}")

    if any(2 * margin >= s for s in arr.shape):
        raise ValueError(f"margin={margin} is too large for shape {arr.shape}")

    # Loop over each axis
    for ax in range(arr.ndim):
        # Slice selecting the master layer at index = margin
        master = [slice(None)] * arr.ndim
        master[ax] = slice(margin, margin + 1)

        # Slice for lower and upper boundary block
        lo = [slice(None)] * arr.ndim
        lo[ax] = slice(0, margin)
        hi = [slice(None)] * arr.ndim
        hi[ax] = slice(-margin, None)

        # Overwrite both boundary blocks using the master layer
        arr[tuple(lo)] = arr[tuple(master)]
        arr[tuple(hi)] = arr[tuple(master)]

    return arr
