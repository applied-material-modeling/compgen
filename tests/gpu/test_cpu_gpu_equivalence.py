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

"""Check that the CPU and GPU versions of each physics give the same answer.

Each test runs the same mesh, materials and load cases through
``moose.execute_moose_simulations`` in cpu mode (the original templates) and gpu mode
(Kokkos assembly and materials, device PETSc), then compares, for every load case, the
volume-averaged stimuli/responses (the CSV postprocessors, every time step for the transient
physics) and the element fields.

Both modes solve the same discrete problem (the same homogenization constraints, kinematics,
volumetric locking correction and constitutive models), so they agree to solver tolerance.
The nonlinear tolerances are tightened in both modes (``options``) so that the comparison
tolerance can be tight.

These tests need a GPU build of MOOSE and a GPU, so they are skipped unless
``COMPGEN_TEST_DEVICE`` names the compute device (e.g. ``xpu``). The executables are
``$MOOSE_DIR/modules/<module>/<module>-opt`` for the module each physics needs
(solid_mechanics or heat_transfer), or ``COMPGEN_TEST_MOOSE`` for all of them (e.g. a
combined app). ``COMPGEN_TEST_MPI`` (e.g. ``mpiexec``) enables the multi-rank cases, and
``COMPGEN_TEST_VERBOSE=1`` (with ``pytest -s``) shows the MOOSE output.
"""

import os

import exodusii
import numpy as np
import pytest

from compgen import mesh, moose
from compgen.exoutil import get_element_field

DEVICE = os.environ.get("COMPGEN_TEST_DEVICE")
MOOSE_DIR = os.environ.get("MOOSE_DIR", "")
MPI = os.environ.get("COMPGEN_TEST_MPI")


def _executable(physics):
    if "COMPGEN_TEST_MOOSE" in os.environ:
        return os.environ["COMPGEN_TEST_MOOSE"]
    module = "heat_transfer" if "thermal_conductivity" in physics else "solid_mechanics"
    return os.path.join(MOOSE_DIR, "modules", module, f"{module}-opt")


pytestmark = [
    pytest.mark.gpu,
    pytest.mark.skipif(
        not DEVICE
        or not all(
            os.path.isfile(_executable(p))
            for p in ("2d/elastic", "2d/thermal_conductivity")
        ),
        reason="set COMPGEN_TEST_DEVICE (and MOOSE_DIR or COMPGEN_TEST_MOOSE) to run",
    ),
]

ELASTIC = {
    "A": {"youngs_modulus": 100000.0, "poissons_ratio": 0.3},
    "B": {"youngs_modulus": 410000.0, "poissons_ratio": 0.14},
    "AB": {},
}
EXPANSION = {
    "A": {
        "youngs_modulus": 100000.0,
        "poissons_ratio": 0.3,
        "thermal_expansion_coefficient": 1e-5,
    },
    "B": {
        "youngs_modulus": 410000.0,
        "poissons_ratio": 0.14,
        "thermal_expansion_coefficient": 4e-6,
    },
    "AB": {},
}
PLASTIC = {
    "A": {
        "youngs_modulus": 100000.0,
        "poissons_ratio": 0.3,
        "yield_strength": 100.0,
        "hardening_modulus": 1000.0,
    },
    "B": {
        "youngs_modulus": 200000.0,
        "poissons_ratio": 0.25,
        "yield_strength": 300.0,
        "hardening_modulus": 5000.0,
    },
    "AB": {},
}
THERMAL = {
    "A": {"conductivity": 1.0},
    "B": {"conductivity": 100.0},
    "AB": {"interfacial_conductivity": 50.0},
}

TIGHT = [
    "Executioner/nl_rel_tol=1e-12",
    "Executioner/nl_abs_tol=1e-9",
    "Executioner/nl_max_its=50",
]

# The plastic physics loads until the equivalent strain limit, several hundred time steps.
# Stop both modes at t = 0.2 (about 10 steps past yield for these materials) so the test
# runs in minutes; on a mesh this small the GPU solve is latency bound.
PLASTIC_OPTIONS = TIGHT + ["Executioner/end_time=0.2"]

# physics, materials, options for both modes, rtol (averages and fields)
CASES = [
    ("2d/elastic", ELASTIC, TIGHT, 1e-7),
    ("3d/elastic", ELASTIC, TIGHT, 1e-7),
    ("2d/thermal_expansion", EXPANSION, TIGHT, 1e-7),
    ("3d/thermal_expansion", EXPANSION, TIGHT, 1e-7),
    ("2d/plastic", PLASTIC, PLASTIC_OPTIONS, 1e-6),
    ("3d/plastic", PLASTIC, PLASTIC_OPTIONS, 1e-6),
    ("2d/thermal_conductivity", THERMAL, [], 1e-8),
    ("3d/thermal_conductivity", THERMAL, [], 1e-8),
    ("2d/thermal_conductivity_with_interface", THERMAL, [], 1e-8),
    ("3d/thermal_conductivity_with_interface", THERMAL, [], 1e-8),
]

# Load directions of the plastic physics run here (of the 12 in its settings)
PLASTIC_LOADS = (0, 2)


def _image(dim):
    """A two-phase image with no symmetry: an off-center disk/ball plus a bar."""
    n = 24 if dim == 2 else 10
    x = (np.arange(n) + 0.5) / n
    grids = np.meshgrid(*([x] * dim), indexing="ij")
    center = [0.4, 0.55, 0.45][:dim]
    r2 = sum((g - c) ** 2 for g, c in zip(grids, center))
    img = r2 < 0.3**2
    img |= (grids[0] > 0.75) & (grids[1] < 0.3)
    return img.astype(np.uint8)


@pytest.fixture(name="meshes", scope="module")
def _meshes(tmp_path_factory):
    out = {}
    for dim in (2, 3):
        d = tmp_path_factory.mktemp(f"mesh{dim}d")
        fname = str(d / "mesh.exo")
        cwd = os.getcwd()
        os.chdir(d)
        try:
            mesh.generate_mesh(
                _image(dim),
                "mesh.exo",
                L=(1.0,) * dim,
                settings={"storage": {"temp_dir": str(d), "delete_temp_dir": True}},
                run_sculpt=False,
                quality_check=False,
            )
        finally:
            os.chdir(cwd)
        out[dim] = fname
    return out


def _settings(physics, mode, tmp_path, ranks=1, options=()):
    settings = {
        "moose": {
            "executable": _executable(physics),
            "options": list(options),
            "mode": mode,
            "device": DEVICE,
        },
        "storage": {"temp_dir": str(tmp_path), "delete_temp_dir": False},
        # COMPGEN_TEST_VERBOSE=1 shows the MOOSE output (use with pytest -s)
        "verbose": bool(os.environ.get("COMPGEN_TEST_VERBOSE")),
    }
    if ranks > 1:
        settings["mpi"] = {"executable": MPI, "rank_command": "-n", "ranks": ranks}
    return settings


def _fields(physics, exo_file):
    _, info = moose.get_physics(physics)
    names = []
    for group in ("stimuli_fields", "response_fields"):
        for field in info[group].values():
            names += field["field_components"]
    with exodusii.File(exo_file, mode="r") as exo:
        return {name: np.asarray(get_element_field(exo, name)) for name in names}


def _run(physics, mesh_file, materials, mode, tmp_path, ranks=1, options=(), tag=None):
    tmp = tmp_path / (tag or mode)
    tmp.mkdir()
    settings = _settings(physics, mode, tmp, ranks, options)
    results = moose.execute_moose_simulations(
        physics, mesh_file, materials, settings=settings
    )
    # Keep the exodus output for the field comparison
    run_dir = next(p for p in tmp.iterdir() if p.is_dir())
    fields = [
        _fields(physics, str(run_dir / f"output_{r['index']}.e")) for r in results
    ]
    return results, fields


def _assert_close(gpu, cpu, rtol, what):
    gpu = np.asarray(gpu, dtype=float)
    cpu = np.asarray(cpu, dtype=float)
    scale = max(np.max(np.abs(cpu)), 1e-300)
    err = np.max(np.abs(gpu - cpu)) / scale
    assert err <= rtol, f"{what}: relative difference {err:.3e} > {rtol:.1e}"


def _compare(physics, cpu, gpu, rtol_avg, rtol_field=None):
    (cpu_res, cpu_fields), (gpu_res, gpu_fields) = cpu, gpu
    assert [r["index"] for r in gpu_res] == [r["index"] for r in cpu_res]
    for c, g, cf, gf in zip(cpu_res, gpu_res, cpu_fields, gpu_fields):
        load = c["index"]
        for kind in ("stimuli", "responses"):
            for name, tensor in c["generalized"][kind].items():
                _assert_close(
                    g["generalized"][kind][name]["data"],
                    tensor["data"],
                    rtol_avg,
                    f"{physics} load {load} average {name}",
                )
        if rtol_field is None:
            continue
        for name, values in cf.items():
            _assert_close(
                gf[name], values, rtol_field, f"{physics} load {load} field {name}"
            )


@pytest.fixture(autouse=True)
def _fewer_plastic_loads(monkeypatch):
    """Run only PLASTIC_LOADS of the plastic physics' load directions."""
    get_physics = moose.get_physics

    def trimmed(name, *args, **kwargs):
        template, settings = get_physics(name, *args, **kwargs)
        if "substitution_dictionary" in settings:
            settings["substitution_dictionary"] = {
                k: [v[i] for i in PLASTIC_LOADS]
                for k, v in settings["substitution_dictionary"].items()
            }
        return template, settings

    monkeypatch.setattr(moose, "get_physics", trimmed)


@pytest.mark.parametrize("physics,materials,options,rtol", CASES)
def test_cpu_gpu_equivalence(physics, materials, options, rtol, meshes, tmp_path):
    """CPU and GPU templates give the same averages and fields for every load case."""
    mesh_file = meshes[int(physics[0])]
    gpu = _run(physics, mesh_file, materials, "gpu", tmp_path, options=options)
    cpu = _run(physics, mesh_file, materials, "cpu", tmp_path, options=options)
    _compare(physics, cpu, gpu, rtol, rtol)


@pytest.mark.skipif(not MPI, reason="set COMPGEN_TEST_MPI (e.g. mpiexec) to run")
@pytest.mark.parametrize(
    "physics,materials",
    [
        ("2d/elastic", ELASTIC),
        ("2d/plastic", PLASTIC),
        ("3d/thermal_expansion", EXPANSION),
        ("3d/thermal_conductivity_with_interface", THERMAL),
    ],
)
def test_gpu_multirank_matches_single_rank(physics, materials, meshes, tmp_path):
    """A 2-rank GPU run (one device per rank) matches the single-rank GPU run."""
    mesh_file = meshes[int(physics[0])]
    options = PLASTIC_OPTIONS if "plastic" in physics else TIGHT
    one = _run(physics, mesh_file, materials, "gpu", tmp_path, options=options)
    two = _run(
        physics,
        mesh_file,
        materials,
        "gpu",
        tmp_path,
        ranks=2,
        tag="gpu2",
        options=options,
    )
    _compare(physics, one, two, 1e-7, 1e-7)
