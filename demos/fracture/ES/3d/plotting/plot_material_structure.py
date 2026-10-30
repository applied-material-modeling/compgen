#!/usr/bin/env python3
"""Plot native x-y, x-z, and y-z slices of the Al/SiC structure."""

from pathlib import Path

import h5py
import hdf5plugin  # Registers compression filters used by CompGen HDF5 output.
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch, Polygon
import numpy as np
from matplotlib.collections import PatchCollection
from scipy.spatial import ConvexHull

from plotting_utils import get_plot_output_dir, parse_plot_args, resolve_h5_file


NUMBER_OF_SLICES = 3


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
    if connectivity.shape[1] not in (4, 8):
        raise ValueError(
            f"This plotter supports quadrilateral or hexahedral elements, "
            f"not {connectivity.shape[1]}-node elements."
        )
    if material.shape[0] != connectivity.shape[0]:
        raise ValueError("Material data and connectivity have different sizes.")

    if coords.shape[1] < 3 and connectivity.shape[1] == 8:
        raise ValueError("Hexahedral meshes must contain three coordinate dimensions.")

    return coords, connectivity, material


def select_native_slices(coords, connectivity, normal_axis):
    """Select three native layers from a minimum-coordinate face to center."""
    element_centers = coords[connectivity].mean(axis=1)
    layers = np.unique(element_centers[:, normal_axis])
    requested_z = np.linspace(
        layers.min(), 0.5 * (layers.min() + layers.max()), NUMBER_OF_SLICES
    )

    slices = []
    for requested in requested_z:
        selected_layer = layers[np.argmin(np.abs(layers - requested))]
        element_indices = np.flatnonzero(
            np.isclose(
                element_centers[:, normal_axis], selected_layer, rtol=0.0, atol=1e-12
            )
        )
        if len(element_indices) == 0:
            raise ValueError(f"No elements found at axis {normal_axis}={selected_layer}.")
        slices.append({
            "element_indices": element_indices,
            "requested_z": requested,
            "coordinate": selected_layer,
        })
    return slices


def material_label_position(coords, connectivity, material, material_id):
    """Return a representative element-center position for a material."""
    centers = coords[connectivity].mean(axis=1)
    selected = centers[np.isclose(material, material_id)]
    if selected.size == 0:
        return None

    mean_position = selected.mean(axis=0)
    nearest = np.argmin(np.linalg.norm(selected - mean_position, axis=1))
    return selected[nearest]


def projected_polygon(coords):
    """Return a non-self-intersecting polygon for a projected cell."""
    points = np.unique(coords, axis=0)
    if len(points) <= 2:
        return points
    return points[ConvexHull(points).vertices]


def plot_structure(h5_path, output_path):
    coords, connectivity, material = load_material_mesh(h5_path)
    material_ids = np.rint(material).astype(int)

    # Each row is a plane orientation and each column is a native layer from
    # that plane's minimum-coordinate face toward its center. The tuple is
    # (displayed horizontal axis, displayed vertical axis, slice normal axis).
    plane_specs = (
        ((0, 1, 2), "x", "y", "z", "x-y"),
        ((0, 2, 1), "x", "z", "y", "x-z"),
        ((1, 2, 0), "y", "z", "x", "y-z"),
    )
    figure, axes = plt.subplots(3, 3, figsize=(14, 13), constrained_layout=True)
    axes = axes.ravel()
    legend = [
        Patch(facecolor="#F2B134", edgecolor="none", label="Aluminum (Al)"),
        Patch(facecolor="#4C78A8", edgecolor="none", label="Silicon carbide (SiC)"),
    ]

    for row, (display_axes, xlabel, ylabel, normal_label, plane_label) in enumerate(
        plane_specs
    ):
        slices = select_native_slices(coords, connectivity, display_axes[2])
        for column, plane in enumerate(slices):
            axis = axes[row * NUMBER_OF_SLICES + column]
            element_indices = plane["element_indices"]
            patches = [
                Polygon(
                    projected_polygon(element[:, list(display_axes[:2])]), closed=True
                )
                for element in coords[connectivity[element_indices]]
            ]
            collection = PatchCollection(
                patches,
                cmap=ListedColormap(["#4C78A8", "#F2B134"]),
                linewidth=0.0,
                edgecolor="none",
            )
            collection.set_array(material_ids[element_indices])
            collection.set_clim(-0.5, 1.5)
            axis.add_collection(collection)
            axis.set_xlim(
                coords[:, display_axes[0]].min(), coords[:, display_axes[0]].max()
            )
            axis.set_ylim(
                coords[:, display_axes[1]].min(), coords[:, display_axes[1]].max()
            )
            axis.set_aspect("equal")
            axis.set_xlabel(xlabel)
            axis.set_ylabel(ylabel)
            axis.set_title(
                f"{plane_label}: {normal_label} = {plane['coordinate']:.4g}"
            )

    figure.legend(handles=legend, loc="upper center", ncol=2, framealpha=0.95)
    figure.suptitle(
        "Material structure on native slices\n"
        "Columns: face, midway to center, center; rows: x-y, x-z, y-z",
        fontsize=16,
    )
    figure.savefig(output_path, dpi=250, bbox_inches="tight")
    plt.close(figure)
    print(f"Saved material plot to {output_path}")


def main():
    args = parse_plot_args(__doc__)
    h5_file = resolve_h5_file(args.h5_file)
    output_file = get_plot_output_dir(h5_file) / "material_structure.png"
    plot_structure(h5_file, output_file)


if __name__ == "__main__":
    main()
