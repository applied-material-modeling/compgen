import sys

sys.path.append("..")

from compgen import gen2d, utils

import matplotlib.pyplot as plt
import numpy as np

import skimage

if __name__ == "__main__":
    print("Generating random images")
    gen = gen2d.RandomGenerator(nx=128, ny=128, seed=42)
    for i, structure in zip(range(5), gen):
        plt.imshow(structure.T, cmap="gray")
        plt.axis("off")
        plt.show()

    print("Generating spinodal-like structures")
    gen = gen2d.SpinodalGenerator(nx=128, ny=128, vf=0.3, l=100, bandwidth=3, seed=42)
    for i, structure in zip(range(5), gen):
        smoothed = utils.binary_smoother(
            structure,
            lambda img: skimage.util.img_as_float(
                skimage.filters.rank.mean(
                    skimage.util.img_as_ubyte(img.astype(float)),
                    footprint=skimage.morphology.disk(3),
                )
            ),
        )
        plt.imshow(smoothed.T, cmap="gray")
        plt.axis("off")
        plt.show()

    print("Generating images from a picture of a real composite.")
    seg = utils.load_and_segment("composite.jpg")
    min_px = np.min(seg.shape)
    seg = seg[:min_px, :min_px]

    plt.imshow(seg.T, cmap="gray")
    plt.axis("off")
    plt.show()

    gen = gen2d.TwoPointGenerator(seg, nx=128, ny=128, random_seed=42, radial_mask=50)

    for i, structure in zip(range(5), gen):
        smoothed = utils.binary_smoother(
            structure,
            lambda img: skimage.util.img_as_float(
                skimage.filters.rank.mean(
                    skimage.util.img_as_ubyte(img.astype(float)),
                    footprint=skimage.morphology.disk(3),
                )
            ),
        )
        smoothed = skimage.morphology.binary_opening(
            skimage.morphology.binary_closing(smoothed)
        )
        plt.imshow(smoothed.T, cmap="gray")
        plt.axis("off")
        plt.show()
