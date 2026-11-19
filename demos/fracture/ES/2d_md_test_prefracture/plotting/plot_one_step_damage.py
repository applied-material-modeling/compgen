#!/usr/bin/env python3
"""Plot the actual phase-field damage from a short RACOON diagnostic run."""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
import numpy as np
import pyvista as pv


SCRIPT_DIR = Path(__file__).resolve().parent
DEMO_DIR = SCRIPT_DIR.parent
DEFAULT_OUTPUT = DEMO_DIR / "visualizations" / "one_step_damage.png"


def find_default_exodus():
    candidates = sorted(
        (DEMO_DIR / "visualizations" / "one_step").glob(
            "tmp/*/output_0_fracture0.e"
        )
    )
    if not candidates:
        raise FileNotFoundError(
            "No one-step RACOON Exodus file found. Pass one with --exodus."
        )
    return candidates[-1]


def iter_grids(obj):
    if isinstance(obj, pv.MultiBlock):
        for index in range(obj.n_blocks):
            child = obj[index]
            if child is not None:
                yield from iter_grids(child)
    elif isinstance(obj, pv.DataSet):
        yield obj


def read_damage(path, time_index):
    reader = pv.get_reader(str(path))
    if time_index >= reader.number_time_points:
        raise ValueError(
            f"Requested time index {time_index}, but the file has "
            f"{reader.number_time_points} time point(s)."
        )
    reader.set_active_time_point(time_index)
    root = reader.read()
    grids = [
        grid
        for grid in iter_grids(root)
        if "d" in grid.point_data
        and (grid.bounds[1] - grid.bounds[0]) > 1e-12
        and (grid.bounds[3] - grid.bounds[2]) > 1e-12
    ]
    if not grids:
        raise ValueError(f"No point-centered damage field 'd' found in {path}")
    return grids, reader.time_values[time_index]


def plot_damage(grids, time, output_path):
    figure, axis = plt.subplots(figsize=(12, 5), constrained_layout=True)
    damage_cmap = LinearSegmentedColormap.from_list(
        "damage_white_red",
        [(0.0, "#ffffff"), (0.005, "#fff7bc"), (0.25, "#fec44f"), (1.0, "#b30000")],
    )
    norm = Normalize(0.0, 1.0)
    damage_values = []
    damage_points = []
    damage_point_values = []
    for grid in grids:
        damage = np.asarray(grid.point_data["d"], dtype=float)
        damage_values.append(damage)
        points = np.asarray(grid.points)[:, :2]
        nonzero_mask = damage > 1e-12
        damage_points.append(points[nonzero_mask])
        damage_point_values.append(damage[nonzero_mask])

    all_damage_points = np.concatenate(damage_points)
    all_damage_values = np.concatenate(damage_point_values)
    axis.scatter(
        all_damage_points[:, 0], all_damage_points[:, 1], color="#d62728", s=18,
        edgecolors="#550000", linewidths=0.3, zorder=3,
        label="Nonzero damage nodes from Exodus",
    )

    axis.set_xlim(all_damage_points[:, 0].min() - 0.02, all_damage_points[:, 0].max() + 0.02)
    axis.set_ylim(all_damage_points[:, 1].min() - 0.02, all_damage_points[:, 1].max() + 0.02)
    axis.set_aspect("equal")
    axis.set_xlabel("x")
    axis.set_ylabel("y")
    axis.set_facecolor("#f2f2f2")
    axis.grid(True, color="white", linewidth=1.0)
    axis.legend(loc="upper right", framealpha=0.95)

    max_damage = max(values.max() for values in damage_values)
    nonzero_count = sum(np.count_nonzero(values > 1e-12) for values in damage_values)
    axis.text(
        0.02,
        0.04,
        f"nonzero damage nodes: {nonzero_count:,}\nmax(d): {max_damage:g}",
        transform=axis.transAxes,
        ha="left",
        va="bottom",
        bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "0.7"},
    )
    axis.set_title(
        "Actual RACOON initial phase-field damage support\n"
        f"t = {time:g}; points shown only where d > 0"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(figure)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exodus", type=Path, default=None, help="RACOON Exodus file to plot."
    )
    parser.add_argument("--time-index", type=int, default=0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    exodus = args.exodus or find_default_exodus()
    grids, time = read_damage(exodus, args.time_index)
    plot_damage(grids, time, args.output)
    print(f"Saved damage figure to {args.output}")


if __name__ == "__main__":
    main()