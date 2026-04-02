"""General utilities for image segmentation, smoothing, and JSON config merging."""

import json
import os

import numpy as np
from skimage.io import imread
from skimage.color import rgb2gray
from skimage.segmentation import chan_vese
from skimage.transform import resize


def binary_smoother(binary_image, smoothing_function):
    """Apply a smoothing function to a binary image and re-binarize it.

    Args:
        binary_image (np.ndarray): 2D binary array.
        smoothing_function (callable): Function that takes a 2D array and
            returns a smoothed 2D array.

    Returns:
        np.ndarray: Smoothed binary image.
    """
    vf = np.mean(binary_image)
    smoothed = smoothing_function(binary_image)
    thresh = np.quantile(smoothed, 1 - vf)
    smoothed = smoothed >= thresh

    return smoothed


def standardize_image(image, shape=None, dtype=None):
    """
    Resize/binarize an image (2D or 3D).

    Args:
        image (np.ndarray): Input image with shape (nx, ny) or (nx, ny, nz).
        shape (tuple[int, ...], optional): Target shape, must be either
            (nx, ny) for 2D input or (nx, ny, nz) for 3D input.
        dtype (type, optional): Output dtype for binarization.
    """
    img = np.asarray(image, dtype=float)

    if img.ndim not in (2, 3):
        raise ValueError(
            f"image must be 2D or 3D, got {img.ndim}D with shape {img.shape}"
        )

    if shape is not None:
        shape = tuple(shape)

        if len(shape) != img.ndim:
            raise ValueError(
                f"shape dimensionality must match image dimensionality: "
                f"got image shape {img.shape} ({img.ndim}D)"
                f"and target shape {shape} ({len(shape)}D)"
            )

        img = resize(
            img,
            shape,
            order=1,
            mode="reflect",
            anti_aliasing=True,
        )

    if dtype is not None:
        img = (img > 0.5).astype(dtype)

    return img


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


def load_json(fnames):
    """Load and merge multiple JSON files into a single dictionary.

    Substitute environment variables in the JSON values if present.

    Args:
        fnames (list[str]): List of JSON file paths.
    Returns:
        dict: Merged dictionary.
    """
    dicts = []
    for fname in fnames:
        try:
            with open(fname, "r", encoding="utf-8") as f:
                str_json = f.read()
                sub_str = os.path.expandvars(str_json)
                dicts.append(json.loads(sub_str))
        except Exception as e:
            raise RuntimeError(f"Error loading JSON file {fname}: {e}") from e

    return dict_merge(dicts)


def dict_merge(dict_list):
    """Merge a list of recursive dictionaries of dictionaries.

    Args:
        dict_list (list[dict]): List of dictionaries to merge.

    Returns:
        dict: Merged dictionary.

    Raises:
        ValueError: If a key exists in multiple dicts with non-dict values or
            incompatible types.
        TypeError: If the input is not a list of dicts.
    """
    if not isinstance(dict_list, list):
        raise TypeError("dict_list must be a list of dictionaries")

    merged = {}
    for d in dict_list:
        if not isinstance(d, dict):
            raise TypeError("dict_list must be a list of dictionaries")
        merged = _merge_dicts_recursive(merged, d)

    return merged


def _merge_dicts_recursive(a, b):
    """Recursively merge two dictionaries with strict conflict handling."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        raise TypeError("Both inputs must be dictionaries")

    merged = dict(a)
    for key, b_val in b.items():
        if key not in merged:
            merged[key] = b_val
            continue

        a_val = merged[key]
        if isinstance(a_val, dict) and isinstance(b_val, dict):
            merged[key] = _merge_dicts_recursive(a_val, b_val)
        else:
            raise ValueError(f"Conflict at key '{key}': cannot merge non-dict values")

    return merged
