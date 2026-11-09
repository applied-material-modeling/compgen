#!/usr/bin/env python3
"""Print the arrays and dimensions stored in the first HDF5 result files."""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py


# Path to the folder containing the HDF5 result files to inspect.
INPUT_DIR = Path(
    "/home/bbrunsvik/projects/ai4ns/compgen/demos/fracture/ES/2d/simulations/output"
)

# Inspect only the first few files by default. Increase this value or use
# --limit when more files should be included.
FIRST_N_FILES = 2


def print_dataset(name: str, dataset: h5py.Dataset) -> None:
    """Print one dataset without reading any of its values."""
    shape = " x ".join(str(size) for size in dataset.shape) or "scalar"
    print(f"    {name:<60} shape: {shape:<24} dtype: {dataset.dtype}")


def inspect_file(h5_path: Path) -> None:
    """Print the dataset paths and shapes in one HDF5 file."""
    print(f"\nFile: {h5_path.name}")
    print(f"Path: {h5_path}")

    dataset_count = 0

    def visit_dataset(name: str, item: h5py.Dataset) -> None:
        nonlocal dataset_count
        if isinstance(item, h5py.Dataset):
            print_dataset(name, item)
            dataset_count += 1

    # Opening in read-only mode and accessing .shape/.dtype reads metadata,
    # not the full array contents.
    with h5py.File(h5_path, "r") as h5_file:
        h5_file.visititems(visit_dataset)

    print(f"  Total arrays: {dataset_count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print HDF5 dataset names and dimensions without reading arrays."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=FIRST_N_FILES,
        help=f"number of sorted .h5 files to inspect (default: {FIRST_N_FILES})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")

    h5_files = sorted(INPUT_DIR.glob("*.h5"))[: args.limit]
    if not h5_files:
        print(f"No .h5 files found in {INPUT_DIR}")
        return

    print(f"Input directory: {INPUT_DIR}")
    print(f"Inspecting {len(h5_files)} of the first .h5 files (sorted by name).")
    for h5_path in h5_files:
        inspect_file(h5_path)


if __name__ == "__main__":
    main()