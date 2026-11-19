#!/usr/bin/env python3
"""Run the real compgen mesh path and plot the resulting finite-element mesh.

This is deliberately separate from the simulation launcher.  It exercises the
configured generator, filters, and ``mesh.generate_mesh_2d`` function, then
keeps the Exodus mesh and plots its actual element blocks.  No RACOON run is
started.
"""

import json
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
import numpy as np
import exodusii


SCRIPT_DIR = Path(__file__).resolve().parent
DEMO_DIR = SCRIPT_DIR.parent
REPO_DIR = DEMO_DIR.parents[3]
CONFIG_FILE = DEMO_DIR / "config_case1.json"
OUTPUT_DIR = DEMO_DIR / "visualizations"
MESH_FILE = OUTPUT_DIR / "mesh_case1.exo"
FIGURE_FILE = OUTPUT_DIR / "mesh_preview.png"

sys.path.insert(0, str(REPO_DIR))

from compgen import filters, mesh
from compgen.gen import EllipseGenerator


def load_config():
    with CONFIG_FILE.open() as config_file:
        return json.load(config_file)


def generate_filtered_structure(config):
    generator_config = config["generator"]
    generator = EllipseGenerator(**generator_config["params"])
    structure = generator.sample()
    for filter_config in config.get("filtering", []):
        if filter_config["type"] != "filters.mean_filter":
            raise ValueError(
                f"This diagnostic only supports filters.mean_filter, got {filter_config['type']}"
            )
        structure = filters.mean_filter(structure, **filter_config.get("params", {}))
    return generator, structure


def read_mesh(path):
    # exodusii versions used by the supported environments expect a string
    # path; accepting Path objects here would fail before reading the mesh.
    with exodusii.File(str(path), mode="r") as exo:
        coords = np.asarray(exo.get_coords())[:, :2]
        connectivity = [
            np.asarray(exo.get_element_conn(block), dtype=np.int64) - 1
            for block in (1, 2)
        ]
    return coords, connectivity


def add_mesh(axis, coords, connectivity):
    colors = ("#F2B134", "#4C78A8")
    labels = ("Aluminum (mat_a)", "Silicon carbide (mat_b)")
    for block, (conn, color, label) in enumerate(
        zip(connectivity, colors, labels)
    ):
        patches = [Polygon(coords[element], closed=True) for element in conn]
        collection = PatchCollection(
            patches,
            facecolor=color,
            edgecolor="none",
            linewidth=0.0,
            label=label,
            rasterized=True,
        )
        axis.add_collection(collection)
    axis.set_xlim(coords[:, 0].min(), coords[:, 0].max())
    axis.set_ylim(coords[:, 1].min(), coords[:, 1].max())
    axis.set_aspect("equal")


def add_crack(axis, config, x_scale, y_scale):
    prefracture = config["prefracture"]
    y = prefracture["y_fraction"] * y_scale
    axis.plot(
        [0.0, prefracture["length_fraction"] * x_scale],
        [y, y],
        color="black",
        linewidth=3.0,
        solid_capstyle="butt",
        label="Initial cohesive fracture",
        zorder=5,
    )


def main():
    config = load_config()
    generator, structure = generate_filtered_structure(config)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Use the same mesh function and settings shape as runner.run_single.
    mesh_settings = {
        **config,
        "storage": {"temp_dir": str(OUTPUT_DIR / "mesh_tmp"), "delete_temp_dir": True},
    }
    temporary_mesh = OUTPUT_DIR / "mesh_case1_working.exo"
    mesh.generate_mesh_2d(
        structure,
        str(temporary_mesh),
        L=config["L"],
        settings=mesh_settings,
        **config["mesh"].get("params", {}),
    )
    shutil.copy2(temporary_mesh, MESH_FILE)
    temporary_mesh.unlink()

    coords, connectivity = read_mesh(MESH_FILE)
    figure, axes = plt.subplots(1, 2, figsize=(15, 7), constrained_layout=True)

    axes[0].imshow(
        structure.T,
        cmap="gray",
        origin="lower",
        interpolation="nearest",
        extent=(0, config["L"][0], 0, config["L"][1]),
    )
    add_crack(axes[0], config, *config["L"])
    axes[0].set_title("After generator and filtering\n(bitmap supplied to mesher)")
    axes[0].set_xlabel("x")
    axes[0].set_ylabel("y")
    axes[0].set_aspect("equal")

    add_mesh(axes[1], coords, connectivity)
    add_crack(axes[1], config, *config["L"])
    axes[1].set_title(
        f"Actual Exodus finite-element mesh\n"
        f"{sum(len(block) for block in connectivity):,} elements"
    )
    axes[1].set_xlabel("x")
    axes[1].set_ylabel("y")
    axes[1].legend(loc="upper right", framealpha=0.95)

    figure.suptitle("Compgen post-meshing verification: case1")
    figure.savefig(FIGURE_FILE, dpi=220, bbox_inches="tight")
    plt.close(figure)
    print(f"Saved Exodus mesh to {MESH_FILE}")
    print(f"Saved mesh preview to {FIGURE_FILE}")


if __name__ == "__main__":
    main()