#!/usr/bin/env python3
import argparse
import os
import tempfile
from pathlib import Path

import h5py
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(SCRIPT_DIR / ".mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(SCRIPT_DIR / ".cache"))
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pyvista as pv


def newest_h5_file(directory):
    files = sorted(directory.glob("*.h5"), key=lambda path: path.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No .h5 files found in {directory}")
    return files[-1]


def load_tensor(group):
    return np.asarray(group["data"])


def build_grid(coords, connectivity):
    if coords.shape[1] == 2:
        points = np.column_stack([coords, np.zeros(coords.shape[0])])
    else:
        points = coords

    ncell = connectivity.shape[0]
    cell_sizes = np.full((ncell, 1), connectivity.shape[1], dtype=np.int64)
    cells = np.hstack([cell_sizes, connectivity.astype(np.int64)]).ravel()

    if connectivity.shape[1] == 4:
        cell_type = pv.CellType.QUAD
    elif connectivity.shape[1] == 8:
        cell_type = pv.CellType.HEXAHEDRON
    else:
        raise ValueError(f"Unsupported cell size {connectivity.shape[1]}")

    celltypes = np.full(ncell, cell_type, dtype=np.uint8)
    return pv.UnstructuredGrid(cells, celltypes, points)


def reshape_cell_data(coords, connectivity, values):
    centroids = coords[connectivity].mean(axis=1)
    x_vals = np.unique(centroids[:, 0])
    y_vals = np.unique(centroids[:, 1])
    if x_vals.size * y_vals.size != centroids.shape[0]:
        raise ValueError("Cell centroids are not on a regular grid.")

    grid = np.full((x_vals.size, y_vals.size), np.nan, dtype=float)
    ix = np.searchsorted(x_vals, centroids[:, 0])
    iy = np.searchsorted(y_vals, centroids[:, 1])
    grid[ix, iy] = values
    return x_vals, y_vals, grid


def plot_cell_field(ax, x_vals, y_vals, grid, title, cmap):
    image = ax.imshow(
        grid.T,
        origin="lower",
        extent=(x_vals[0], x_vals[-1], y_vals[0], y_vals[-1]),
        aspect="equal",
        cmap=cmap,
    )
    ax.set_title(title)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    plt.colorbar(image, ax=ax, shrink=0.85)


def render_damage_image(coords, connectivity, damage, title, window_size):
    grid = build_grid(coords, connectivity)
    grid.point_data[title] = damage

    plotter = pv.Plotter(off_screen=True, window_size=window_size)
    plotter.set_background("white")
    plotter.add_text(title, font_size=12)
    plotter.add_mesh(
        grid,
        scalars=title,
        preference="point",
        cmap="inferno",
        show_edges=False,
        lighting=False,
        scalar_bar_args={"title": title},
    )
    plotter.view_xy()
    plotter.camera.parallel_projection = True

    with tempfile.NamedTemporaryFile(
        suffix=".png", dir=SCRIPT_DIR, delete=False
    ) as handle:
        temp_path = Path(handle.name)

    try:
        plotter.screenshot(str(temp_path))
        image = plt.imread(temp_path)
    finally:
        plotter.close()
        if temp_path.exists():
            temp_path.unlink()

    return image


def main():
    parser = argparse.ArgumentParser(
        description="Plot a quick summary of a compgen fracture HDF5 result."
    )
    parser.add_argument(
        "h5_file",
        nargs="?",
        help="Path to the .h5 result file. Defaults to the newest file in this directory.",
    )
    parser.add_argument(
        "--time-index",
        type=int,
        default=-1,
        help="Time index to plot. Defaults to the last time step.",
    )
    parser.add_argument(
        "--output",
        help="Optional PNG output path. Defaults next to the .h5 file.",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        nargs=2,
        metavar=("WIDTH", "HEIGHT"),
        default=(1800, 1200),
        help="Window size for the PyVista damage render.",
    )
    args = parser.parse_args()

    h5_path = Path(args.h5_file).resolve() if args.h5_file else newest_h5_file(SCRIPT_DIR)
    png_path = (
        Path(args.output).resolve()
        if args.output
        else h5_path.with_name(f"{h5_path.stem}_summary.png")
    )

    with h5py.File(h5_path, "r") as h5:
        mesh = h5["unstructured_mesh"]
        coords = np.asarray(mesh["coords"])
        connectivity = np.asarray(mesh["connectivity"], dtype=np.int64)

        material = load_tensor(mesh["element_fields"]["material"])[0].astype(float)
        psie_active = load_tensor(mesh["element_fields"]["stimuli"]["psie_active"])[
            args.time_index
        ]
        cauchy_stress = load_tensor(
            mesh["element_fields"]["responses"]["cauchy_stress"]
        )[args.time_index]
        damage = load_tensor(mesh["node_fields"]["stimuli"]["d"])[args.time_index]

    stress_xx = cauchy_stress[:, 0]
    stress_xy = cauchy_stress[:, 2]
    stress_yy = cauchy_stress[:, 1]

    x_cell, y_cell, material_grid = reshape_cell_data(coords, connectivity, material)
    _, _, psie_grid = reshape_cell_data(coords, connectivity, psie_active)
    _, _, stress_yy_grid = reshape_cell_data(coords, connectivity, stress_yy)
    damage_image = render_damage_image(
        coords, connectivity, damage, "Damage d", args.window_size
    )

    figure, axes = plt.subplots(2, 2, figsize=(12, 10), constrained_layout=True)
    figure.suptitle(
        f"{h5_path.name}\n"
        f"time index {args.time_index} | "
        f"stress_xx range [{stress_xx.min():.3e}, {stress_xx.max():.3e}] | "
        f"stress_xy range [{stress_xy.min():.3e}, {stress_xy.max():.3e}]",
        fontsize=11,
    )

    plot_cell_field(axes[0, 0], x_cell, y_cell, material_grid, "Material", "gray")
    axes[0, 1].imshow(damage_image)
    axes[0, 1].set_title("Damage d")
    axes[0, 1].axis("off")
    plot_cell_field(axes[1, 0], x_cell, y_cell, psie_grid, "psie_active", "viridis")
    plot_cell_field(
        axes[1, 1], x_cell, y_cell, stress_yy_grid, "Cauchy Stress yy", "coolwarm"
    )

    figure.savefig(png_path, dpi=200)
    plt.close(figure)
    print(f"Saved summary plot to {png_path}")


if __name__ == "__main__":
    main()
