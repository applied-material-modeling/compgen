import numpy as np

import json
import os

from compgen import gen2d, mesh2d, moose, hdfwriter, temp

if __name__ == "__main__":
    n = 128
    lx = 1.0
    ly = 1.0

    generator = gen2d.RandomGenerator(n, n)

    img = next(generator)
    global_settings = json.load(open("config.json"))

    tempdir = temp.make_temp_directory(global_settings)

    pwd = os.getcwd()
    os.chdir(tempdir)
    mesh2d.generate_mesh(img, "mesh.exo", settings=global_settings, sculpt=False)

    res = moose.execute_moose_simulations(
        "2d/elastic",
        "mesh.exo",
        material_properties={
            "A": {"youngs_modulus": 10.0, "poissons_ratio": 0.3},
            "B": {"youngs_modulus": 1.0, "poissons_ratio": 0.3},
            "AB": {},
        },
        settings=global_settings,
    )
    os.chdir(pwd)
    for i, result in enumerate(res):
        result["grid"] = mesh2d.extract_grid_from_mesh(
            result["unstructured_mesh"], img, lx, ly
        )
        with open(f"demo_result_{i}.h5", "wb") as f:
            hdfwriter.write_hdf5(f, result)
