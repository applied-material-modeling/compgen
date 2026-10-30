#!/usr/bin/env python3
"""Animate interface damage on four native x-y slices of a 3D result.

The 3D fracture setup applies displacement in the y direction: the bottom
boundary is fixed and the top boundary is pulled.  Consequently, y is shown
vertically in every panel.  The four panels are x-y slices at native element
locations running from the minimum-z face to the geometric z center:

    face, one-third of the way to the center, two-thirds of the way,
    and the center.

The interface damage field is element-centered.  The closest available
element-center z layer is selected for each requested location; no
interpolation or resampling is performed.
"""

import os
from pathlib import Path

import h5py
import hdf5plugin  # Registers compression filters used by CompGen output.
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.colors import Normalize
import numpy as np

from plotting_utils import get_plot_output_dir, parse_plot_args, resolve_h5_file


GRID_DPI = 140
FPS = 5
NUMBER_OF_SLICES = 4


def load_data(h5_path):
    """Load mesh data, native interface damage, and time values."""
    with h5py.File(h5_path, "r") as h5:
        coords = np.asarray(h5["unstructured_mesh/coords"])
        connectivity = np.asarray(h5["unstructured_mesh/connectivity"], dtype=np.int64)
        damage = np.asarray(
            h5["unstructured_mesh/element_fields/stimuli/d_interface/data"]
        )
        times = np.asarray(h5["time"])

    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError("Expected 3D coordinates with shape (nodes, 3).")
    if connectivity.ndim != 2 or connectivity.shape[1] != 8:
        raise ValueError("Expected hexahedral connectivity with shape (elements, 8).")
    if damage.ndim != 2:
        raise ValueError("Expected interface damage with shape (time, elements).")
    if damage.shape[1] != connectivity.shape[0]:
        raise ValueError("Interface damage and connectivity element counts do not match.")
    if damage.shape[0] != len(times):
        raise ValueError("Interface damage and time dimensions do not match.")

    element_centers = coords[connectivity].mean(axis=1)
    return element_centers, damage, times


def select_slices(element_centers, damage):
    """Select four closest native z layers from the face to the z center."""
    z_layers = np.unique(element_centers[:, 2])
    z_face = z_layers.min()
    z_center = 0.5 * (z_layers.min() + z_layers.max())
    requested_z = np.linspace(z_face, z_center, NUMBER_OF_SLICES)

    slices = []
    for requested in requested_z:
        selected_z = z_layers[np.argmin(np.abs(z_layers - requested))]
        layer = np.isclose(element_centers[:, 2], selected_z, rtol=0.0, atol=1e-12)
        points = element_centers[layer][:, :2]
        values = damage[:, layer]
        if len(points) == 0:
            raise ValueError(f"No elements found at z={selected_z}.")
        slices.append({
            "points": points,
            "values": values,
            "requested_z": requested,
            "z": selected_z,
        })

    return slices


def main():
    args = parse_plot_args(__doc__)
    h5_path = resolve_h5_file(args.h5_file)
    output_dir = get_plot_output_dir(Path(h5_path))
    output_path = os.path.join(output_dir, "interface_damage_slices.gif")

    element_centers, damage, times = load_data(h5_path)
    slices = select_slices(element_centers, damage)

    global_max = np.nanmax(damage)
    norm = Normalize(vmin=0.0, vmax=max(1.0, global_max))

    print(f"Input: {h5_path}")
    for index, plane in enumerate(slices, start=1):
        print(
            f"Slice {index}: requested z={plane['requested_z']:.9g}, "
            f"selected native z={plane['z']:.9g}, points={len(plane['points'])}"
        )
    print(f"Writing: {output_path}")

    fig, axes = plt.subplots(2, 2, figsize=(12, 10), constrained_layout=True)
    axes = axes.ravel()
    artists = []
    for index, (axis, plane) in enumerate(zip(axes, slices), start=1):
        points = plane["points"]
        artist = axis.scatter(
            points[:, 0],
            points[:, 1],
            c=plane["values"][0],
            cmap="magma",
            norm=norm,
            s=10,
            marker="s",
            linewidths=0,
        )
        axis.set_xlabel("x")
        axis.set_ylabel("y (loading direction)")
        axis.set_title(f"Interface damage, z = {plane['z']:.4g}")
        axis.set_aspect("equal")
        artists.append(artist)

    fig.colorbar(artists[0], ax=axes.tolist(), label="Interface damage")
    suptitle = fig.suptitle(
        f"Interface damage on native x-y slices, t = {times[0]:.6g}"
    )

    def update(frame):
        for artist, plane in zip(artists, slices):
            artist.set_array(plane["values"][frame])
        suptitle.set_text(
            f"Interface damage on native x-y slices, t = {times[frame]:.6g}"
        )
        return artists + [suptitle]

    animation = FuncAnimation(fig, update, frames=damage.shape[0], blit=False)
    animation.save(output_path, writer=PillowWriter(fps=FPS), dpi=GRID_DPI)
    plt.close(fig)
    print("Completed successfully.")


if __name__ == "__main__":
    main()