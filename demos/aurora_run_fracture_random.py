import sys

sys.path.append("..")

from compgen import runner

if __name__ == "__main__":
    # This demo runs randomly-sampled material configurations with RACOON
    # integration, distributed over a PBS allocation.
    # Materials are drawn per-simulation by materials.DistributionMaterialGenerator
    # (see fracture_random_slurm.json). The drawn properties are recorded in each
    # output .h5, so the sweep is self-documenting.
    # units are mm-MPa-s

    results = runner.run(
        "fracture_random_slurm.json", "aurora_machine_config_random.json"
    )

    print("Completed parallel simulations successfully. Results available in result folder.")
