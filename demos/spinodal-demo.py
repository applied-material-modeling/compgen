import sys

sys.path.append("..")

from compgen import gen, filters, utils

import matplotlib.pyplot as plt
import numpy as np

import skimage

if __name__ == "__main__":

    for i in range(100):
        generator = gen.SpinodalGenerator(
            N=[64, 64], vf=[0.01, 0.99], l=[50, 150], bandwidth=[1, 5]
        )
        structure = next(generator)
        smoothed = utils.binary_smoother(
            structure,
            lambda img: skimage.util.img_as_float(
                skimage.filters.rank.mean(
                    skimage.util.img_as_ubyte(img.astype(float)),
                    footprint=skimage.morphology.disk(3),
                )
            ),
        )
        smoothed = filters.make_orthogonal(smoothed)
        plt.imshow(smoothed.T, cmap="gray")
        plt.axis("off")
        plt.show()
