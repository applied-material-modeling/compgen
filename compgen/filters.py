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
