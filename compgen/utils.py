from skimage.io import imread
from skimage.color import rgb2gray
from skimage.segmentation import chan_vese


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
