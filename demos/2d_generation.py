import sys

sys.path.append("..")

from compgen import gen, filters, utils

import matplotlib.pyplot as plt
import numpy as np

import skimage

if __name__ == "__main__":
    seed = 42
    vf = 0.3
    n = 128

    print("Generating random images")
    generator = gen.RandomGenerator(N=[n, n], vf=vf, random_seed=seed)
    for i, structure in zip(range(5), generator):
        structure = filters.make_orthogonal(structure)
        plt.imshow(structure.T, cmap="gray")
        plt.axis("off")
        plt.show()

    print("Generating spinodal-like structures")
    generator = gen.SpinodalGenerator(
        N=[n, n], vf=vf, l=100, bandwidth=3, random_seed=seed
    )
    for i, structure in zip(range(5), generator):
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

    print("Generating images from a picture of a real composite.")
    seg = utils.load_and_segment("composite.jpg")
    min_px = np.min(seg.shape)
    seg = seg[:min_px, :min_px]
    seg = filters.make_orthogonal(seg)

    plt.imshow(seg.T, cmap="gray")
    plt.axis("off")
    plt.show()

    generator = gen.TwoPointGenerator(
        N=[n, n], reference_image=seg, random_seed=seed, radial_mask=50
    )

    for i, structure in zip(range(5), generator):
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
        smoothed = filters.make_orthogonal(smoothed)
        plt.imshow(smoothed.T, cmap="gray")
        plt.axis("off")
        plt.show()
