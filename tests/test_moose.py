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

"""Tests for MOOSE load-case failure handling (no MOOSE binary needed)."""

import subprocess

import pytest

from compgen import moose


@pytest.fixture
def fail_second_load(monkeypatch, tmp_path):
    """Stub the solver so load case 1 fails and the others succeed."""
    calls = []

    def run(cmd, env, capture, timeout_s):
        calls.append(cmd)
        if len(calls) == 2:
            raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(moose, "_run_moose_command", run)
    monkeypatch.setattr(moose, "material_property_substitutions", lambda *a: [])
    monkeypatch.setattr(moose, "process_output", lambda *a: {})
    mesh = tmp_path / "mesh.exo"
    mesh.write_text("")
    settings = {
        "moose": {"executable": "moose", "options": []},
        "storage": {"temp_dir": str(tmp_path), "delete_temp_dir": True},
    }
    return str(mesh), settings, calls


def test_failed_load_fails_structure_by_default(fail_second_load):
    """A failed load case drops the structure, so results are never partial."""
    mesh, settings, calls = fail_second_load
    with pytest.raises(RuntimeError, match="did not converge"):
        moose.execute_moose_simulations("2d/elastic", mesh, {}, settings=settings)
    assert len(calls) == 2


def test_failed_load_skipped_when_partial_allowed(fail_second_load):
    """With allow_partial_loads, the other load cases are kept and indexed."""
    mesh, settings, _ = fail_second_load
    settings["moose"]["allow_partial_loads"] = True
    out = moose.execute_moose_simulations("2d/elastic", mesh, {}, settings=settings)
    assert [r["index"] for r in out] == [0, 2]
