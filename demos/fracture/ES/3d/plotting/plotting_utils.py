"""Shared input-file and output-directory helpers for the 3D plotters."""

from argparse import ArgumentParser, Namespace
from pathlib import Path


PLOTTING_DIR = Path(__file__).resolve().parent
SIMULATION_OUTPUT_DIR = PLOTTING_DIR.parent / "simulations" / "output"


def add_h5_file_argument(parser: ArgumentParser) -> None:
    """Add the common optional HDF5 input argument to a plotter parser."""
    parser.add_argument(
        "--h5-file",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "HDF5 result to plot. Defaults to the newest source .h5 file in "
            f"{SIMULATION_OUTPUT_DIR}."
        ),
    )


def parse_plot_args(description: str) -> Namespace:
    """Parse the arguments shared by all plotters."""
    parser = ArgumentParser(description=description)
    add_h5_file_argument(parser)
    return parser.parse_args()


def source_h5_files(directory: Path = SIMULATION_OUTPUT_DIR) -> list[Path]:
    """Return source result files, excluding generated interpolation files."""
    return sorted(
        (
            path
            for path in directory.glob("*.h5")
            if not path.name.startswith("interpolated_")
        ),
        key=lambda path: path.stat().st_mtime,
    )


def resolve_h5_file(h5_file: Path | str | None = None) -> Path:
    """Resolve an explicit result path or select the newest source result."""
    if h5_file is not None:
        path = Path(h5_file).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"HDF5 file does not exist: {path}")
        if path.suffix.lower() != ".h5":
            raise ValueError(f"Expected an .h5 file, not: {path}")
        return path

    files = source_h5_files()
    if not files:
        raise FileNotFoundError(
            f"No source .h5 files found in {SIMULATION_OUTPUT_DIR}"
        )
    return files[-1]


def get_plot_output_dir(h5_path: Path) -> Path:
    """Create and return the directory used for plots derived from one result."""
    output_dir = h5_path.with_suffix("")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir