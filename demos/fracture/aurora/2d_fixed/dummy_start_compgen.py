import os
import sys
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DEMO_DIR.parents[3]))
os.chdir(DEMO_DIR)

from compgen import runner

if __name__ == "__main__":
    # This demo shows how to run predefined structures from a numpy file with RACOON integration
    # distributed over a SLURM allocation.
    # units are mm-MPa-s

    results = runner.run(
        str(DEMO_DIR / "config_fracture.json"),
        str(DEMO_DIR / "config_machine.json"),
    )

    print("Completed parallel simulations successfully. Results available in result folder.")
