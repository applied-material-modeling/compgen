import sys

sys.path.append("..")

from compgen import gen2d, utils

import matplotlib.pyplot as plt
import numpy as np

if __name__ == "__main__":
    seg = utils.load_and_segment("composite.jpg")
    min_px = np.min(seg.shape)
    seg = seg[:min_px, :min_px]

    plt.imshow(seg.T, cmap="gray")
    plt.axis("off")
    plt.show()

    gen = gen2d.SpectralGenerator(seg, nx=128, ny=128, seed=42)

    for i, structure in zip(range(5), gen):
        plt.imshow(structure.T, cmap="gray")
        plt.axis("off")
        plt.show()
