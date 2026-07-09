import sys
import os
import matplotlib.pyplot as plt
import numpy as np
import skimage

sys.path.append("..")
from compgen import gen, utils

if __name__ == "__main__":
    N = [256, 256]
    vf = 0.25
    bandwidth = 0.05
    seeds = [42, 100, 2026] # use fixed seed for deterministic comparison

    for l_val in [10.0, 30.0, 50.0]:
        generator = gen.SpinodalGenerator(
            N=N, vf=vf, l=l_val, bandwidth=bandwidth, random_seed=42
        )
        structure = next(generator)
        
        # Apply the mean smoothing filter similar to the demo config
        smoothed = utils.binary_smoother(
            structure,
            lambda img: skimage.util.img_as_float(
                skimage.filters.rank.mean(
                    skimage.util.img_as_ubyte(img.astype(float)),
                    footprint=skimage.morphology.disk(3),
                )
            ),
        )
        smoothed = gen.make_orthogonal(smoothed)
        
        plt.figure(figsize=(6, 6))
        plt.imshow(smoothed.T, cmap="gray")
        plt.title(f"Spinodal structure (l={l_val}, vf={vf}, bandwidth={bandwidth})")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(f"spinodal_l{int(l_val)}.png", dpi=150)
        plt.close()
        print(f"Generated spinodal_l{int(l_val)}.png")
