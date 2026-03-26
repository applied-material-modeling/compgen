import sys

sys.path.append("../../../..")

from compgen import runner

if __name__ == "__main__":
    runner.run(
        "demo.json",
        "../thermal_config_rec.json",
        "../parallel_config.json",
        "../../machine_config.json",
    )
