import sys

sys.path.append("..")

from compgen import runner

if __name__ == "__main__":
    # Small, fast local RACOON smoke test verifying that fracture results come
    # out of the workflow already carrying homogenized ("generalized")
    # quantities and float32/Blosc2-compressed mesh fields. Reduced 64x64
    # resolution and no frame sampling: one full, processed file is written.

    results = runner.run("fracture_verified.json", "machine_config.json")

    print(results)
