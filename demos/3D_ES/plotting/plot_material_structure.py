#!/usr/bin/env python3
"""Plot the Al/SiC material structure from a CompGen HDF5 result."""

import argparse
from pathlib import Path

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch, Polygon
import numpy as np
from matplotlib.collections import PatchCollection


SCRIPT_DIR = Path(__file__).resolve().parent


def newest_h5_file(directory):
    files = sorted(directory.glob("*.h5"), key=lambda path: path.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No .h5 files found in {directory}")
    return files[-1]


def load_material_mesh(h5_path):
    with h5py.File(h5_path, "r") as h5:
        mesh = h5["unstructured_mesh"]
        coords = np.asarray(mesh["coords"])
        connectivity = np.asarray(mesh["connectivity"], dtype=np.int64)
        material = np.asarray(mesh["element_fields"]["material"]["data"])[0]

    if coords.shape[1] < 2:
        raise ValueError("The mesh must have at least two coordinate dimensions.")
    if connectivity.ndim != 2:
        raise ValueError("Expected a two-dimensional element connectivity array.")
    if connectivity.shape[1] not in (3, 4):
        raise ValueError(
            f"This plotter supports triangular or quadrilateral elements, "
            f"not {connectivity.shape[1]}-node elements."
        )
    if material.shape[0] != connectivity.shape[0]:
        raise ValueError("Material data and connectivity have different sizes.")

    return coords[:, :2], connectivity, material


def material_label_position(coords, connectivity, material, material_id):
    """Return a representative element-center position for a material."""
    centers = coords[connectivity].mean(axis=1)
    selected = centers[np.isclose(material, material_id)]
    if selected.size == 0:
        return None

    mean_position = selected.mean(axis=0)
    nearest = np.argmin(np.linalg.norm(selected - mean_position, axis=1))
    return selected[nearest]


def plot_structure(h5_path, output_path):
    coords, connectivity, material = load_material_mesh(h5_path)
    material_ids = np.rint(material).astype(int)

    patches = [Polygon(coords[element], closed=True) for element in connectivity]
    collection = PatchCollection(
        patches,
        cmap=ListedColormap(["#4C78A8", "#F2B134"]),
        linewidth=0.0,
        edgecolor="none",
    )
    collection.set_array(material_ids)
    collection.set_clim(-0.5, 1.5)

    figure, axis = plt.subplots(figsize=(9, 8), constrained_layout=True)
    axis.add_collection(collection)
    axis.set_xlim(coords[:, 0].min(), coords[:, 0].max())
    axis.set_ylim(coords[:, 1].min(), coords[:, 1].max())
    axis.set_aspect("equal")
    axis.set_xlabel("x")
    axis.set_ylabel("y")
    axis.set_title(f"Material structure\n{h5_path.name}")

    legend = [
        Patch(facecolor="#F2B134", edgecolor="none", label="Aluminum (Al)"),
        Patch(facecolor="#4C78A8", edgecolor="none", label="Silicon carbide (SiC)"),
    ]
    axis.legend(handles=legend, loc="upper right", framealpha=0.95)

    label_specs = (
        (1, "Al", "#7A4B00", (28, -28)),
        (0, "SiC", "#123B63", (-28, 28)),
    )
    for material_id, label, color, offset in label_specs:
        position = material_label_position(
            coords, connectivity, material_ids, material_id
        )
        if position is not None:
            axis.annotate(
                label,
                xy=position,
                xytext=offset,
                textcoords="offset points",
                color=color,
                fontsize=13,
                fontweight="bold",
                ha="center",
                va="center",
                bbox={
                    "boxstyle": "round,pad=0.25",
                    "facecolor": "white",
                    "edgecolor": color,
                    "alpha": 0.9,
                },
                arrowprops={
                    "arrowstyle": "->",
                    "color": color,
                    "linewidth": 1.2,
                },
            )

    axis.margins(x=0.02, y=0.02)
    figure.savefig(output_path, dpi=250, bbox_inches="tight")
    plt.close(figure)
    print(f"Saved material plot to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Plot Aluminum and SiC material blocks from a CompGen HDF5 result."
    )
    parser.add_argument(
        "h5_file",
        nargs="?",
        help="HDF5 result file. Defaults to the newest .h5 file in this directory.",
    )
    parser.add_argument(
        "--output",
        help="PNG output path. Defaults next to the HDF5 file.",
    )
    args = parser.parse_args()

    h5_path = Path(args.h5_file).resolve() if args.h5_file else newest_h5_file(SCRIPT_DIR)
    output_path = (
        Path(args.output).resolve()
        if args.output
        else h5_path.with_name(f"{h5_path.stem}_material_structure.png")
    )
    plot_structure(h5_path, output_path)


if __name__ == "__main__":
    main()
