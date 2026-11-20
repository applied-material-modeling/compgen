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

"""Tests for runner orchestration, focused on retryable vs fatal failures."""

import numpy as np
import pytest

from compgen import runner

NUMBER = 4
FACTOR = 3  # cap = FACTOR * NUMBER draws


class _CountingGenerator:
    """Yields structures and records how many draws the runner asked for."""

    N = [16, 16]

    def __init__(self, binary=True):
        self.binary = binary
        self.draws = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.draws += 1
        img = np.random.default_rng(self.draws).random((16, 16))
        return img > 0.5 if self.binary else img


def _config(filter_spec, nthreads):
    return {
        "number": NUMBER,
        "max_attempts_factor": FACTOR,
        "dim": 2,
        "L": 1.0,
        "nthreads": nthreads,
        "filtering": [filter_spec],
        "mesh": {"type": "mesh.generate_mesh"},
        "mesh_file": "mesh.exo",
        "executor": {
            "type": "moose.execute_moose_simulations",
            "physics": "2d/thermal",
        },
        "output": {"write_files": False},
        "storage": {"delete_temp_dir": True},
        "generator": {},
        "material_A": {},
        "material_B": {},
    }


@pytest.mark.parametrize("nthreads", [1, 2])
@pytest.mark.parametrize(
    "binary,filter_spec,expected",
    [
        # Resolution errors: caught up front, before any structure is drawn.
        (True, {"type": "filters.nope", "params": {}}, AttributeError),
        (True, {"params": {}}, AttributeError),
        (True, {"type": "a.b.c", "params": {}}, ValueError),
        # Call-time errors: deterministic given the config, so no redraw helps.
        (True, {"type": "filters.mean_filter", "params": {"radiuz": 5}}, TypeError),
        (
            True,
            {"type": "filters.make_periodic", "params": {"margin_cells": 99}},
            runner.filters.FilterInputError,
        ),
        (
            False,
            {"type": "filters.make_periodic", "params": {"margin_cells": 2}},
            runner.filters.NonBinaryImageError,
        ),
    ],
)
def test_deterministic_filter_errors_abort_without_retrying(
    monkeypatch, nthreads, binary, filter_spec, expected
):
    """A filter failure the config guarantees aborts instead of spending the cap."""
    gen = _CountingGenerator(binary=binary)
    config = _config(filter_spec, nthreads)

    monkeypatch.setattr(runner.utils, "load_json", lambda _files: config)
    monkeypatch.setattr(runner, "setup_generator", lambda *_a: gen)
    monkeypatch.setattr(runner, "setup_material", lambda _c: iter(lambda: {}, object()))

    with pytest.raises(expected):
        runner.run("unused.json")

    # At most one draw per worker may already be in flight; the point is that the
    # runner does not keep redrawing up to FACTOR * NUMBER.
    assert gen.draws <= nthreads


class _PredefinedGenerator(_CountingGenerator):
    """NUMBER fixed structures that wrap around, like FromNumpyGenerator.

    Each structure is filled with its index so the stub below can identify it.
    """

    predefined = True
    N = [2, 2]

    def __next__(self):
        self.draws += 1
        return np.full((2, 2), (self.draws - 1) % NUMBER)


@pytest.mark.parametrize("nthreads", [1, 2])
def test_predefined_structures_are_not_backfilled(monkeypatch, nthreads):
    """A mesh failure on a predefined structure stays in place as -1 instead of
    being backfilled with a wrapped-around duplicate of structure 0."""
    gen = _PredefinedGenerator()
    config = _config({"type": "filters.mean_filter", "params": {}}, nthreads)

    def fake_run_single(img, *_args):
        idx = int(img[0, 0])
        return runner.MESH_FAILED if idx == 1 else idx

    monkeypatch.setattr(runner.utils, "load_json", lambda _files: config)
    monkeypatch.setattr(runner, "setup_generator", lambda *_a: gen)
    monkeypatch.setattr(runner, "setup_material", lambda _c: iter(lambda: {}, object()))
    monkeypatch.setattr(runner, "run_single", fake_run_single)

    assert runner.run("unused.json") == [0, -1, 2, 3]
    assert gen.draws == NUMBER


def test_setup_generator_scalar_n_and_dim():
    """A scalar `N` and the config's `dim` give a square/cubic generator."""
    spec = {"type": "gen.RandomGenerator", "params": {"N": 8, "vf": 0.5}}
    assert runner.setup_generator(spec, 3).N == [8, 8, 8]
    with pytest.raises(ValueError, match="dim"):
        runner.setup_generator(spec)
    with pytest.raises(ValueError, match="integer"):
        runner.setup_generator({**spec, "params": {"N": [8, 8], "vf": 0.5}}, 2)


def test_from_numpy_generator_takes_size_from_data(tmp_path):
    """No `N`: the size comes from the data, which must be square/cubic."""
    path = tmp_path / "structures.npy"
    np.save(path, np.zeros((1, 8, 8), dtype=bool))
    gen = runner.setup_generator(
        {"type": "gen.FromNumpyGenerator", "params": {"filename": str(path)}}, 2
    )
    assert gen.N == [8, 8] and gen.dim == 2
    np.save(path, np.zeros((1, 8, 10), dtype=bool))
    with pytest.raises(ValueError, match="square"):
        runner.setup_generator(
            {"type": "gen.FromNumpyGenerator", "params": {"filename": str(path)}}, 2
        )


def _res_config(n_mesh=None, n_out=None, dim=2):
    config = {
        "dim": dim,
        "L": 1.0,
        "mesh": {"params": {}},
        "output": {"grid_extractor": {}},
    }
    if n_mesh is not None:
        config["mesh"]["params"]["N"] = n_mesh
    if n_out is not None:
        config["output"]["grid_extractor"]["params"] = {"N": n_out}
    return config


class _Shape:  # pylint: disable=too-few-public-methods
    def __init__(self, n, dim=2):
        self.N = [n] * dim


def test_check_resolutions_defaults_and_values():
    """N_mesh defaults to N_gen and N_out to N_mesh; non-integer ratios are fine."""
    assert runner.check_resolutions(_res_config(), _Shape(64)) == (64, 64, 64)
    assert runner.check_resolutions(_res_config(96, 128), _Shape(256)) == (256, 96, 128)
    assert runner.check_resolutions(_res_config(96), _Shape(256)) == (256, 96, 96)


def test_check_resolutions_rejects_mesh_finer_than_generator():
    """The mesh cannot be finer than the generated image."""
    with pytest.raises(ValueError, match="below mesh"):
        runner.check_resolutions(_res_config(128), _Shape(96))


def test_check_resolutions_warns_on_aliasing_output(caplog):
    """N_out < N_mesh / 2 logs an aliasing warning."""
    with caplog.at_level("WARNING", logger="compgen.runner"):
        runner.check_resolutions(_res_config(96, 32), _Shape(256))
    assert "alias" in caplog.text


@pytest.mark.parametrize(
    "config",
    [
        {"dim": 4, "L": 1.0},
        {"L": 1.0},
        {"dim": 2, "L": [1.0, 1.0]},
        {"dim": 3, "L": 1.0},  # 2D generator
    ],
)
def test_check_resolutions_rejects_bad_dim_or_l(config):
    """Bad dim, a list L or a generator of another dimension is rejected."""
    with pytest.raises(ValueError):
        runner.check_resolutions(config, _Shape(16))


def test_filter_params_passes_references_only_where_taken():
    """Each filter gets the unit-cell references it takes; an explicit value in
    the config wins."""
    refs = {"n_gen": 256, "n_mesh": 96}
    mp = {"type": "filters.make_periodic", "params": {"margin_cells": 2.5}}
    assert runner.filter_params(runner.filters.make_periodic, mp, refs) == {
        "margin_cells": 2.5,
        "n_gen": 256,
        "n_mesh": 96,
    }
    mf = {"type": "filters.mean_filter", "params": {"radius": 0.02}}
    assert runner.filter_params(runner.filters.mean_filter, mf, refs) == {
        "radius": 0.02,
        "n_gen": 256,
    }
    assert not runner.filter_params(runner.filters.make_orthogonal, {}, refs)
    explicit = {"params": {"margin_cells": 2, "n_mesh": 32}}
    assert (
        runner.filter_params(runner.filters.make_periodic, explicit, refs)["n_mesh"]
        == 32
    )


def test_orthogonal_copies_and_resolutions():
    """make_orthogonal mirrors the generated cell into 2 copies per side of the
    domain: the image, and the default mesh/output N, double; mesh N may then
    exceed the generator N."""
    config = _res_config(64)
    assert runner.orthogonal_copies(config) == 1
    config["filtering"] = [{"type": "filters.make_orthogonal"}]
    assert runner.orthogonal_copies(config) == 2
    assert runner.check_resolutions(config, _Shape(32)) == (64, 64, 64)
    assert runner.check_resolutions(
        _res_config() | {"filtering": config["filtering"]}, _Shape(32)
    ) == (64, 64, 64)


def test_run_single_orthogonal_keeps_domain_and_cell_references(monkeypatch, tmp_path):
    """With make_orthogonal the domain stays [0, L] and mesh/output N refer to
    it, while the filters get the unreplicated cell's N_gen and N_mesh."""
    seen = {}

    def fake_filter(img, n_gen=None, n_mesh=None):
        seen["refs"] = (n_gen, n_mesh)
        return img

    def fake_mesh(img, _fname, L, **params):
        seen["mesh"] = (img.shape, L, params["N"])

    def fake_exec(*_args, **_kwargs):
        return [{"unstructured_mesh": None}]

    def fake_extract(_mesh_data, _img, L, N):
        seen["out"] = (L, N)
        return {"cell_fields": {"material": {"data": np.ones((N, N), bool)}}}

    objs = {
        "fake.filter": fake_filter,
        "fake.mesh": fake_mesh,
        "fake.exec": fake_exec,
        "fake.extract": fake_extract,
    }
    real_get = runner.get_object_from_module
    monkeypatch.setattr(
        runner,
        "get_object_from_module",
        lambda name, **kw: objs.get(name) or real_get(name, **kw),
    )
    config = {
        "dim": 2,
        "L": 1.0,
        "mesh_file": "m.e",
        "storage": {"temp_dir": str(tmp_path), "delete_temp_dir": True},
        "filtering": [{"type": "filters.make_orthogonal"}, {"type": "fake.filter"}],
        "mesh": {"type": "fake.mesh", "params": {"N": 16}},
        "executor": {"type": "fake.exec", "physics": "x"},
        "output": {
            "write_files": False,
            "grid_extractor": {"type": "fake.extract", "params": {"N": 8}},
        },
    }
    img = np.zeros((32, 32), bool)
    img[:5, :7] = True
    runner.run_single(img, {}, {}, {}, config)
    assert seen["refs"] == (32, 8)
    assert seen["mesh"] == ((64, 64), 1.0, 16)
    assert seen["out"] == (1.0, 8)
