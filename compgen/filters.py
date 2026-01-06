from compgen import utils

import skimage


def mean_filter(img, radius=3):
    """Apply a mean filter to an image.

    Args:
        img (np.ndarray): 2D array representing the image.
        radius (int): Radius of the disk footprint for the mean filter. Defaults to 3.

    Returns:
        np.ndarray: Smoothed image.
    """
    return utils.binary_smoother(
        img,
        lambda i: skimage.util.img_as_float(
            skimage.filters.rank.mean(
                skimage.util.img_as_ubyte(i.astype(float)),
                footprint=skimage.morphology.disk(radius),
            )
        ),
    )
