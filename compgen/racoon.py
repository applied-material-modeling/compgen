import os
import shutil
import subprocess

import numpy as np

from compgen import temp
from compgen.moose import (
    get_physics,
    material_property_substitutions,
    target_substitutions,
    output_subsitutions,
    process_output
)


def generate_cracks(ncrack, lb, ub, L_avg, L_cov):
    L = np.random.normal(L_avg, L_cov * L_avg, ncrack)
    xc = np.random.uniform(lb, ub, (ncrack, 2))
    q = np.random.uniform(0, 2 * np.pi, ncrack)
    x1 = xc + 0.5 * L[:, np.newaxis] * np.column_stack((np.cos(q), np.sin(q)))
    x2 = xc - 0.5 * L[:, np.newaxis] * np.column_stack((np.cos(q), np.sin(q)))
    
    def clip_segment_to_box(p0, p1, lb, ub, eps=1e-12):
        d = p1 - p0
        t0 = 0.0
        t1 = 1.0
        for axis in range(2):
            if abs(d[axis]) < eps:
                if p0[axis] < lb or p0[axis] > ub:
                    return None
                continue
            inv_da = 1.0 / d[axis]
            t_enter = (lb - p0[axis]) * inv_da
            t_exit = (ub - p0[axis]) * inv_da
            if t_enter > t_exit:
                t_enter, t_exit = t_exit, t_enter
            t0 = max(t0, t_enter)
            t1 = min(t1, t_exit)
            if t0 > t1 + eps:
                return None
        q0 = p0 + t0 * d
        q1 = p0 + t1 * d
        return q0, q1

    def periodic_split_segment(p0, p1, lb, ub, eps=1e-10):
        w = ub - lb
        seg_min_x = min(p0[0], p1[0])
        seg_max_x = max(p0[0], p1[0])
        seg_min_y = min(p0[1], p1[1])
        seg_max_y = max(p0[1], p1[1])
        kx_min = int(np.ceil((lb - seg_max_x) / w))
        kx_max = int(np.floor((ub - seg_min_x) / w))
        ky_min = int(np.ceil((lb - seg_max_y) / w))
        ky_max = int(np.floor((ub - seg_min_y) / w))
        pieces = []
        for kx in range(kx_min, kx_max + 1):
            for ky in range(ky_min, ky_max + 1):
                shift = np.array([kx * w, ky * w])
                clipped = clip_segment_to_box(p0 + shift, p1 + shift, lb, ub)
                if clipped is None:
                    continue
                a, b = clipped
                if np.linalg.norm(b - a) <= eps:
                    continue
                pieces.append((a, b))
        unique = []
        for a, b in pieces:
            found = False
            for ua, ub_ in unique:
                same_dir = np.allclose(a, ua, atol=eps) and np.allclose(b, ub_, atol=eps)
                opp_dir = np.allclose(a, ub_, atol=eps) and np.allclose(b, ua, atol=eps)
                if same_dir or opp_dir:
                    found = True
                    break
            if not found:
                unique.append((a, b))
        return unique

    segments = []
    for i in range(ncrack):
        segments.extend(periodic_split_segment(x1[i], x2[i], lb, ub))
    
    x1_periodic = np.array([s[0] for s in segments])
    x2_periodic = np.array([s[1] for s in segments])
    z = np.zeros(len(segments))
    
    return {
        "x1": " ".join(f"{v:.8f}" for v in x1_periodic[:, 0]),
        "y1": " ".join(f"{v:.8f}" for v in x1_periodic[:, 1]),
        "x2": " ".join(f"{v:.8f}" for v in x2_periodic[:, 0]),
        "y2": " ".join(f"{v:.8f}" for v in x2_periodic[:, 1]),
        "z1": " ".join(f"{v:.8f}" for v in z),
        "z2": " ".join(f"{v:.8f}" for v in z)
    }

def inject_cracks(fracture_file_path, cracks_data):
    with open(fracture_file_path, "r") as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if "x1 =" in line:
            lines[i] = f"      x1 = '{cracks_data['x1']}'\n"
        elif "y1 =" in line:
            lines[i] = f"      y1 = '{cracks_data['y1']}'\n"
        elif "x2 =" in line:
            lines[i] = f"      x2 = '{cracks_data['x2']}'\n"
        elif "y2 =" in line:
            lines[i] = f"      y2 = '{cracks_data['y2']}'\n"
        elif "z1 =" in line:
            lines[i] = f"      z1 = '{cracks_data['z1']}'\n"
        elif "z2 =" in line:
            lines[i] = f"      z2 = '{cracks_data['z2']}'\n"
            
    with open(fracture_file_path, "w") as f:
        f.writelines(lines)


def execute_racoon_simulations(
    physics, mesh, material_properties, settings={}, output_name="output"
):
    """
    Execute the RACOON simulations for a given physics template and mesh.
    """
    template_input, physics_settings = get_physics(physics)
    
    with temp.TempDirectory(settings) as (cwd, tmpdir):
        shutil.copy(os.path.join(cwd, mesh), os.path.join(tmpdir, "mesh.exo"))
        shutil.copy(os.path.join(cwd, template_input), os.path.join(tmpdir, "input.i"))
        
        physics_dir = os.path.dirname(template_input)
        
        aux_files = physics_settings.get("auxiliary_files", [])
        for aux_file in aux_files:
            aux_src = os.path.join(cwd, physics_dir, aux_file)
            shutil.copy(aux_src, os.path.join(tmpdir, aux_file))
            
            if aux_file == "fracture.i":
                ncrack = settings.get("fracture", {}).get("ncrack", 8)
                L_avg = settings.get("fracture", {}).get("L_avg", 0.1)
                L_cov = settings.get("fracture", {}).get("L_cov", 0.3)
                
                L_val = settings.get("L", [1.0, 1.0])[0]
                cracks_data = generate_cracks(ncrack, 0, L_val, L_avg, L_cov)
                inject_cracks(os.path.join(tmpdir, aux_file), cracks_data)

        mat_subs = material_property_substitutions(
            material_properties,
            physics_settings["material_properties"],
        )

        outputs = []

        sub_type = physics_settings.get("substitution_mode", "iterative")
        if sub_type == "dictlist":
            sub_dict = physics_settings.get("substitution_dictionary", {})
            if sub_dict:
                lengths = [len(v) for v in sub_dict.values()]
                if len(set(lengths)) != 1:
                    raise ValueError("All values in the substitution dictionary must have the same length.")
                N = lengths[0]
            else:
                N = 1
        elif sub_type == "iterative":
            N = int(physics_settings.get("number_of_targets", 1))
        else:
            raise ValueError(f"Unknown substitution mode '{sub_type}'.")

        for target in range(N):
            target_subs = []
            if sub_type == "dictlist":
                if sub_dict:
                    target_subs = [f"{key}={sub_dict[key][target]}" for key in sub_dict]
            elif sub_type == "iterative":
                target_sub_string = physics_settings.get("target_substitution", "")
                if target_sub_string and target_sub_string != "":
                    target_subs = target_substitutions(
                        target,
                        physics_settings["number_of_targets"],
                        target_sub_string,
                        physics_settings["target_name"],
                        physics_settings["zero_name"],
                    )
            
            output_subs = output_subsitutions(
                target,
                physics_settings["output_substitution"],
                output_name,
            )
            
            cmd = (
                [settings["racoon"]["executable"]]
                + settings.get("racoon", {}).get("options", [])
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

            subprocess.run(
                cmd,
                check=True,
                env=settings.get("racoon", {}).get("environment", {}) | os.environ,
                capture_output=False,
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
