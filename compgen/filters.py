from compgen import utils

import skimage


def mean_filter(img, radius=3):
    """Apply a mean filter to an image.

    Args:
        img (np.ndarray): ND array representing the image.
        radius (int): Radius of the disk footprint for the mean filter. Defaults to 3.

    Returns:
        np.ndarray: Smoothed image.
    """
    if len(img.shape) == 3:
        footprint = skimage.morphology.ball(radius)
    elif len(img.shape) == 2:
        footprint = skimage.morphology.disk(radius)
    else:
        raise ValueError("mean_filter only supports 2D and 3D images")

    return utils.binary_smoother(
        img,
        lambda i: skimage.util.img_as_float(
            skimage.filters.rank.mean(
                skimage.util.img_as_ubyte(i.astype(float)),
                footprint=footprint,
            )
        ),
    )
