# Copyright 2026, UChicago Argonne, LLC
# All Rights Reserved
# Software Name: compgen
# By: Argonne National Laboratory
# OPEN SOURCE LICENSE (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""End-to-end verification tests comparing solver outputs to reference physics responses."""

import json

import numpy as np
import pytest

from compgen.runner import run

config_file = "tests/verification/test_config.json"


@pytest.mark.parametrize(
    "input_info,solution",
    [
        (
            ["2d/elasticity.json", "elastic_moose.json"],
            [
                {
                    "density": 5.0,
                    "cauchy_stress": np.stack(
                        [
                            np.zeros(
                                3,
                            ),
                            np.array(
                                [134615.38462, 57692.30769, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "cauchy_stress": np.stack(
                        [
                            np.zeros(
                                3,
                            ),
                            np.array(
                                [0.0, 0.0, 76923.0769231],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "cauchy_stress": np.stack(
                        [
                            np.zeros(
                                3,
                            ),
                            np.array(
                                [57692.30769, 134615.38462, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
            ],
        ),
        (
            ["2d/thermal_conductivity.json", "thermal_moose.json"],
            [
                {
                    "density": 5.0,
                    "heat_flux": np.stack(
                        [
                            np.zeros(
                                2,
                            ),
                            np.array(
                                [10.0, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "heat_flux": np.stack(
                        [
                            np.zeros(
                                2,
                            ),
                            np.array(
                                [0.0, 10.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
            ],
        ),
        (
            ["2d/thermal_conductivity_with_interface.json", "thermal_moose.json"],
            [
                {
                    "density": 5.0,
                    "heat_flux": np.stack(
                        [
                            np.zeros(
                                2,
                            ),
                            np.array(
                                [10.0, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "heat_flux": np.stack(
                        [
                            np.zeros(
                                2,
                            ),
                            np.array(
                                [0.0, 10.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
            ],
        ),
        (
            ["3d/elasticity.json", "elastic_moose.json"],
            [
                {
                    "density": 5.0,
                    "cauchy_stress": np.stack(
                        [
                            np.zeros(
                                6,
                            ),
                            np.array(
                                [134615.38462, 57692.30769, 57692.30769, 0.0, 0.0, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "cauchy_stress": np.stack(
                        [
                            np.zeros(
                                6,
                            ),
                            np.array(
                                [0.0, 0.0, 0.0, 0.0, 0.0, 76923.0769231],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "cauchy_stress": np.stack(
                        [
                            np.zeros(
                                6,
                            ),
                            np.array(
                                [57692.30769, 134615.38462, 57692.30769, 0.0, 0.0, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "cauchy_stress": np.stack(
                        [
                            np.zeros(
                                6,
                            ),
                            np.array(
                                [0.0, 0.0, 0.0, 0.0, 76923.0769231, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "cauchy_stress": np.stack(
                        [
                            np.zeros(
                                6,
                            ),
                            np.array(
                                [0.0, 0.0, 0.0, 76923.0769231, 0.0, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "cauchy_stress": np.stack(
                        [
                            np.zeros(
                                6,
                            ),
                            np.array(
                                [57692.30769, 57692.30769, 134615.38462, 0.0, 0.0, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
            ],
        ),
        (
            ["3d/thermal_conductivity.json", "thermal_moose.json"],
            [
                {
                    "density": 5.0,
                    "heat_flux": np.stack(
                        [
                            np.zeros(
                                3,
                            ),
                            np.array(
                                [10.0, 0.0, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "heat_flux": np.stack(
                        [
                            np.zeros(
                                3,
                            ),
                            np.array(
                                [0.0, 10.0, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "heat_flux": np.stack(
                        [
                            np.zeros(
                                3,
                            ),
                            np.array(
                                [0.0, 0.0, 10.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
            ],
        ),
        (
            ["3d/thermal_conductivity_with_interface.json", "thermal_moose.json"],
            [
                {
                    "density": 5.0,
                    "heat_flux": np.stack(
                        [
                            np.zeros(
                                3,
                            ),
                            np.array(
                                [10.0, 0.0, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "heat_flux": np.stack(
                        [
                            np.zeros(
                                3,
                            ),
                            np.array(
                                [0.0, 10.0, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
                {
                    "density": 5.0,
                    "heat_flux": np.stack(
                        [
                            np.zeros(
                                3,
                            ),
                            np.array(
                                [0.0, 0.0, 10.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
            ],
        ),
        (
            ["2d/thermal_expansion.json", "elastic_moose.json"],
            [
                {
                    "density": 5.0,
                    "total_strain": np.stack(
                        [
                            np.zeros(
                                3,
                            ),
                            np.array(
                                [1, 1, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
            ],
        ),
        (
            ["3d/thermal_expansion.json", "elastic_moose.json"],
            [
                {
                    "density": 5.0,
                    "total_strain": np.stack(
                        [
                            np.zeros(
                                6,
                            ),
                            np.array(
                                [1, 1, 1, 0.0, 0.0, 0.0],
                            ),
                        ],
                        axis=0,
                    ),
                },
            ],
        ),
    ],
)
def test_verification(input_info, solution):
    """Test that the solver outputs match the reference solutions for a set
    of verification problems."""
    problem, moose = input_info
    problem_file = f"tests/verification/{problem}"
    moose_file = f"tests/verification/{moose}"
    result = run(problem_file, config_file, moose_file)

    for simul, correct in zip(result[0], solution):
        for field, value in correct.items():
            if field == "density":
                assert np.isclose(simul["density"], value, rtol=1e-5, atol=1e-8)
            else:
                np.testing.assert_allclose(
                    simul["generalized"]["responses"][field]["data"],
                    value,
                    rtol=1e-5,
                    atol=1e-1,
                )


def _plastic_problem(tmp_path):
    """A 2D plastic problem on inclined lamellae of two different materials.

    The lamellae make the cell anisotropic, so the macroscopic constraints matter:
    with all four in-plane entries stress-controlled the cell rotates and the
    Cauchy stress picks up shear (up to about 0.7 % of its norm here); with the
    triangular F/P constraints it stays diagonal.
    """
    i, j = np.meshgrid(np.arange(32), np.arange(32), indexing="ij")
    lamellae = ((i + 2 * j) % 16) < 8  # periodic on the 32 x 32 grid, vf = 0.5
    np.save(tmp_path / "lamellae.npy", lamellae[np.newaxis])

    def plastic(young, poisson, yield_strength, hardening):
        return {
            "type": "materials.FixedMaterialGenerator",
            "params": {
                "youngs_modulus": young,
                "poissons_ratio": poisson,
                "yield_strength": yield_strength,
                "hardening_modulus": hardening,
            },
        }

    problem = {
        "number": 1,
        "nthreads": 1,
        "mesh_file": "mesh.exo",
        "L": [1.0, 1.0],
        "generator": {
            "type": "gen.FromNumpyGenerator",
            "params": {"filename": str(tmp_path / "lamellae.npy")},
        },
        "mesh": {"type": "mesh.generate_mesh_2d", "params": {"run_sculpt": False}},
        "executor": {
            "type": "moose.execute_moose_simulations",
            "physics": "2d/plastic",
        },
        "material_A": plastic(70000.0, 0.3, 100.0, 1000.0),
        "material_B": plastic(410000.0, 0.14, 500.0, 100.0),
        "material_AB": {"type": "materials.FixedMaterialGenerator", "params": {}},
        "output": {"write_files": False},
    }
    problem_file = tmp_path / "plasticity.json"
    problem_file.write_text(json.dumps(problem), encoding="utf-8")
    return str(problem_file)


def test_plastic_2d_cauchy_stress_is_diagonal(tmp_path):
    """In every load direction the averaged Cauchy stress stays diagonal in the
    load axes, and the plane-strain out-of-plane stress is recorded."""
    result = run(
        _plastic_problem(tmp_path),
        config_file,
        "tests/verification/elastic_moose.json",
    )
    load_cases = result[0]
    assert len(load_cases) == 12

    for case in load_cases:
        stimuli = case["generalized"]["stimuli"]
        sigma = stimuli["cauchy_stress"]["data"]  # (ntime, 3): xx, yy, xy
        norm = np.sqrt(sigma[:, 0] ** 2 + sigma[:, 1] ** 2 + 2 * sigma[:, 2] ** 2)
        loaded = norm > 0.05 * norm.max()
        assert np.all(np.abs(sigma[loaded, 2]) < 1e-3 * norm[loaded])

        sigma_zz = stimuli["cauchy_stress_zz"]["data"]
        assert sigma_zz.shape == sigma.shape[:1]
        assert np.all(np.isfinite(sigma_zz))

    # Plane strain: under the uniaxial load along x (theta = 0), sigma_zz is a
    # sizeable reaction, a large fraction of sigma_xx.
    uniaxial = load_cases[0]["generalized"]["stimuli"]
    sigma_xx = uniaxial["cauchy_stress"]["data"][-1, 0]
    assert uniaxial["cauchy_stress_zz"]["data"][-1] > 0.2 * sigma_xx > 0
