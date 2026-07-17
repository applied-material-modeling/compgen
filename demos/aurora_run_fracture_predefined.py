import sys

sys.path.append("..")

from compgen import runner

if __name__ == "__main__":
    # This demo shows how to run predefined structures from a numpy file with RACOON integration
    # distributed over a SLURM allocation.
    # units are mm-MPa-s

    results = runner.run("fracture_predefined_slurm.json", "aurora_machine_config.json")

    print("Completed parallel simulations successfully. Results available in result folder.")
