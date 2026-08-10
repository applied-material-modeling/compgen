"""Print the complete key structure of an HDF5 file."""

import argparse
from pathlib import Path

import h5py


def format_attribute(value):
    """Return a compact representation of an HDF5 attribute value."""
    text = repr(value)
    return text if len(text) <= 120 else f"{text[:117]}..."


def print_attributes(obj, indent="    "):
    """Print all attributes attached to a group or dataset."""
    for key, value in obj.attrs.items():
        print(f"{indent}@{key} = {format_attribute(value)}")


def print_hdf5_keys(filename):
    """Print every group, dataset, and attribute in an HDF5 file."""
    path = Path(filename).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"HDF5 file not found: {path}")

    print(f"File: {path}")
    with h5py.File(path, "r") as hdf:
        print("[GROUP] /")
        print_attributes(hdf)

        def print_item(name, obj):
            depth = name.count("/")
            indent = "    " * depth
            if isinstance(obj, h5py.Group):
                print(f"{indent}[GROUP] {name}/")
            else:
                print(
                    f"{indent}[DATASET] {name} " f"shape={obj.shape} dtype={obj.dtype}"
                )
            print_attributes(obj, indent=f"{indent}    ")

        hdf.visititems(print_item)


def main():
    parser = argparse.ArgumentParser(
        description="Print every group, dataset, and attribute in an HDF5 file."
    )
    parser.add_argument("h5_file", help="Path to the HDF5 file to inspect")
    args = parser.parse_args()
    print_hdf5_keys(args.h5_file)


if __name__ == "__main__":
    main()
