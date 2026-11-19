#!/usr/bin/env python3
"""Generate a contact sheet of ellipse structures without running a simulation."""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


SCRIPT_DIR = Path(__file__).resolve().parent
DEMO_DIR = SCRIPT_DIR.parent
REPO_DIR = DEMO_DIR.parents[3]
CONFIG_FILE = DEMO_DIR / "config_case1.json"
OUTPUT_DIR = DEMO_DIR / "visualizations"
OUTPUT_FILE = OUTPUT_DIR / "ellipse_preview.png"
NUMBER_OF_STRUCTURES = 10

sys.path.insert(0, str(REPO_DIR))

from compgen.gen import EllipseGenerator


def main():
    with CONFIG_FILE.open() as config_file:
        config = json.load(config_file)

    generator_config = config["generator"]
    if generator_config["type"] != "gen.EllipseGenerator":
        raise ValueError(
            f"Expected gen.EllipseGenerator, got {generator_config['type']}"
        )

    generator = EllipseGenerator(**generator_config["params"])
    prefracture = config.get("prefracture")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(2, 5, figsize=(12, 5), constrained_layout=True)
    for index, axis in enumerate(axes.flat, start=1):
        structure = generator.sample()
        axis.imshow(structure.T, cmap="gray", origin="lower", interpolation="nearest")
        protected = generator.prefracture_mask()
        axis.contour(
            protected.T,
            levels=[0.5],
            colors=["crimson"],
            linewidths=1.5,
            origin="lower",
        )
        if prefracture is not None:
            x1 = 0.0
            x2 = prefracture["length_fraction"] * generator.nx
            y = prefracture["y_fraction"] * generator.ny
            axis.plot(
                [x1, x2],
                [y, y],
                color="black",
                linewidth=3.0,
                solid_capstyle="butt",
            )
        axis.set_title(f"Structure {index}")
        axis.axis("off")

    figure.suptitle("Ellipse structures with left-entering initial cohesive fracture")
    figure.legend(
        handles=[
            Line2D([0], [0], color="black", linewidth=3, label="Initial fracture"),
            Line2D([0], [0], color="crimson", linewidth=1.5, label="Ellipse exclusion corridor"),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
    )
    figure.savefig(OUTPUT_FILE, dpi=200)
    plt.close(figure)
    print(f"Saved ellipse preview to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()