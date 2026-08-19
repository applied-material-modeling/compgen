from pathlib import Path

import h5py
import numpy as np

from compgen import generalized
from compgen.hdfwriter import write_hdf5
from compgen.runner import write_result_files


def tensor(data):
    return {"type": "scalar", "shape": tuple(), "data": np.asarray(data)}


def fracture_result():
    """Two unit-square quads (phase A + phase B) over three time frames.

    Only ``stress_xx`` is nonzero so the plane von Mises reduces to ``|sxx|``,
    making the reference values easy to hand-check. Frame 2 fully damages both
    elements so ``max_von_mises_undamaged`` must be NaN there.
    """
    coords = np.array(
        [[0, 0], [1, 0], [2, 0], [0, 1], [1, 1], [2, 1]], dtype=np.float64
    )
    connectivity = np.array([[0, 1, 4, 3], [1, 2, 5, 4]], dtype=np.int64)
    material = np.array([[True, False]])  # (1, E)

    stress = np.zeros((3, 2, 3), dtype=np.float64)
    stress[0, :, 0] = [10.0, 20.0]
    stress[1, :, 0] = [30.0, 40.0]
    stress[2, :, 0] = [50.0, 60.0]

    d_interface = np.array(
        [[0.1, 0.2], [0.1, 0.9], [0.9, 0.9]], dtype=np.float64
    )
    d_node = np.array([[0.0] * 6, [0.5] * 6, [1.0] * 6], dtype=np.float64)

    return {
        "time": np.array([0.0, 1.0, 2.0], dtype=np.float64),
        "physics": {"type": "transient"},
        "unstructured_mesh": {
            "coords": coords,
            "connectivity": connectivity,
            "element_fields": {
                "material": tensor(material),
                "responses": {"cauchy_stress": {"type": "symmetric_rank_two_tensor", "shape": (3,), "data": stress}},
                "stimuli": {"d_interface": tensor(d_interface)},
            },
            "node_fields": {"stimuli": {"d": tensor(d_node)}, "responses": {}},
        },
        "generalized": {"stimuli": {}, "responses": {}},
    }


def test_has_fracture_fields_detects_fracture_and_ignores_plain_results():
    assert generalized.has_fracture_fields(fracture_result()) is True

    plain = {
        "unstructured_mesh": {
            "element_fields": {
                "responses": {"stress": tensor(np.zeros((2, 2)))},
                "stimuli": {},
            }
        }
    }
    assert generalized.has_fracture_fields(plain) is False


def test_compute_fracture_generalized_matches_reference():
    quantities = generalized.compute_fracture_generalized(fracture_result())

    resp = quantities["responses"]["cauchy_stress"]
    np.testing.assert_allclose(resp["mean"][:, 0], [15.0, 35.0, 55.0])
    np.testing.assert_allclose(resp["mean_phase_true"][:, 0], [10.0, 30.0, 50.0])
    np.testing.assert_allclose(resp["mean_phase_false"][:, 0], [20.0, 40.0, 60.0])

    # Frame 0: both undamaged -> max(|10|, |20|) = 20.
    # Frame 1: only phase-A element undamaged -> |30| = 30.
    # Frame 2: no undamaged element -> NaN.
    vm = resp["max_von_mises_undamaged"]
    np.testing.assert_allclose(vm[:2], [20.0, 30.0])
    assert np.isnan(vm[2])

    d_iface = quantities["stimuli"]["d_interface"]
    np.testing.assert_allclose(d_iface["mean"], [0.15, 0.5, 0.9])
    np.testing.assert_allclose(d_iface["damaged_area_fraction"], [0.0, 0.5, 1.0])
    np.testing.assert_allclose(quantities["stimuli"]["d"]["mean"], [0.0, 0.5, 1.0])


def test_inject_fracture_generalized_does_not_overwrite_existing_keys():
    result = fracture_result()
    sentinel = tensor(np.array([1.0, 2.0, 3.0]))
    result["generalized"]["stimuli"]["d"] = sentinel

    generalized.inject_fracture_generalized(result)

    assert result["generalized"]["stimuli"]["d"] is sentinel
    assert "cauchy_stress" in result["generalized"]["responses"]


def test_write_hdf5_compresses_mesh_and_preserves_generalized(tmp_path: Path):
    big = np.arange(4096, dtype=np.float64).reshape(8, 512)
    data = {
        "mesh_field": big,
        "generalized": {"responses": {"mean": np.arange(2048, dtype=np.float64)}},
    }
    output = tmp_path / "compressed.h5"

    write_hdf5(output, data, compress=True)

    with h5py.File(output, "r") as hdf:
        mesh = hdf["mesh_field"]
        assert mesh.dtype == np.float32
        assert mesh.chunks is not None
        # Third-party (Blosc2) filters are not surfaced via .compression, so
        # inspect the dataset creation filter pipeline directly.
        assert mesh.id.get_create_plist().get_nfilters() > 0
        np.testing.assert_allclose(mesh[:], big.astype(np.float32))

        gen = hdf["generalized/responses/mean"]
        assert gen.dtype == np.float64
        assert gen.chunks is None
        assert gen.id.get_create_plist().get_nfilters() == 0


def test_write_result_files_injects_generalized_and_compresses(tmp_path: Path):
    result = fracture_result()
    output = tmp_path / "verified_result_id_0.h5"

    written = write_result_files(output, result, {})

    assert written == [output]
    with h5py.File(output, "r") as hdf:
        resp = hdf["generalized/responses/cauchy_stress"]
        assert resp["mean"].dtype == np.float64
        assert resp.attrs["type"] == "symmetric_rank_two_tensor"
        assert resp["field_components"].attrs["0"] == "stress_xx"
        np.testing.assert_allclose(resp["mean"][:, 0], [15.0, 35.0, 55.0])
        # Mesh stress field downcast to float32 by compression.
        assert (
            hdf["unstructured_mesh/element_fields/responses/cauchy_stress/data"].dtype
            == np.float32
        )
