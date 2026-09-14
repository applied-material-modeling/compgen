#!/usr/bin/env python
"""Plot histograms of the sampled material properties across a random sweep.

Every ``fracture_random_*.h5`` written by the sweep records the material
properties that were drawn for that run under the ``material_properties`` group,
with one subgroup per phase (``A``, ``B``, ``AB``) and each scalar property
stored as an HDF5 *attribute* on that subgroup. This script gathers those
attributes across all files in a directory and shows one histogram per property
so you can eyeball that the sampling is actually random / correctly shaped
(uniform-in-linear for E, nu, density, eta; uniform-in-log for Gc, psic, and the
interface energies/strengths).

Usage:
    python plot_random_material_histograms.py [DIR] [--out FIG.png]
                                              [--bins N] [--show] [--glob PAT]

DIR defaults to the current directory. On a headless HPC login/compute node the
figure is written to a PNG (no display needed); pass --show only if you have an
X/display available.
"""

import argparse
import glob
import math
import os
import sys

import h5py
import numpy as np

# Non-interactive backend by default so this works over SSH / on compute nodes.
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Phases (HDF5 subgroups under material_properties), in display order.
PHASES = ["A", "B", "AB"]

# Properties known to be sampled log-uniformly (span many decades) -> plotted
# with log-spaced bins and a log x-axis so a correct sample looks flat.
# Anything not listed is auto-detected: positive-valued props spanning >= 100x
# are treated as log, everything else as linear.
KNOWN_LOG_PROPS = {
    "Gc",
    "psic",
    "GI_c",
    "GII_c",
    "normal_strength",
    "shear_strength",
}


def collect(files):
    """Return {phase: {prop: np.array(values)}} gathered across all files.

    Files missing the material_properties group (or a phase) are skipped with a
    warning rather than aborting the whole run.
    """
    data = {phase: {} for phase in PHASES}
    used = 0
    for path in files:
        try:
            with h5py.File(path, "r") as f:
                if "material_properties" not in f:
                    print(f"  skip (no material_properties): {os.path.basename(path)}")
                    continue
                mp = f["material_properties"]
                for phase in PHASES:
                    if phase not in mp:
                        continue
                    for key, value in mp[phase].attrs.items():
                        data[phase].setdefault(key, []).append(float(value))
                used += 1
        except (OSError, KeyError) as e:
            print(f"  skip (unreadable: {e}): {os.path.basename(path)}")
    # to arrays
    for phase in data:
        data[phase] = {k: np.asarray(v) for k, v in data[phase].items()}
    return data, used


def is_log(prop, values):
    """Decide whether to bin/plot a property on a log scale."""
    if prop in KNOWN_LOG_PROPS:
        return True
    v = values[np.isfinite(values)]
    if v.size == 0 or np.min(v) <= 0:
        return False
    return (np.max(v) / np.min(v)) >= 100.0


def make_bins(values, log, nbins):
    """Bin edges for a property; degenerate (constant) props get a single bin."""
    v = values[np.isfinite(values)]
    if v.size == 0:
        return nbins
    lo, hi = float(np.min(v)), float(np.max(v))
    if not np.isclose(lo, hi):
        if log and lo > 0:
            return np.logspace(math.log10(lo), math.log10(hi), nbins + 1)
        return np.linspace(lo, hi, nbins + 1)
    # constant value (e.g. a fixed `l`): one narrow bin centered on the value
    pad = abs(lo) * 0.05 or 0.5
    return np.linspace(lo - pad, hi + pad, 3)


def plot(data, used, out_path, nbins, show):
    # Build the list of (phase, prop) panels. Overlay bulk A & B on shared
    # panels; give the interface (AB) its own panels.
    bulk_props = sorted(set(data["A"]) | set(data["B"]))
    iface_props = sorted(set(data["AB"]))
    panels = [("bulk", p) for p in bulk_props] + [("AB", p) for p in iface_props]

    if not panels:
        print("No material properties found in any file - nothing to plot.")
        return

    ncols = 3
    nrows = math.ceil(len(panels) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 3.4 * nrows))
    axes = np.atleast_1d(axes).ravel()

    for ax, (kind, prop) in zip(axes, panels):
        if kind == "bulk":
            series = [
                ("A", data["A"].get(prop), "tab:blue"),
                ("B", data["B"].get(prop), "tab:orange"),
            ]
            combined = np.concatenate(
                [s for _, s, _ in series if s is not None and s.size]
            )
        else:
            series = [("AB", data["AB"].get(prop), "tab:green")]
            combined = data["AB"][prop]

        log = is_log(prop, combined)
        bins = make_bins(combined, log, nbins)

        for label, values, color in series:
            if values is None or values.size == 0:
                continue
            ax.hist(
                values,
                bins=bins,
                alpha=0.6,
                color=color,
                label=f"{label} (n={values.size})",
                edgecolor="white",
                linewidth=0.3,
            )
        if log:
            ax.set_xscale("log")
        ax.set_title(prop)
        ax.set_ylabel("count")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.2)

    # hide any unused axes
    for ax in axes[len(panels):]:
        ax.set_visible(False)

    fig.suptitle(
        f"Sampled material properties across {used} runs "
        f"(log-x = log-uniform sampling)",
        fontsize=13,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(out_path, dpi=130)
    print(f"\nWrote figure: {out_path}")
    if show:
        plt.show()


def print_summary(data, used):
    print(f"\nSummary over {used} run(s):")
    for phase in PHASES:
        if not data[phase]:
            continue
        print(f"  [{phase}]")
        for prop in sorted(data[phase]):
            v = data[phase][prop]
            log = is_log(prop, v)
            tag = " (log)" if log else ""
            print(
                f"    {prop:<16} n={v.size:<4} "
                f"min={np.min(v):.4g}  max={np.max(v):.4g}  "
                f"mean={np.mean(v):.4g}{tag}"
            )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory containing the .h5 files (default: current dir).",
    )
    ap.add_argument(
        "--glob",
        default="fracture_random_*.h5",
        help="Filename glob pattern (default: fracture_random_*.h5).",
    )
    ap.add_argument("--out", default=None, help="Output PNG path.")
    ap.add_argument("--bins", type=int, default=20, help="Histogram bins.")
    ap.add_argument("--show", action="store_true", help="Also display the figure.")
    args = ap.parse_args(argv)

    pattern = os.path.join(args.directory, args.glob)
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"No files matched: {pattern}", file=sys.stderr)
        return 1
    print(f"Found {len(files)} file(s) matching {pattern}")

    data, used = collect(files)
    if used == 0:
        print("No readable files with material_properties.", file=sys.stderr)
        return 1

    print_summary(data, used)

    out_path = args.out or os.path.join(args.directory, "random_material_histograms.png")
    plot(data, used, out_path, args.bins, args.show)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
