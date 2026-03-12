"""Tests for runner setup and dispatch behavior."""

import numpy as np

from compgen import runner


def test_setup_runner_defaults_to_threaded_runner_with_legacy_nthreads():
    """If no runner section is provided, use ThreadedRunner and legacy nthreads."""
    r = runner.setup_runner(None, default_nthreads=4)

    assert isinstance(r, runner.ThreadedRunner)
    assert r.nthreads == 4


def test_setup_runner_explicit_threaded_runner_config():
    """An explicit runner section should instantiate configured runner class."""
    r = runner.setup_runner(
        {
            "type": "runner.ThreadedRunner",
            "params": {"nthreads": 2},
        },
        default_nthreads=7,
    )

    assert isinstance(r, runner.ThreadedRunner)
    assert r.nthreads == 2


def test_threaded_runner_single_thread_executes_all_tasks(monkeypatch):
    """Single-threaded mode should map all tasks through run_single."""
    calls = []

    def fake_run_single(img, material_a, material_b, material_ab, config):
        calls.append((img, material_a, material_b, material_ab, config))
        return img + material_a["k"] + material_b["k"] + material_ab["k"]

    monkeypatch.setattr(runner, "run_single", fake_run_single)

    composite = [
        (1, {"k": 2}, {"k": 3}, {"k": 4}, 0),
        (5, {"k": 6}, {"k": 7}, {"k": 8}, 1),
    ]
    cfg = {"nthreads": 99}

    r = runner.ThreadedRunner(nthreads=1)
    out = r.run(composite, config=cfg)

    assert out == [10, 26]
    assert len(calls) == 2
    assert calls[0][-1] is cfg
    assert calls[1][-1] is cfg


def test_run_uses_default_runner_when_runner_section_missing(monkeypatch):
    """Top-level run() should default to threaded runner setup for backward compatibility."""
    captured = {}

    class FakeRunner:
        def run(self, composite, config, log=False):
            captured["composite"] = list(composite)
            captured["config"] = config
            captured["log"] = log
            return ["ok"]

    config = {
        "number": 2,
        "nthreads": 3,
        "generator": {},
        "material_A": {},
        "material_B": {},
    }

    monkeypatch.setattr(runner.utils, "load_json", lambda _: config)
    monkeypatch.setattr(
        runner,
        "setup_generator",
        lambda _: iter([np.array([[1]]), np.array([[0]])]),
    )
    monkeypatch.setattr(runner, "setup_material", lambda _: iter([{"x": 1}, {"x": 2}]))

    def fake_setup_runner(config_input, default_nthreads):
        captured["config_input"] = config_input
        captured["default_nthreads"] = default_nthreads
        return FakeRunner()

    monkeypatch.setattr(runner, "setup_runner", fake_setup_runner)

    out = runner.run("dummy.json")

    assert out == ["ok"]
    assert captured["config_input"] is None
    assert captured["default_nthreads"] == 3
    assert len(captured["composite"]) == 2
