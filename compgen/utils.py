import numpy as np

import skimage as sk
from skimage.io import imread
from skimage.color import rgb2gray
from skimage.segmentation import chan_vese


def binary_smoother(binary_image, smoothing_function):
    """Apply a smoothing function to a binary image and re-binarize it.

    Args:
        binary_image (np.ndarray): 2D binary array.
        smoothing_function (callable): Function that takes a 2D array and returns a smoothed 2D array.

    Returns:
        np.ndarray: Smoothed binary image.
    """
    vf = np.mean(binary_image)
    smoothed = smoothing_function(binary_image)
    thresh = np.quantile(smoothed, 1 - vf)
    smoothed = smoothed >= thresh

    return smoothed


def load_and_segment(fname, miter=100):
    """Load an image from file and do Chan-Vese segmentation.

    Args:
        fname (str): Path to the image file.

    Keyword Args:
        miter (int): Maximum number of iterations for Chan-Vese segmentation. Defaults to 100.
    """
    img = imread(fname)
    if img.shape[-1] == 3:
        img = rgb2gray(img)

    cv = chan_vese(img, max_num_iter=miter)
    return cv.T  # ij convention
