#!/usr/bin/env python3
"""Plot center-plane slices of 3D element-centered stress_xx.

The result contains element-centered Cauchy stress, so the node closest to the
geometric center is used to define the three slice coordinates. For each plane,
the nearest layer of element centers is plotted.
"""

import os
from pathlib import Path

import h5py
import hdf5plugin  # Registers compression filters used by CompGen output.
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.animation import FuncAnimation, PillowWriter
import numpy as np

from plotting_utils import get_plot_output_dir, parse_plot_args, resolve_h5_file

GRID_DPI = 140
FPS = 5


def load_data(h5_path):
    with h5py.File(h5_path, "r") as h5:
        coords = np.asarray(h5["unstructured_mesh/coords"])
        connectivity = np.asarray(h5["unstructured_mesh/connectivity"], dtype=np.int64)
        stress = np.asarray(
            h5["unstructured_mesh/element_fields/responses/cauchy_stress/data"]
        )
        times = np.asarray(h5["time"])

    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError("Expected 3D coordinates with shape (nodes, 3).")
    if connectivity.ndim != 2 or connectivity.shape[1] != 8:
        raise ValueError("Expected hexahedral connectivity with shape (elements, 8).")
    if stress.ndim != 3 or stress.shape[2] != 6:
        raise ValueError("Expected 3D Cauchy stress with six components.")
    if stress.shape[1] != connectivity.shape[0]:
        raise ValueError("Stress and connectivity element counts do not match.")

    return coords, connectivity, stress[:, :, 0], times


def select_center_slices(coords, connectivity, stress_xx):
    center = 0.5 * (coords.min(axis=0) + coords.max(axis=0))
    center_node_index = np.argmin(np.linalg.norm(coords - center, axis=1))
    center_node = coords[center_node_index]

    element_centers = coords[connectivity].mean(axis=1)
    # Each entry is (horizontal coordinate indices, perpendicular coordinate index,
    # title, axis labels). The selected layer is the closest element-center layer.
    plane_specs = (
        ((0, 1), 2, "x-y", "x", "y"),
        ((0, 2), 1, "x-z", "x", "z"),
        ((1, 2), 0, "y-z", "y", "z"),
    )
    slices = []
    for axes, perpendicular, title, xlabel, ylabel in plane_specs:
        distance = np.abs(element_centers[:, perpendicular] - center_node[perpendicular])
        layer = np.isclose(distance, distance.min(), rtol=0.0, atol=1e-12)
        points = element_centers[layer][:, axes]
        values = stress_xx[:, layer]
        slices.append({
            "points": points,
            "values": values,
            "title": title,
            "xlabel": xlabel,
            "ylabel": ylabel,
            "coordinate": element_centers[layer, perpendicular][0],
        })

    return center_node_index, center_node, slices


def main():
    args = parse_plot_args(__doc__)
    h5_path = resolve_h5_file(args.h5_file)
    output_dir = get_plot_output_dir(Path(h5_path))
    output_path = os.path.join(output_dir, "stress_xx_center_slices.gif")

    coords, connectivity, stress_xx, times = load_data(h5_path)
    center_node_index, center_node, slices = select_center_slices(
        coords, connectivity, stress_xx
    )
    global_min = np.nanmin(stress_xx)
    global_max = np.nanmax(stress_xx)
    limit = max(abs(global_min), abs(global_max))
    if limit == 0:
        limit = 1.0
    norm = Normalize(vmin=-limit, vmax=limit)

    print(f"Input: {h5_path}")
    print(f"Center node: {center_node_index} at {center_node}")
    for plane in slices:
        print(f"{plane['title']} layer coordinate: {plane['coordinate']}")
    print(f"Writing: {output_path}")

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
    artists = []
    for axis, plane in zip(axes, slices):
        points = plane["points"]
        artist = axis.scatter(
            points[:, 0], points[:, 1], c=plane["values"][0],
            cmap="RdBu_r", norm=norm, s=5, marker="s", linewidths=0,
        )
        axis.set_xlabel(plane["xlabel"])
        axis.set_ylabel(plane["ylabel"])
        axis.set_title(f"$\\sigma_{{xx}}$ on {plane['title']} plane")
        axis.set_aspect("equal")
        fig.colorbar(artist, ax=axis, label="$\\sigma_{xx}$")
        artists.append(artist)
    suptitle = fig.suptitle(f"Cauchy stress $\\sigma_{{xx}}$, t = {times[0]:.6g}")

    def update(frame):
        for artist, plane in zip(artists, slices):
            artist.set_array(plane["values"][frame])
        suptitle.set_text(f"Cauchy stress $\\sigma_{{xx}}$, t = {times[frame]:.6g}")
        return artists + [suptitle]

    animation = FuncAnimation(fig, update, frames=stress_xx.shape[0], blit=False)
    animation.save(output_path, writer=PillowWriter(fps=FPS), dpi=GRID_DPI)
    plt.close(fig)
    print("Completed successfully.")


if __name__ == "__main__":
    main()