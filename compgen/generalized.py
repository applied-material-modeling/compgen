"""Homogenized ("generalized") scalar quantities for fracture results.

This mirrors the standalone ``process_fracture.py`` post-processing so that
fracture result files come out of the workflow already carrying their
homogenized quantities, instead of requiring a separate post-pass.

For a fracture ``result`` (built by :func:`compgen.moose.process_output`) the
following are computed at full float64 precision, before any downcast:

- area-weighted mean Cauchy stress, overall and per phase,
- maximum plane von Mises stress over undamaged elements,
- area-weighted mean interface damage and damaged-area fraction,
- simple mean of the nodal bulk phase-field damage.

They are injected into ``result["generalized"]`` shaped for
:func:`compgen.hdfwriter.write_hdf5`'s conventions (nested dicts become groups,
scalar str/int/float become attributes, lists become index-keyed attribute
subgroups, and ndarrays become datasets).
"""

import numpy as np

DAMAGE_THRESHOLD = 0.5


def quad_areas(coords, connectivity):
    """Shoelace formula for planar quads, vectorized over all elements."""
    verts = coords[connectivity].astype(np.float64)  # (E, 4, 2)
    x, y = verts[:, :, 0], verts[:, :, 1]
    x_next = np.roll(x, -1, axis=1)
    y_next = np.roll(y, -1, axis=1)
    return 0.5 * np.abs(np.sum(x * y_next - x_next * y, axis=1))  # (E,)


def von_mises_plane(sxx, syy, sxy):
    """Plane von Mises equivalent stress."""
    return np.sqrt(np.maximum(sxx**2 - sxx * syy + syy**2 + 3 * sxy**2, 0.0))


def _element_field(result, category, field):
    """Return an element field data array, or ``None`` if it is absent."""
    try:
        return result["unstructured_mesh"]["element_fields"][category][field]["data"]
    except (KeyError, TypeError):
        return None


def _node_field(result, category, field):
    """Return a node field data array, or ``None`` if it is absent."""
    try:
        return result["unstructured_mesh"]["node_fields"][category][field]["data"]
    except (KeyError, TypeError):
        return None


def has_fracture_fields(result):
    """Return True when ``result`` carries the fields fracture homogenization needs."""
    if not isinstance(result, dict):
        return False
    return (
        _element_field(result, "responses", "cauchy_stress") is not None
        and _element_field(result, "stimuli", "d_interface") is not None
        and _node_field(result, "stimuli", "d") is not None
    )


def compute_fracture_generalized(result, damage_threshold=DAMAGE_THRESHOLD):
    """Compute homogenized fracture quantities from an in-memory result dict.

    Args:
        result (dict): Simulation result as built by ``moose.process_output``.
        damage_threshold (float): Interface damage cutoff separating damaged
            from undamaged elements.

    Returns:
        dict: A nested dictionary shaped for ``write_hdf5`` describing the
        ``generalized/responses`` and ``generalized/stimuli`` subtrees.
    """
    mesh = result["unstructured_mesh"]
    coords = np.asarray(mesh["coords"])
    connectivity = np.asarray(mesh["connectivity"])
    material = np.asarray(mesh["element_fields"]["material"]["data"][0]).astype(bool)  # (E,)

    stress = np.asarray(_element_field(result, "responses", "cauchy_stress"), dtype=np.float64)  # (T, E, 3)
    d_interface = np.asarray(_element_field(result, "stimuli", "d_interface"), dtype=np.float64)  # (T, E)
    d_node = np.asarray(_node_field(result, "stimuli", "d"), dtype=np.float64)  # (T, N)

    areas = quad_areas(coords, connectivity)  # (E,)
    total_area = areas.sum()
    area_true = areas[material].sum()
    area_false = areas[~material].sum()

    # Area-weighted mean stress: overall and restricted to each phase.
    mean_stress = np.einsum("e,tec->tc", areas, stress) / total_area
    mean_stress_true = np.einsum("e,tec->tc", areas * material, stress) / area_true
    mean_stress_false = np.einsum("e,tec->tc", areas * (~material), stress) / area_false

    # Maximum von Mises stress over undamaged elements (NaN when none exist).
    vm = von_mises_plane(stress[:, :, 0], stress[:, :, 1], stress[:, :, 2])  # (T, E)
    undamaged = d_interface < damage_threshold
    masked_vm = np.where(undamaged, vm, -np.inf)
    max_vm_undamaged = masked_vm.max(axis=1)
    max_vm_undamaged = np.where(np.isfinite(max_vm_undamaged), max_vm_undamaged, np.nan)

    mean_d_interface = np.einsum("e,te->t", areas, d_interface) / total_area
    damaged_area_fraction = (
        (areas[None, :] * (d_interface > damage_threshold)).sum(axis=1) / total_area
    )
    mean_d_node = d_node.mean(axis=1)

    return {
        "responses": {
            "cauchy_stress": {
                "dim": 2,
                "type": "symmetric_rank_two_tensor",
                "description": (
                    "Homogenized quantities computed from the full float64 "
                    "cauchy_stress field prior to any precision downcast, "
                    "area-weighted using element areas derived from "
                    "unstructured_mesh/coords and connectivity."
                ),
                "max_von_mises_undamaged_threshold": damage_threshold,
                "field_components": ["stress_xx", "stress_yy", "stress_xy"],
                "mean": mean_stress,
                "mean_phase_true": mean_stress_true,
                "mean_phase_false": mean_stress_false,
                "max_von_mises_undamaged": max_vm_undamaged,
            }
        },
        "stimuli": {
            "d": {
                "location": "node",
                "type": "scalar",
                "description": (
                    "Simple (unweighted) mean of the nodal bulk phase-field damage."
                ),
                "mean": mean_d_node,
            },
            "d_interface": {
                "type": "scalar",
                "damage_threshold": damage_threshold,
                "description": (
                    "Area-weighted mean interface damage and damaged-area fraction."
                ),
                "mean": mean_d_interface,
                "damaged_area_fraction": damaged_area_fraction,
            },
        },
    }


def inject_fracture_generalized(result, damage_threshold=DAMAGE_THRESHOLD):
    """Merge computed fracture generalized quantities into ``result`` in place.

    Existing keys under ``result["generalized"]`` are never overwritten.
    """
    quantities = compute_fracture_generalized(result, damage_threshold)
    generalized = result.setdefault("generalized", {})
    for category, fields in quantities.items():
        target = generalized.setdefault(category, {})
        for field, value in fields.items():
            target.setdefault(field, value)
