"""Interfaces for running physics templates and postprocessing outputs."""

import os
import os.path
import json
import shutil
import signal
import subprocess
import logging

import numpy as np
import exodusii

from compgen import temp
from compgen.exoutil import get_element_field
from compgen.tensors import assemble_tensor

logger = logging.getLogger(__name__)


def get_physics(name, settings_name="settings.json", template_name="template.i"):
    """Return the absolute path to the template and the options set for a given physics

    Args:
        name (str): Name of the physics template.  Can include / subdirectories.

    Keyword Args:
        settings_name (str): Name of the settings file within the physics directory.
        template_name (str): Name of the template file within the physics directory.
    """
    base = os.path.join(os.path.dirname(__file__), "physics", name)
    if not os.path.isdir(base):
        raise ValueError(f"Physics '{name}' not found.")

    return os.path.join(base, template_name), json.load(
        open(os.path.join(base, settings_name), "r", encoding="utf-8")
    )


def material_property_substitutions(material_properties, physics_properties):
    """Generate substitutions for material properties.

    Args:
        material_properties (dict): Dictionary defining material properties for materials A and B.
        physics_properties (dict): Dictionary defining physics properties.
    """
    subs = []
    for ind, prop in enumerate(physics_properties["bulk_material_properties"]):
        if prop not in material_properties["A"]:
            raise ValueError(f"Material property '{prop}' not defined for material A.")
        if prop not in material_properties["B"]:
            raise ValueError(f"Material property '{prop}' not defined for material B.")

        subs.append(
            f"{physics_properties['material_A_substitutions'][ind]}="
            f"{material_properties['A'][prop]}"
        )
        subs.append(
            f"{physics_properties['material_B_substitutions'][ind]}="
            f"{material_properties['B'][prop]}"
        )

    for ind, prop in enumerate(
        physics_properties.get("interface_material_properties", [])
    ):
        if prop not in material_properties.get("AB", {}):
            raise ValueError(
                f"Material property '{prop}' not defined for material interface AB."
            )

        subs.append(
            f"{physics_properties['interface_substitutions'][ind]}="
            f"{material_properties['AB'][prop]}"
        )

    return subs


def target_substitutions(
    target,
    number_of_targets,
    target_substitution,
    target_name,
    zero_name,
):
    """Generate substitutions for a given target.

    Args:
        target (int): Target index.
        number_of_targets (int): Total number of targets.
        target_substitution (str): Substitution template for the target.
        target_name (str): Name of the target variable.
        zero_name (str): Name of the zero variable.
    """
    subs = []
    for i in range(number_of_targets):
        if i == target:
            subs.append(target_name)
        else:
            subs.append(zero_name)

    return [f"{target_substitution}='{' '.join(subs)}'"]


def output_subsitutions(target, output_substitution, output_name):
    """Generate substitutions for output variables.

    Args:
        target (int): Target index.
        output_substitution (str): Substitution template for the output.
        output_name (str): Base name for output
    """
    return [f"{output_substitution}={output_name}_{target}"]


def simplify_mesh(mesh):
    """Simplify the mesh file into a simpler format.

    Args:
        mesh (str): Path to the input mesh file.
    """
    with exodusii.File(mesh, mode="r") as exo:
        coords = np.copy(exo.get_coords()[:])
        conn_a = exo.get_element_conn(1)
        conn_b = exo.get_element_conn(2)

    conn = np.concatenate((conn_a, conn_b), axis=0)
    material = np.ones(conn.shape[0], dtype=bool)
    material[len(conn_a) :] = 0  # Material B

    # Screw you 1 indexing
    return {
        "coords": coords,
        "connectivity": conn - 1,
        "element_fields": {
            "material": {
                "type": "scalar",
                "shape": tuple(),
                "data": material[np.newaxis, :],
            }
        },
    }


def append_field_results(mesh, physics, output_exo):
    """Append field results from the MOOSE output to the simplified mesh.

    Args:
        mesh (dict): Simplified mesh dictionary.
        physics (str): Name of the physics template.  Can include / subdirectories.
        output_exo (str): Path to the output Exodus file.
    """
    _, physics_settings = get_physics(physics)

    with exodusii.File(output_exo, mode="r") as exo:
        mesh["element_fields"]["stimuli"] = {}
        for field, info in physics_settings["stimuli_fields"].items():
            mesh["element_fields"]["stimuli"][field] = assemble_tensor(
                info["type"],
                int(info["dim"]),
                [get_element_field(exo, comp) for comp in info["field_components"]],
            )
        mesh["element_fields"]["responses"] = {}
        for field, info in physics_settings["response_fields"].items():
            mesh["element_fields"]["responses"][field] = assemble_tensor(
                info["type"],
                int(info["dim"]),
                [get_element_field(exo, comp) for comp in info["field_components"]],
            )

    return mesh


def generalized_stimuli_and_forces(physics, output_csv):
    """Extract generalized stimuli and forces from the MOOSE output CSV.

    Args:
        physics (str): Name of the physics template.  Can include / subdirectories.
        output_csv (str): Path to the output CSV file.
    """
    _, physics_settings = get_physics(physics)

    data = np.genfromtxt(output_csv, delimiter=",", names=True)

    stimuli = {}
    for field, info in physics_settings["stimuli_fields"].items():
        stimuli[field] = assemble_tensor(
            info["type"],
            int(info["dim"]),
            [data[comp] for comp in info["postprocessor_components"]],
        )

    responses = {}
    for field, info in physics_settings["response_fields"].items():
        responses[field] = assemble_tensor(
            info["type"],
            int(info["dim"]),
            [data[comp] for comp in info["postprocessor_components"]],
        )

    return {"stimuli": stimuli, "responses": responses}


def extract_physics_data(physics):
    """Extract physics data from the physics settings.

    Args:
        physics (str): Name of the physics template.  Can include / subdirectories.
    """
    _, physics_settings = get_physics(physics)
    return {
        "type": physics_settings["type"],
        "name": os.path.basename(physics),
        "dimension": int(os.path.split(physics)[-2][0]),
        "stimuli": physics_settings["stimuli_fields"],
        "responses": physics_settings["response_fields"],
    }


def process_output(physics, mesh, material_properties, output_exo, output_csv):
    """Process the output from a MOOSE simulation into partial (unstructured grid) data.

    Args:
        physics (str): Name of the physics template.  Can include / subdirectories.
        mesh (str): Path to the input mesh file.
        material_properties (dict): Dictionary defining material properties for materials A and B.
        output_exo (str): Path to the output Exodus file.
        output_csv (str): Path to the output CSV file.
    """
    # Convert the exodus output to a simpler unstructured mesh format
    simple_mesh = simplify_mesh(mesh)
    simple_mesh = append_field_results(simple_mesh, physics, output_exo)

    # Extract generalized stimuli and forces from the CSV output
    output_csv_data = generalized_stimuli_and_forces(physics, output_csv)

    return {
        "physics": extract_physics_data(physics),
        "unstructured_mesh": simple_mesh,
        "generalized": output_csv_data,
        "material_properties": material_properties,
    }


def _run_moose_command(cmd, env, capture, timeout_s):
    """Run a single MOOSE command, killing the whole process tree on timeout.

    ``subprocess.run(timeout=...)`` only kills the direct child (e.g. ``mpirun``);
    the MPI ranks it spawned would be orphaned and keep running. Launching the
    command in its own session and killing the process group on timeout tears the
    whole tree down (mpirun -> hydra_pmi_proxy -> solid_mechanics ranks).

    Args:
        cmd (list[str]): Command and arguments.
        env (dict): Environment for the subprocess.
        capture (bool): Capture stdout/stderr instead of inheriting them.
        timeout_s (float | None): Wall-clock limit in seconds; ``None`` disables it.

    Raises:
        subprocess.TimeoutExpired: The command exceeded ``timeout_s`` (tree killed).
        subprocess.CalledProcessError: The command exited with a non-zero code.
    """
    pipe = subprocess.PIPE if capture else None
    with subprocess.Popen(
        cmd, env=env, stdout=pipe, stderr=pipe, start_new_session=True
    ) as proc:
        try:
            out, err = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            # Kill the entire process group (mpirun + hydra_pmi_proxy + ranks).
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()  # reap the killed tree
            raise
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, cmd, output=out, stderr=err
            )


def execute_moose_simulations(
    physics,
    mesh,
    material_properties,
    settings=None,
    output_name="output",
    problem_id=None,
):
    """
    Execute the MOOSE simulations for a given physics template and mesh.

    Args:
        physics (str): Name of the physics template.  Can include / subdirectories.
        mesh (str): Path to the input mesh file.
        material_properties (dict): Dictionary defining material properties for materials A and B.

    Keyword Args:
        settings (dict): Global settings dict
        output_name (str): Base name for output files
        problem_id (str): Problem UUID, used only to tag per-load-case log messages
            so failures/timeouts are greppable by problem.
    """
    if settings is None:
        settings = {}

    template_input, physics_settings = get_physics(physics)

    # Temp storage
    with temp.TempDirectory(settings) as (cwd, tmpdir):
        # Need the mesh and the template
        shutil.copy(os.path.join(cwd, mesh), os.path.join(tmpdir, "mesh.exo"))
        shutil.copy(os.path.join(cwd, template_input), os.path.join(tmpdir, "input.i"))

        # Form the substitutions for material properties
        mat_subs = material_property_substitutions(
            material_properties,
            physics_settings["material_properties"],
        )

        outputs = []

        sub_type = physics_settings.get("substitution_mode", "iterative")
        if sub_type == "dictlist":
            sub_dict = physics_settings["substitution_dictionary"]
            # Check that all values in the dictionary have the same length
            lengths = [len(v) for v in sub_dict.values()]
            if len(set(lengths)) != 1:
                raise ValueError(
                    "All values in the substitution dictionary must have the same length."
                )
            N = lengths[0]
        elif sub_type == "iterative":
            N = int(physics_settings["number_of_targets"])
        else:
            raise ValueError(f"Unknown substitution mode '{sub_type}'.")

        # Per-load-case wall-clock limit. The config value is in MINUTES; an
        # absent value or any value <= 0 means no timeout.
        timeout_min = settings.get("moose", {}).get("timeout")
        timeout_s = timeout_min * 60 if timeout_min and timeout_min > 0 else None

        for target in range(N):
            if sub_type == "dictlist":
                target_subs = [f"{key}={sub_dict[key][target]}" for key in sub_dict]
            elif sub_type == "iterative":
                target_subs = target_substitutions(
                    target,
                    physics_settings["number_of_targets"],
                    physics_settings["target_substitution"],
                    physics_settings["target_name"],
                    physics_settings["zero_name"],
                )
            else:
                raise ValueError(f"Unknown substitution mode '{sub_type}'.")
            output_subs = output_subsitutions(
                target,
                physics_settings["output_substitution"],
                output_name,
            )
            cmd = (
                [settings["moose"]["executable"]]
                + settings["moose"]["options"]
                + ["-i", "input.i"]
                + mat_subs
                + target_subs
                + output_subs
            )
            if "mpi" in settings:
                cmd = (
                    [settings["mpi"]["executable"]]
                    + [settings["mpi"]["rank_command"], str(settings["mpi"]["ranks"])]
                    + settings["mpi"].get("extra_args", [])
                    + cmd
                )

            try:
                _run_moose_command(
                    cmd,
                    env=settings["moose"].get("environment", {}) | os.environ,
                    capture=(not settings.get("verbose", False)),
                    timeout_s=timeout_s,
                )
            except subprocess.TimeoutExpired:
                # The solve exceeded the configured wall-clock limit (typically a
                # solve stuck in time-step cutback).  The whole process tree has
                # been killed; skip this load case and continue with the next.
                logger.warning(
                    "Problem %s: Load case %d of physics '%s' exceeded the "
                    "%g-minute timeout; killed it and skipping this load and "
                    "continuing.",
                    problem_id,
                    target,
                    physics,
                    timeout_min,
                )
                continue
            except subprocess.CalledProcessError as e:
                # A non-converged (or otherwise failed) MOOSE solve aborts with a
                # non-zero exit code.  Skip just this load case and continue with
                # the next one, keeping the loads that already succeeded.
                logger.warning(
                    "Problem %s: Load case %d of physics '%s' did not converge "
                    "(exit code %s); skipping this load and continuing.",
                    problem_id,
                    target,
                    physics,
                    e.returncode,
                )
                continue

            result = process_output(
                physics,
                mesh,
                material_properties,
                f"{output_name}_{target}.e",
                f"{output_name}_{target}.csv",
            )
            # Tag the result with its load index (and load values when available)
            # so downstream output keeps a 1-to-1 index <-> load correspondence
            # even when some load cases are skipped.
            result["index"] = target
            if sub_type == "dictlist":
                result["loads"] = {key: sub_dict[key][target] for key in sub_dict}
            outputs.append(result)

    if not outputs:
        raise RuntimeError(
            f"All {N} load cases failed to converge for physics '{physics}'."
        )

    return outputs
