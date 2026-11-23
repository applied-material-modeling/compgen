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

import os
import re
import subprocess

import pytest

from compgen import moose


@pytest.fixture(name="fail_second_load")
def _fail_second_load(monkeypatch, tmp_path):
    """Stub the solver so load case 1 fails and the others succeed."""
    calls = []

    def run(cmd, **_kwargs):
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


# ---------------------------------------------------------------------------------------------
# cpu/gpu mode
# ---------------------------------------------------------------------------------------------
GPU_PHYSICS = [
    f"{d}d/{p}"
    for d in (2, 3)
    for p in (
        "elastic",
        "plastic",
        "thermal_expansion",
        "thermal_conductivity",
        "thermal_conductivity_with_interface",
    )
]


def test_every_physics_has_a_gpu_version():
    """All bundled physics support both modes."""
    base = os.path.join(os.path.dirname(moose.__file__), "physics")
    physics = sorted(
        f"{d}/{p}" for d in os.listdir(base) for p in os.listdir(os.path.join(base, d))
    )
    assert physics == sorted(GPU_PHYSICS)
    for name in physics:
        assert moose.supports_mode(name, "cpu") and moose.supports_mode(name, "gpu")


def test_physics_without_gpu_block_rejects_gpu_mode(monkeypatch, tmp_path):
    """A physics whose settings have no "gpu" block cannot run in gpu mode."""
    phys = tmp_path / "physics" / "2d" / "cpu_only"
    phys.mkdir(parents=True)
    (phys / "settings.json").write_text("{}")
    (phys / "template.i").write_text("")
    monkeypatch.setattr(moose, "__file__", str(tmp_path / "moose.py"))
    assert moose.supports_mode("2d/cpu_only", "cpu")
    assert not moose.supports_mode("2d/cpu_only", "gpu")
    with pytest.raises(ValueError, match="no GPU version"):
        moose.get_physics("2d/cpu_only", mode="gpu")


@pytest.mark.parametrize("physics", GPU_PHYSICS)
def test_gpu_physics_files_exist(physics):
    """Each GPU physics has its template, and the CPU settings are unchanged."""
    template, settings = moose.get_physics(physics, mode="gpu")
    assert template.endswith("template_gpu.i") and os.path.isfile(template)
    assert "gpu" not in settings
    cpu_template, cpu_settings = moose.get_physics(physics)
    assert cpu_template.endswith("template.i")
    assert "gpu" not in cpu_settings
    # gpu substitutions describe the same load cases and the same output fields
    if isinstance(settings.get("target_substitution"), list):
        assert len(settings["target_substitution"]) == cpu_settings["number_of_targets"]
    for key in ("response_fields", "stimuli_fields", "output_substitution", "type"):
        assert settings[key] == cpu_settings[key]
    assert settings.get("substitution_dictionary") == cpu_settings.get(
        "substitution_dictionary"
    )


def _check_path_in_template(path, text, template):
    """A substitution path is a top-level variable or a [block]/.../param in the template."""
    parts = path.split("/")
    if len(parts) == 1:
        assert re.search(rf"^{path}\s*=", text, re.M), f"{path} not in {template}"
        return
    pos = 0
    for block in parts[:-1]:
        m = re.compile(rf"^\s*\[(\./)?{re.escape(block)}\]\s*$", re.M).search(text, pos)
        assert m, f"[{block}] of {path} not in {template}"
        pos = m.end()
    end = min(i for i in (text.find("[]", pos), text.find("[../]", pos)) if i >= 0)
    assert re.search(
        rf"^\s*{parts[-1]}\s*=", text[pos:end], re.M
    ), f"{path} not in {template}"


@pytest.mark.parametrize("physics", GPU_PHYSICS)
@pytest.mark.parametrize("mode", ["cpu", "gpu"])
def test_substitution_targets_exist_in_template(physics, mode):
    """Every input-file path and top-level variable that compgen sets exists in the template."""
    template, settings = moose.get_physics(physics, mode=mode)
    with open(template, encoding="utf-8") as f:
        text = f.read()
    paths = []
    targets = settings.get("target_substitution")
    if targets is not None:
        paths += [targets] if isinstance(targets, str) else list(targets)
    paths += list(settings.get("substitution_dictionary", {}))
    props = settings["material_properties"]
    for key in (
        "material_A_substitutions",
        "material_B_substitutions",
        "interface_substitutions",
    ):
        for entry in props.get(key, []):
            paths += [entry] if isinstance(entry, str) else list(entry)
    paths.append(settings["output_substitution"])
    for path in paths:
        _check_path_in_template(path, text, template)


def test_unknown_mode_rejected():
    """Only cpu and gpu modes exist."""
    with pytest.raises(ValueError, match="Unknown MOOSE mode"):
        moose.get_physics("2d/elastic", mode="tpu")
    with pytest.raises(ValueError, match="Unknown MOOSE mode"):
        moose.moose_mode({"moose": {"mode": "tpu"}})


def test_target_substitutions_list_form():
    """A list of paths gets one value each; a string gets the space-separated list."""
    assert moose.target_substitutions(1, 3, "a/targets", "value", "zero") == [
        "a/targets='zero value zero'"
    ]
    assert moose.target_substitutions(1, 3, ["exx", "exy", "eyy"], "1", "0") == [
        "exx=0",
        "exy=1",
        "eyy=0",
    ]
    with pytest.raises(ValueError, match="Expected 3"):
        moose.target_substitutions(0, 3, ["exx", "exy"], "1", "0")


def test_material_substitutions_accept_path_lists():
    """One property can be substituted into several input-file paths."""
    props = {
        "bulk_material_properties": ["k"],
        "material_A_substitutions": [["k1", "Materials/a/k"]],
        "material_B_substitutions": ["k2"],
    }
    subs = moose.material_property_substitutions({"A": {"k": 1}, "B": {"k": 2}}, props)
    assert subs == ["k1=1", "Materials/a/k=1", "k2=2"]


def test_material_substitutions_convert_lame():
    """Lame parameters are converted to E/nu for the MOOSE templates."""
    _, settings = moose.get_physics("2d/elastic")
    E, nu = 100000.0, 0.25
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E / (2 * (1 + nu))
    subs = moose.material_property_substitutions(
        {
            "A": {"lame_lambda": lam, "lame_mu": mu},
            "B": {"youngs_modulus": 120000.0, "poissons_ratio": 0.21},
        },
        settings["material_properties"],
    )
    values = dict(s.split("=", 1) for s in subs)
    assert float(values["Materials/elastic_tensor_1/youngs_modulus"]) == pytest.approx(
        E
    )
    assert float(values["Materials/elastic_tensor_1/poissons_ratio"]) == pytest.approx(
        nu
    )
    assert values["Materials/elastic_tensor_2/youngs_modulus"] == "120000.0"
    assert values["Materials/elastic_tensor_2/poissons_ratio"] == "0.21"


def test_material_substitutions_convert_bulk_shear():
    """Bulk/shear moduli are converted to E/nu for the MOOSE templates."""
    _, settings = moose.get_physics("3d/plastic", mode="gpu")
    E, nu = 100000.0, 0.3
    K = E / (3 * (1 - 2 * nu))
    G = E / (2 * (1 + nu))
    mat = {"bulk_modulus": K, "shear_modulus": G, "yield_strength": 1.0}
    mat["hardening_modulus"] = 1.0
    subs = moose.material_property_substitutions(
        {"A": mat, "B": mat}, settings["material_properties"]
    )
    values = dict(s.split("=", 1) for s in subs)
    for phase in (1, 2):
        path = f"Materials/compute_stress_{phase}/"
        assert float(values[path + "youngs_modulus"]) == pytest.approx(E)
        assert float(values[path + "poissons_ratio"]) == pytest.approx(nu)


def _gpu_settings(**gpu):
    return {
        "moose": {
            "executable": "moose",
            "options": ["-x"],
            "mode": "gpu",
            "device": "xpu",
        },
        "gpu": gpu,
    }


def test_build_command_cpu_mode_unchanged():
    """cpu mode keeps the original command: [mpi] moose options args."""
    settings = {
        "moose": {"executable": "moose", "options": ["-x"]},
        "mpi": {"executable": "mpirun", "rank_command": "-np", "ranks": "4"},
    }
    cmd, _ = moose.build_moose_command(settings, ["-i", "input.i"])
    assert cmd == ["mpirun", "-np", "4", "moose", "-x", "-i", "input.i"]


def test_build_command_gpu_single_rank():
    """gpu mode adds the device flag and the binding wrapper; the slot sets the offset."""
    cmd, env = moose.build_moose_command(
        _gpu_settings(devices_per_node=12), ["-i", "input.i"], slot=3
    )
    assert cmd[:2] == ["bash", moose.gpu_bind_script()]
    assert cmd[2:] == ["moose", "-x", "-i", "input.i", "--compute-device=xpu"]
    assert env["COMPGEN_DEVICE_OFFSET"] == "3"
    assert env["COMPGEN_VISIBLE_DEVICES_ENV"] == "ZE_AFFINITY_MASK"


def test_build_command_gpu_multi_rank_with_cpu_bind():
    """Each slot gets a block of ranks_per_run devices and the matching CPU cores."""
    cores = [f"{8 * i + 1}-{8 * i + 8}" for i in range(12)]
    settings = _gpu_settings(
        devices_per_node=12,
        ranks_per_run=4,
        cpu_bind=cores,
        visible_devices_env="CUDA_VISIBLE_DEVICES",
        environment={"FOO": "bar"},
    )
    settings["mpi"] = {
        "executable": "mpiexec",
        "rank_command": "-n",
        "ranks": 1,
        "extra_args": ["--no-transfer"],
    }
    cmd, env = moose.build_moose_command(settings, ["-i", "input.i"], slot=1)
    assert cmd[:5] == [
        "mpiexec",
        "-n",
        "4",
        "--no-transfer",
        "--cpu-bind=list:33-40:41-48:49-56:57-64",
    ]
    assert cmd[5:7] == ["bash", moose.gpu_bind_script()]
    assert env["COMPGEN_DEVICE_OFFSET"] == "4"
    assert env["COMPGEN_VISIBLE_DEVICES_ENV"] == "CUDA_VISIBLE_DEVICES"
    assert env["FOO"] == "bar"


def test_build_command_gpu_errors():
    """Device required; slots must fit on the node; multi-rank needs mpi."""
    settings = _gpu_settings(devices_per_node=4, ranks_per_run=2)
    settings["mpi"] = {"executable": "mpiexec", "rank_command": "-n", "ranks": 2}
    moose.build_moose_command(settings, [], slot=1)
    with pytest.raises(ValueError, match="devices_per_node"):
        moose.build_moose_command(settings, [], slot=2)
    del settings["mpi"]
    with pytest.raises(ValueError, match="needs an 'mpi' section"):
        moose.build_moose_command(settings, [], slot=0)
    settings = _gpu_settings()
    del settings["moose"]["device"]
    with pytest.raises(ValueError, match="needs a device"):
        moose.build_moose_command(settings, [])


def test_build_command_slot_from_environment(monkeypatch):
    """Without an explicit slot, the worker's COMPGEN_GPU_SLOT is used."""
    monkeypatch.setenv(moose.GPU_SLOT_ENV, "5")
    _, env = moose.build_moose_command(_gpu_settings(), [])
    assert env["COMPGEN_DEVICE_OFFSET"] == "5"


def test_check_gpu_capacity():
    """nthreads x ranks_per_run must fit in devices_per_node in gpu mode only."""
    settings = _gpu_settings(devices_per_node=12, ranks_per_run=4)
    moose.check_gpu_capacity(settings, 3)
    with pytest.raises(ValueError, match="need 16 devices"):
        moose.check_gpu_capacity(settings, 4)
    settings["moose"]["mode"] = "cpu"
    moose.check_gpu_capacity(settings, 100)


def test_gpu_bind_script_sets_device():
    """The wrapper exposes offset + local rank through the configured variable."""
    env = dict(os.environ) | {
        "PALS_LOCAL_RANKID": "2",
        "COMPGEN_DEVICE_OFFSET": "4",
        "COMPGEN_VISIBLE_DEVICES_ENV": "MY_DEVICE",
    }
    out = subprocess.run(
        ["bash", moose.gpu_bind_script(), "bash", "-c", "echo $MY_DEVICE"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "6"


def test_gpu_mode_runs_gpu_template(monkeypatch, tmp_path):
    """In gpu mode the GPU template is run with the per-load-case substitutions and the device
    flag."""
    seen = []

    def run(cmd, **_kwargs):
        with open("input.i", encoding="utf-8") as f:
            seen.append((cmd, f.read()))

    monkeypatch.setattr(moose, "_run_moose_command", run)
    monkeypatch.setattr(moose, "process_output", lambda *a: {})
    mesh = tmp_path / "mesh.exo"
    mesh.write_text("")
    settings = _gpu_settings()
    settings["storage"] = {"temp_dir": str(tmp_path), "delete_temp_dir": True}
    materials = {"A": {"conductivity": 1.0}, "B": {"conductivity": 2.0}}
    out = moose.execute_moose_simulations(
        "2d/thermal_conductivity", str(mesh), materials, settings=settings
    )
    assert [r["index"] for r in out] == [0, 1]
    for n, (cmd, text) in enumerate(seen):
        assert "KokkosHeatConductionHomogenized" in text
        assert f"gx={int(n == 0)}" in cmd and f"gy={int(n == 1)}" in cmd
        assert "k1=1.0" in cmd and "k2=2.0" in cmd
        assert cmd[-1] == "--compute-device=xpu"
