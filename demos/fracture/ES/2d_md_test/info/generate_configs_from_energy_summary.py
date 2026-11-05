#!/usr/bin/env python3
"""Generate the MD fracture configuration files from energy_summary.csv.

The CSV reports interface quantities in physical units, while the CompGen
configuration uses the MPa-mm-N convention documented in
``units_compgen_raccoon.md``:

* peak stress in GPa -> strength in MPa: multiply by 1000
* work in J/m^2 -> fracture energy in N/mm: divide by 1000

Mode I supplies ``GI_c`` and ``normal_strength``.  Mode II supplies ``GII_c``
and ``shear_strength``.  The other CSV columns are retained as source data but
are not parameters accepted by the current ``material_AB`` generator.
"""

from __future__ import annotations

import argparse
import csv
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path


INFO_DIR = Path(__file__).resolve().parent
DEMO_DIR = INFO_DIR.parent
CSV_PATH = INFO_DIR / "energy_summary.csv"
BASELINE_PATH = DEMO_DIR / "config_case0.json"

EXPECTED_CASES = set(range(1, 11))
MODE_I = "I"
MODE_II = "II"


def read_energy_summary(path: Path) -> dict[int, dict[str, dict[str, str]]]:
    """Read and validate the two mode rows required for each case."""
    with path.open(newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    required_columns = {
        "mode",
        "case",
        "peak_stress_GPa",
        "work_J_m2",
    }
    missing_columns = required_columns - set(rows[0]) if rows else required_columns
    if missing_columns:
        raise ValueError(f"CSV is missing required columns: {sorted(missing_columns)}")

    cases: dict[int, dict[str, dict[str, str]]] = {}
    for row in rows:
        try:
            case = int(row["case"])
        except ValueError as error:
            raise ValueError(f"Invalid case number: {row['case']!r}") from error

        mode = row["mode"].strip().upper()
        if case not in EXPECTED_CASES:
            raise ValueError(f"Unexpected case {case}; expected cases 1 through 10")
        if mode not in {MODE_I, MODE_II}:
            raise ValueError(f"Unexpected mode {row['mode']!r} in case {case}")
        if mode in cases.setdefault(case, {}):
            raise ValueError(f"Duplicate mode {mode} for case {case}")
        cases[case][mode] = row

    if set(cases) != EXPECTED_CASES:
        raise ValueError(
            f"CSV cases are {sorted(cases)}; expected cases 1 through 10"
        )
    for case, modes in cases.items():
        if set(modes) != {MODE_I, MODE_II}:
            raise ValueError(
                f"Case {case} must contain exactly one mode I and one mode II row"
            )
    return cases


def energy_to_config_value(row: dict[str, str], column: str, scale: float) -> float:
    """Convert one CSV value and return it as a JSON number."""
    try:
        # Convert the decimal text before applying the unit conversion.  This
        # avoids introducing a one-ulp discrepancy for values such as case 1's
        # work values compared with the manually prepared configuration.
        return float(Decimal(row[column]) * Decimal(str(scale)))
    except (KeyError, ValueError, ArithmeticError) as error:
        raise ValueError(f"Invalid {column!r} value in CSV row: {row}") from error


def make_config(template: dict, case: int, modes: dict[str, dict[str, str]]) -> dict:
    """Create one case configuration from the case 0 baseline."""
    config = deepcopy(template)
    interface = config["material_AB"]["params"]

    mode_i = modes[MODE_I]
    mode_ii = modes[MODE_II]
    interface.update(
        {
            "GI_c": energy_to_config_value(mode_i, "work_J_m2", 1 / 1000),
            "GII_c": energy_to_config_value(mode_ii, "work_J_m2", 1 / 1000),
            "normal_strength": energy_to_config_value(
                mode_i, "peak_stress_GPa", 1000
            ),
            "shear_strength": energy_to_config_value(
                mode_ii, "peak_stress_GPa", 1000
            ),
        }
    )

    simulation_dir = DEMO_DIR / "simulations" / f"case{case}"
    config["output"].update(
        {
            "output_prefix": f"alan_case{case}",
            "output_dir": str(simulation_dir / "output"),
        }
    )
    config["storage"]["temp_dir"] = str(simulation_dir / "tmp")
    config["log_file"] = str(simulation_dir / "logs" / "compgen.log")
    return config


def generate_configs(csv_path: Path = CSV_PATH, baseline_path: Path = BASELINE_PATH) -> None:
    """Generate config_case1.json through config_case10.json."""
    with baseline_path.open() as baseline_file:
        template = json.load(baseline_file)

    for case, modes in sorted(read_energy_summary(csv_path).items()):
        output_path = DEMO_DIR / f"config_case{case}.json"
        config = make_config(template, case, modes)
        with output_path.open("w") as output_file:
            json.dump(config, output_file, indent=4)
            output_file.write("\n")
        print(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=CSV_PATH)
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    args = parser.parse_args()
    generate_configs(args.csv, args.baseline)


if __name__ == "__main__":
    main()