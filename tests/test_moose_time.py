from unittest.mock import MagicMock, patch

import h5py
import numpy as np
import pytest

from compgen.hdfwriter import write_hdf5
from compgen.moose import (
    get_simulation_times,
    process_output,
    validate_time_alignment,
)


def tensor(data):
    return {"type": "scalar", "shape": tuple(), "data": np.asarray(data)}


def simulation_mesh(frame_count=3):
    return {
        "coords": np.zeros((2, 2)),
        "connectivity": np.zeros((1, 4), dtype=int),
        "element_fields": {
            "material": tensor(np.ones((1, 1), dtype=bool)),
            "responses": {
                "stress": tensor(np.arange(frame_count).reshape(frame_count, 1))
            },
            "stimuli": {},
        },
    }


def test_get_simulation_times_preserves_exodus_values_as_float64():
    exodus_file = MagicMock()
    exodus_file.__enter__.return_value.get_times.return_value = [0.0, 2.0e-4, 3.0e-4]

    with patch("compgen.moose.exodusii.File", return_value=exodus_file):
        times = get_simulation_times("output.e")

    np.testing.assert_array_equal(times, [0.0, 2.0e-4, 3.0e-4])
    assert times.dtype == np.dtype("float64")


def test_validate_time_alignment_rejects_mismatched_transient_field():
    mesh = simulation_mesh(frame_count=2)

    with pytest.raises(ValueError, match="does not match 3 saved times"):
        validate_time_alignment({"unstructured_mesh": mesh}, np.arange(3))


def test_process_output_writes_exact_time_dataset(tmp_path):
    times = np.array([0.0, 2.0e-4, 3.0e-4], dtype=np.float64)
    mesh = simulation_mesh(frame_count=len(times))

    with (
        patch("compgen.moose.simplify_mesh", return_value=mesh),
        patch("compgen.moose.append_field_results", return_value=mesh),
        patch(
            "compgen.moose.generalized_stimuli_and_forces",
            return_value={"stimuli": {}, "responses": {}},
        ),
        patch("compgen.moose.extract_physics_data", return_value={"type": "transient"}),
        patch("compgen.moose.get_simulation_times", return_value=times),
    ):
        result = process_output("2d/fracture", "mesh.exo", {}, "output.e", "output.csv")

    output = tmp_path / "result.h5"
    write_hdf5(output, result)

    with h5py.File(output, "r") as hdf:
        assert "time" in hdf
        np.testing.assert_array_equal(hdf["time"][:], times)
        assert hdf["time"].dtype == np.dtype("float64")
        assert hdf["unstructured_mesh/element_fields/responses/stress/data"].shape[
            0
        ] == len(hdf["time"])
