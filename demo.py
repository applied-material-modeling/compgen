import numpy as np

import json
import tempfile
import os

from compgen import gen2d, mesh2d, moose, hdfwriter

if __name__ == "__main__":
    n = 128
    demo_structure = [
        gen2d.Rotate(
            gen2d.Rectangle(0.4, 0.6, -1.0, 2.0),
            np.pi / 4,
            origin=np.array([0.5, 0.5]),
        ),
        gen2d.Rotate(
            gen2d.Rectangle(-1.0, 2.0, 0.4, 0.6),
            np.pi / 4,
            origin=np.array([0.5, 0.5]),
        ),
    ]

    lx = 1.0
    ly = 1.0

    img = gen2d.generate_from_objects(demo_structure, lx, ly, n, n)
    global_settings = json.load(open("config.json"))

    with tempfile.TemporaryDirectory() as tempdir:
        pwd = os.getcwd()
        os.chdir(tempdir)
        mesh2d.generate_mesh(img, "mesh.exo", settings=global_settings)

        res = moose.execute_moose_simulations(
            "2d/elastic",
            "mesh.exo",
            material_properties={
                "A": {"youngs_modulus": 10.0, "poissons_ratio": 0.3},
                "B": {"youngs_modulus": 1.0, "poissons_ratio": 0.3},
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
