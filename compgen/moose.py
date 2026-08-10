import os
import os.path
import json
import shutil
import subprocess

import numpy as np
import exodusii

from compgen import temp
from compgen.exoutil import get_element_field, get_node_field_aligned
from compgen.tensors import assemble_tensor


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
        open(os.path.join(base, settings_name))
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
            f"{physics_properties['material_A_substitutions'][ind]}={material_properties['A'][prop]}"
        )
        subs.append(
            f"{physics_properties['material_B_substitutions'][ind]}={material_properties['B'][prop]}"
        )

    for ind, prop in enumerate(
        physics_properties.get("interface_material_properties", [])
    ):
        if prop not in material_properties.get("AB", {}):
            raise ValueError(
                f"Material property '{prop}' not defined for material interface AB."
            )

        subs.append(
            f"{physics_properties['interface_substitutions'][ind]}={material_properties['AB'][prop]}"
        )

    return subs


def target_substitutions(
    target, number_of_targets, target_substitution, target_name, zero_name
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

    def append_fields(target_group, fields, getter):
        for field, info in fields.items():
            target_group[field] = assemble_tensor(
                info["type"],
                int(info["dim"]),
                [getter(comp) for comp in info["field_components"]],
            )

    with exodusii.File(output_exo, mode="r") as exo:
        mesh["element_fields"]["stimuli"] = {}
        mesh["element_fields"]["responses"] = {}
        mesh["node_fields"] = {"stimuli": {}, "responses": {}}

        for category, settings_key in (
            ("stimuli", "stimuli_fields"),
            ("responses", "response_fields"),
        ):
            field_info = physics_settings[settings_key]
            element_fields = {
                field: info
                for field, info in field_info.items()
                if info.get("location", "element") == "element"
            }
            node_fields = {
                field: info
                for field, info in field_info.items()
                if info.get("location") == "node"
            }
            append_fields(
                mesh["element_fields"][category],
                element_fields,
                lambda comp: get_element_field(exo, comp),
            )
            append_fields(
                mesh["node_fields"][category],
                node_fields,
                lambda comp: get_node_field_aligned(output_exo, comp, mesh["coords"]),
            )

        if not mesh["node_fields"]["stimuli"] and not mesh["node_fields"]["responses"]:
            del mesh["node_fields"]

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
        if "postprocessor_components" in info:
            stimuli[field] = assemble_tensor(
                info["type"],
                int(info["dim"]),
                [data[comp] for comp in info["postprocessor_components"]],
            )

    responses = {}
    for field, info in physics_settings["response_fields"].items():
        if "postprocessor_components" in info:
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


def get_simulation_times(output_exo):
    """Read the physical simulation time associated with each Exodus frame."""
    with exodusii.File(output_exo, mode="r") as exo:
        times = np.asarray(exo.get_times(), dtype=np.float64)

    if times.ndim != 1:
        raise ValueError(
            f"Expected a one-dimensional time vector in '{output_exo}', "
            f"but found shape {times.shape}."
        )
    if times.size == 0:
        raise ValueError(f"No simulation times were found in '{output_exo}'.")
    if not np.all(np.isfinite(times)):
        raise ValueError(f"Non-finite simulation times were found in '{output_exo}'.")
    if np.any(np.diff(times) < 0):
        raise ValueError(
            f"Simulation times are not monotonically increasing in '{output_exo}'."
        )

    return np.copy(times)


def validate_time_alignment(data, times):
    """Verify that every transient tensor has one frame per saved time value."""
    times = np.asarray(times)
    constant_fields = {"material", "material_reprojected"}

    def visit(value, path=()):
        if not isinstance(value, dict):
            return

        if {"type", "shape", "data"}.issubset(value):
            tensor_data = np.asarray(value["data"])
            field_name = path[-1] if path else "<root>"
            allowed_frame_counts = {len(times)}
            if field_name in constant_fields:
                allowed_frame_counts.add(1)

            if (
                tensor_data.ndim == 0
                or tensor_data.shape[0] not in allowed_frame_counts
            ):
                location = "/".join(path)
                raise ValueError(
                    f"Time alignment error for '{location}': field shape "
                    f"{tensor_data.shape} does not match {len(times)} saved times."
                )

        for key, child in value.items():
            visit(child, path + (key,))

    visit(data)


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

    result = {
        "physics": extract_physics_data(physics),
        "time": get_simulation_times(output_exo),
        "unstructured_mesh": simple_mesh,
        "generalized": output_csv_data,
        "material_properties": material_properties,
    }
    validate_time_alignment(result, result["time"])
    return result


def execute_moose_simulations(
    physics, mesh, material_properties, settings={}, output_name="output"
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
    """
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

            # Build environment with JIT compiler configuration
            run_env = dict(os.environ)

            # Add MOOSE-specific environment from config
            run_env.update(settings["moose"].get("environment", {}))

            # Ensure libMesh JIT compiler is configured for HPC systems
            # This fixes "cmath not found" errors when using cray-mpich
            if "CONDA_PREFIX" in run_env and "LIBMESH_CXX" not in run_env:
                conda_prefix = run_env["CONDA_PREFIX"]
                run_env["LIBMESH_CXX"] = f"{conda_prefix}/bin/g++"

                # Get GCC version dynamically
                try:
                    gcc_version = subprocess.check_output(
                        [f"{conda_prefix}/bin/g++", "-dumpversion"], text=True
                    ).strip()
                    cxx_include = f"{conda_prefix}/lib/gcc/x86_64-conda-linux-gnu/{gcc_version}/include/c++"
                    run_env["LIBMESH_CXXFLAGS"] = (
                        f"-I{cxx_include} "
                        f"-I{conda_prefix}/x86_64-conda-linux-gnu/sysroot/usr/include "
                        f"-L{conda_prefix}/lib "
                        f"-Wl,-rpath,{conda_prefix}/lib"
                    )
                except Exception:
                    pass  # If we can't get GCC version, hope the env vars were set externally

            subprocess.run(
                cmd,
                check=True,
                env=run_env,
                capture_output=(not settings.get("verbose", False)),
            )

            outputs.append(
                process_output(
                    physics,
                    mesh,
                    material_properties,
                    f"{output_name}_{target}.e",
                    f"{output_name}_{target}.csv",
                )
            )

    return outputs
