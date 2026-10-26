"""Run the Aurora predefined fracture sweep on a local machine."""

import sys
from pathlib import Path


DEMO_DIR = Path(__file__).resolve().parent
REPO_DIR = DEMO_DIR.parents[1]
sys.path.insert(0, str(REPO_DIR))

from compgen import runner


if __name__ == "__main__":
    results = runner.run(
        str(DEMO_DIR / "fracture_predefined_local.json"),
        str(DEMO_DIR / "local_machine_config.json"),
    )
    failed = sum(result == -1 for result in results)
    if failed:
        raise RuntimeError(
            f"{failed} simulation group(s) failed. See the log under /tmp/brb "
            "for the detailed error."
        )
    print("Completed local fracture simulations successfully.")
    print(f"Generated {len(results)} result groups.")