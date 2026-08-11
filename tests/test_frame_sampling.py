from pathlib import Path

import h5py
import numpy as np
import pytest

from compgen.frame_sampling import sample_result_frames, select_frame_indices
from compgen.runner import write_result_files


def tensor(data):
    return {"type": "scalar", "shape": tuple(), "data": np.asarray(data)}


def transient_result(times):
    times = np.asarray(times, dtype=np.float64)
    frame_values = np.arange(times.size, dtype=np.float64)
    return {
        "time": times,
        "physics": {"type": "transient"},
        "unstructured_mesh": {
            "coords": np.zeros((3, 2)),
            "connectivity": np.zeros((2, 4), dtype=np.int64),
            "element_fields": {
                "material": tensor(np.ones((1, 2), dtype=bool)),
                "responses": {
                    "stress": tensor(np.repeat(frame_values[:, None], 2, axis=1))
                },
                "stimuli": {},
            },
        },
        "generalized": {
            "responses": {"force": tensor(frame_values)},
            "stimuli": {},
        },
    }


def test_selects_twenty_actual_frames_nearest_to_even_times():
    times = np.arange(300, dtype=np.float64)

    selected = select_frame_indices(times, max_frames=20)

    assert selected.size == 20
    assert selected[0] == 0
    assert selected[-1] == 299
    assert np.all(np.diff(selected) > 0)
    targets = np.linspace(times[0], times[-1], 20)
    assert np.max(np.abs(times[selected] - targets)) <= 0.5


def test_keeps_every_frame_when_result_has_fewer_than_maximum():
    result = transient_result([0.0, 0.1, 0.4, 1.0])

    sampled = sample_result_frames(result, max_frames=20)

    np.testing.assert_array_equal(sampled["time"], result["time"])
    np.testing.assert_array_equal(
        sampled["frame_sampling"]["original_frame_indices"], np.arange(4)
    )
    assert sampled["frame_sampling"]["reduction_applied"] is False


def test_samples_every_transient_tensor_and_preserves_constant_fields():
    result = transient_result([0.0, 0.1, 0.2, 0.4, 0.8, 1.0])

    sampled = sample_result_frames(result, max_frames=4)

    expected_indices = np.array([0, 3, 4, 5])
    np.testing.assert_array_equal(
        sampled["frame_sampling"]["original_frame_indices"], expected_indices
    )
    np.testing.assert_array_equal(sampled["time"], result["time"][expected_indices])
    np.testing.assert_array_equal(
        sampled["generalized"]["responses"]["force"]["data"], expected_indices
    )
    assert sampled["unstructured_mesh"]["element_fields"]["responses"]["stress"][
        "data"
    ].shape == (4, 2)
    assert sampled["unstructured_mesh"]["element_fields"]["material"]["data"].shape == (
        1,
        2,
    )


def test_rejects_a_tensor_with_a_misaligned_frame_axis():
    result = transient_result([0.0, 0.5, 1.0])
    result["generalized"]["responses"]["force"] = tensor([0.0, 1.0])

    with pytest.raises(ValueError, match="has 2 frames, expected 1 or 3"):
        sample_result_frames(result, max_frames=2)


def test_writes_sampled_and_full_hdf5_files(tmp_path: Path):
    result = transient_result([0.0, 0.1, 0.2, 0.4, 0.8, 1.0])
    output = tmp_path / "local_result_id_0.h5"

    written = write_result_files(
        output,
        result,
        {
            "frame_sampling": {
                "max_frames": 3,
                "write_full_result": True,
            }
        },
    )

    full_output = tmp_path / "local_result_id_0_all_frames.h5"
    assert written == [str(full_output), output]
    with h5py.File(full_output, "r") as full_hdf:
        np.testing.assert_array_equal(full_hdf["time"][:], result["time"])
        assert "frame_sampling" not in full_hdf
    with h5py.File(output, "r") as sampled_hdf:
        np.testing.assert_array_equal(sampled_hdf["time"][:], [0.0, 0.4, 1.0])
        assert sampled_hdf["frame_sampling"].attrs["original_frame_count"] == 6
        assert sampled_hdf["frame_sampling"].attrs["retained_frame_count"] == 3
        np.testing.assert_array_equal(
            sampled_hdf["frame_sampling/original_frame_indices"][:], [0, 3, 5]
        )
        assert sampled_hdf[
            "unstructured_mesh/element_fields/responses/stress/data"
        ].shape == (3, 2)


@pytest.mark.parametrize("max_frames", [True, 1, 0, -1, 2.5])
def test_rejects_invalid_max_frames(max_frames):
    expected_exception = (
        TypeError if max_frames is True or max_frames == 2.5 else ValueError
    )
    with pytest.raises(expected_exception):
        select_frame_indices(np.arange(3), max_frames)
