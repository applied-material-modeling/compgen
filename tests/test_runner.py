"""Tests for runner orchestration, focused on retryable vs fatal failures."""

import numpy as np
import pytest

from compgen import runner


NUMBER = 4
FACTOR = 3  # cap = FACTOR * NUMBER draws


class _CountingGenerator:
    """Yields structures and records how many draws the runner asked for."""

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
        "L": [1.0, 1.0],
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
            {"type": "filters.make_periodic", "params": {"margin": 99}},
            runner.filters.FilterInputError,
        ),
        (
            False,
            {"type": "filters.make_periodic", "params": {"margin": 2}},
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
    monkeypatch.setattr(runner, "setup_generator", lambda _c: gen)
    monkeypatch.setattr(runner, "setup_material", lambda _c: iter(lambda: {}, object()))

    with pytest.raises(expected):
        runner.run("unused.json")

    # At most one draw per worker may already be in flight; the point is that the
    # runner does not keep redrawing up to FACTOR * NUMBER.
    assert gen.draws <= nthreads
