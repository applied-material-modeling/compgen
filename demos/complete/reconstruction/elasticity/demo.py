import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

sys.path.append(str(BASE.parents[3]))

from compgen import runner

if __name__ == "__main__":
    runner.run(
        str(BASE / "demo.json"),
        str(BASE.parent / "gen_config.json"),
        str(BASE.parent / "parallel_config.json"),
        str(BASE.parent.parent / "machine_config.json"),
    )
