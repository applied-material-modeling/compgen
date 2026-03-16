import sys

sys.path.append("..")

from compgen import runner

if __name__ == "__main__":
    # This demo shows how to run predefined structures from a numpy file with RACOON integration.
    # The 'fracture_predefined.json' targets the 2d/fracture physics template which 
    # hooks into a separate executor 'racoon.execute_racoon_simulations'.

    results = runner.run("fracture_predefined.json", "machine_config.json")

    print(results)
