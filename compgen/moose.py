import os
import os.path
import json
import tempfile
import shutil
import subprocess

import numpy as np
import exodusii

from compgen.exoutil import get_element_field
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
    for prop in physics_properties["bulk_material_properties"]:
        if prop not in material_properties["A"]:
            raise ValueError(f"Material property '{prop}' not defined for material A.")
        if prop not in material_properties["B"]:
            raise ValueError(f"Material property '{prop}' not defined for material B.")

        ind = physics_properties["bulk_material_properties"].index(prop)

        subs.append(
            f"{physics_properties['material_A_substitutions'][ind]}={material_properties['A'][prop]}"
        )
        subs.append(
            f"{physics_properties['material_B_substitutions'][ind]}={material_properties['B'][prop]}"
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
    cwd = os.getcwd()
    tmpdir = tempfile.mkdtemp()
    print(tmpdir)

    # Need the mesh and the template
    shutil.copy(mesh, os.path.join(tmpdir, "mesh.exo"))
    shutil.copy(template_input, os.path.join(tmpdir, "input.i"))

    os.chdir(tmpdir)

    # Form the substitutions for material properties
    mat_subs = material_property_substitutions(
        material_properties,
        physics_settings["material_properties"],
    )

    outputs = []

    for target in range(int(physics_settings["number_of_targets"])):
        target_subs = target_substitutions(
            target,
            physics_settings["number_of_targets"],
            physics_settings["target_substitution"],
            physics_settings["target_name"],
            physics_settings["zero_name"],
        )
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

        subprocess.run(
            cmd,
            check=True,
            env=settings["moose"].get("environment", {}) | os.environ,
            capture_output=True,
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

    os.chdir(cwd)

    return outputs
