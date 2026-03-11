"""End-to-end verification tests comparing solver outputs to reference physics responses."""

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
