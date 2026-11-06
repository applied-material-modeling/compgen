"""Run the Aurora predefined fracture sweep on a local machine."""

import sys
import os
from pathlib import Path


DEMO_DIR = Path(__file__).resolve().parent
REPO_DIR = DEMO_DIR.parents[3]
sys.path.insert(0, str(REPO_DIR))

from compgen import runner


if __name__ == "__main__":
    os.chdir(DEMO_DIR)
    which_case = os.environ.get("COMPGEN_FRACTURE_CASE", "case1")
    if not which_case.startswith("case") or not which_case[4:].isdigit():
        raise ValueError(
            f"Invalid COMPGEN_FRACTURE_CASE={which_case!r}; expected a case name such as case0 or case10."
        )

    fracture_config = DEMO_DIR / f"config_{which_case}.json"
    if not fracture_config.is_file():
        raise FileNotFoundError(f"Fracture configuration not found: {fracture_config}")

    results = runner.run(
        str(fracture_config),
        str(DEMO_DIR / "config_machine.json"),
    )
    failed = sum(result == -1 for result in results)
    if failed:
        raise RuntimeError(
            f"{failed} simulation group(s) failed. See the configured log file "
            f"for the detailed error ({which_case})."
        )
    print("Completed local fracture simulations successfully.")
    print(f"Completed {which_case}.")
    print(f"Generated {len(results)} result groups.")