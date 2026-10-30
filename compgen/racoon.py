import os
import shutil
import subprocess
import sys
import socket
import logging
import shlex
from pathlib import Path

import numpy as np

from compgen import temp

# Module loaded - debug marker
sys.stderr.write("[DEBUG] racoon.py module loaded\n")
sys.stderr.flush()
from compgen.moose import (
    get_physics,
    material_property_substitutions,
    target_substitutions,
    output_subsitutions,
    process_output
)

def generate_cracks(ncrack, lb, ub, L_avg, L_cov, dimensions=2):
    """Generate periodic line cracks in a 2D or 3D box.

    The 2D path retains the original in-plane angle generation. In 3D,
    uniformly distributed directions on the sphere are used and the same
    periodic clipping logic is applied in all coordinate directions.
    """
    L = np.random.normal(L_avg, L_cov * L_avg, ncrack)
    if dimensions not in (2, 3):
        raise ValueError("Crack generation supports only 2D and 3D boxes.")
    lower = np.broadcast_to(np.asarray(lb, dtype=float), (dimensions,))
    upper = np.broadcast_to(np.asarray(ub, dtype=float), (dimensions,))
    if np.any(upper <= lower):
        raise ValueError("Crack-generation upper bounds must exceed lower bounds.")
    xc = np.random.uniform(lower, upper, (ncrack, dimensions))
    if dimensions == 2:
        q = np.random.uniform(0, 2 * np.pi, ncrack)
        directions = np.column_stack((np.cos(q), np.sin(q)))
    else:
        directions = np.random.normal(size=(ncrack, 3))
        directions /= np.linalg.norm(directions, axis=1)[:, np.newaxis]
    x1 = xc + 0.5 * L[:, np.newaxis] * directions
    x2 = xc - 0.5 * L[:, np.newaxis] * directions
    
    def clip_segment_to_box(p0, p1, lb, ub, eps=1e-12):
        d = p1 - p0
        t0 = 0.0
        t1 = 1.0
        for axis in range(dimensions):
            if abs(d[axis]) < eps:
                if p0[axis] < lower[axis] or p0[axis] > upper[axis]:
                    return None
                continue
            inv_da = 1.0 / d[axis]
            t_enter = (lower[axis] - p0[axis]) * inv_da
            t_exit = (upper[axis] - p0[axis]) * inv_da
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
        widths = upper - lower
        pieces = []
        ranges = [
            range(
                int(np.ceil((lower[i] - max(p0[i], p1[i])) / widths[i])),
                int(np.floor((upper[i] - min(p0[i], p1[i])) / widths[i])) + 1,
            )
            for i in range(dimensions)
        ]
        for offsets in np.ndindex(*(len(r) for r in ranges)):
            shifts = [ranges[i][offsets[i]] for i in range(dimensions)]
            shift = np.asarray(shifts, dtype=float) * widths
            clipped = clip_segment_to_box(p0 + shift, p1 + shift, lower, upper)
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
    if not segments:
        empty = ""
        return {key: empty for key in ("x1", "y1", "z1", "x2", "y2", "z2")}

    values = {
        "x1": x1_periodic[:, 0],
        "y1": x1_periodic[:, 1],
        "x2": x2_periodic[:, 0],
        "y2": x2_periodic[:, 1],
        "z1": x1_periodic[:, 2] if dimensions == 3 else np.zeros(len(segments)),
        "z2": x2_periodic[:, 2] if dimensions == 3 else np.zeros(len(segments)),
    }
    
    return {
        key: " ".join(f"{v:.8f}" for v in component)
        for key, component in values.items()
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
        
        logger = logging.getLogger(__name__)
        logger.debug("RACCOON temp directory: %s", tmpdir)

        physics_dir = os.path.dirname(template_input)
        
        aux_files = physics_settings.get("auxiliary_files", [])
        for aux_file in aux_files:
            aux_src = os.path.join(cwd, physics_dir, aux_file)
            shutil.copy(aux_src, os.path.join(tmpdir, aux_file))
            
            if aux_file == "fracture.i":
                ncrack = settings.get("fracture", {}).get("ncrack", 8)
                L_avg = settings.get("fracture", {}).get("L_avg", 0.1)
                L_cov = settings.get("fracture", {}).get("L_cov", 0.3)
                
                domain = settings.get("L", [1.0, 1.0])
                dimensions = len(domain)
                if dimensions not in (2, 3):
                    raise ValueError("Fracture domain must have 2 or 3 dimensions.")
                cracks_data = generate_cracks(
                    ncrack,
                    0,
                    domain[0] if dimensions == 2 else np.asarray(domain),
                    L_avg,
                    L_cov,
                    dimensions=dimensions,
                )
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
                    + ( # Option to isolate host to hostname. 
                        [settings["mpi"].get("host_command", "--host"), socket.gethostname()]
                        if settings["mpi"].get("isolate_host", False)
                        else []
                    ) # Option to isolate host
                    + settings["mpi"].get("extra_args", [])
                    + cmd
                )

            # Build environment with JIT compiler configuration
            run_env = dict(os.environ)

            # Add RACCOON-specific environment from config
            run_env.update(settings.get("racoon", {}).get("environment", {}))

            ### Logging
            # Do a quick test to make sure we know what host we are running on. 
            if "mpi" in settings:
                mpi = settings["mpi"]
                mpi_probe_cmd = (
                    [
                        mpi["executable"],
                        mpi.get("host_command", "--host"),
                        socket.gethostname(),
                        mpi["rank_command"],
                        "2",
                    ]
                    + mpi.get("extra_args", [])
                    + [
                        "sh",
                        "-c",
                        'echo "hostname is: $(hostname)"',
                    ]
                )

                logger.debug("MPI hostname probe command: %s", shlex.join(mpi_probe_cmd))
                logger.debug(
                    "MPI hostname probe output:\n%s",
                    subprocess.run(
                        mpi_probe_cmd,
                        env=run_env,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        check=False,
                    ).stdout.strip()
                )

            logger.info("Executing command: %s", shlex.join(cmd))

            # # Debug: write the actual command to a file in shared storage
            # # debug_file = "/lustre/roscratch1/rghill/AlSiC_2/compgen/demos/raccoon_debug_cmd.txt"
            # debug_file = "./raccoon_debug_cmd.txt"
            # with open(debug_file, "a") as f:
            #     f.write(f"\n[DEBUG] Executing command: {' '.join(cmd)}\n")
            #     f.write(f"[DEBUG] CWD: {os.getcwd()}\n")
            #     f.write(f"[DEBUG] MPI in settings: {'mpi' in settings}\n")
            #     if "mpi" in settings:
            #         f.write(f"[DEBUG] MPI config: {settings['mpi']}\n")
            #     f.write("\n")
            ### Done with extra logging. 

            # Ensure libMesh JIT compiler is configured for HPC systems
            # This fixes "cmath not found" errors when using cray-mpich
            if "CONDA_PREFIX" in run_env:
                conda_prefix = run_env["CONDA_PREFIX"]

                # RACCOON's embedded FParser JIT compiler command is mpicxx.
                # Ensure the matching conda MPI wrapper is discoverable even
                # when the parent Python process was not started from an
                # activated conda environment.
                conda_bin = f"{conda_prefix}/bin"
                existing_path = run_env.get("PATH")
                run_env["PATH"] = (
                    conda_bin
                    if not existing_path
                    else f"{conda_bin}:{existing_path}"
                )

                # The FParser JIT loader dlopens a temporary object at runtime.
                # Keep the matching conda MOOSE/libMesh libraries discoverable by
                # that loader, in addition to the executable's own RPATH.
                conda_lib = f"{conda_prefix}/lib"
                existing_ld_library_path = run_env.get("LD_LIBRARY_PATH")
                run_env["LD_LIBRARY_PATH"] = (
                    conda_lib
                    if not existing_ld_library_path
                    else f"{conda_lib}:{existing_ld_library_path}"
                )

                # Always set these, even if they exist (override)
                run_env["LIBMESH_CXX"] = f"{conda_prefix}/bin/g++"

                # Get GCC version dynamically
                try:
                    gcc_version = subprocess.check_output(
                        [f"{conda_prefix}/bin/g++", "-dumpversion"],
                        text=True
                    ).strip()
                    cxx_include = f"{conda_prefix}/lib/gcc/x86_64-conda-linux-gnu/{gcc_version}/include/c++"
                    run_env["LIBMESH_CXXFLAGS"] = (
                        f"-I{cxx_include} "
                        f"-I{conda_prefix}/x86_64-conda-linux-gnu/sysroot/usr/include "
                        f"-L{conda_prefix}/lib "
                        f"-Wl,-rpath,{conda_prefix}/lib"
                    )

                    # Debug output
                    print(f"[JIT Config] CONDA_PREFIX: {conda_prefix}")
                    print(f"[JIT Config] GCC version: {gcc_version}")
                    print(f"[JIT Config] LIBMESH_CXX: {run_env['LIBMESH_CXX']}")
                    print(f"[JIT Config] LIBMESH_CXXFLAGS: {run_env['LIBMESH_CXXFLAGS']}")
                except Exception as e:
                    print(f"[JIT Config] WARNING: Failed to configure JIT: {e}")
                    # Fallback to hardcoded GCC 14.3.0 paths
                    gcc_version = "14.3.0"
                    cxx_include = f"{conda_prefix}/lib/gcc/x86_64-conda-linux-gnu/{gcc_version}/include/c++"
                    run_env["LIBMESH_CXXFLAGS"] = (
                        f"-I{cxx_include} "
                        f"-I{conda_prefix}/x86_64-conda-linux-gnu/sysroot/usr/include "
                        f"-L{conda_prefix}/lib "
                        f"-Wl,-rpath,{conda_prefix}/lib"
                    )
                    print(f"[JIT Config] Using fallback GCC {gcc_version}")
            else:
                print("[JIT Config] WARNING: CONDA_PREFIX not found in environment!")

            discard_raccoon_text = settings.get("racoon", {}).get(
                "discard_raccoon_text", False
            )
            if not isinstance(discard_raccoon_text, bool):
                raise TypeError("racoon.discard_raccoon_text must be a boolean")

            raccoon_log_file = None
            if not discard_raccoon_text:
                raccoon_log_path = settings.get("racoon", {}).get(
                    "raccoon_log_file"
                )
                if raccoon_log_path is None and settings.get("log_file"):
                    # Keep Raccoon output beside the Compgen log by default.
                    # runner.py adds the hostname to the Python log filename;
                    # do the same here so multiple hosts do not share a file.
                    log_path = Path(settings["log_file"])
                    raccoon_log_path = log_path.with_name(
                        f"raccoon_{log_path.stem}_{socket.gethostname()}"
                        f"{log_path.suffix}"
                    )
                elif raccoon_log_path is not None:
                    log_path = Path(raccoon_log_path)
                    raccoon_log_path = log_path.with_name(
                        f"{log_path.stem}_{socket.gethostname()}"
                        f"{log_path.suffix}"
                    )

                if raccoon_log_path is None:
                    raise ValueError(
                        "A log_file or racoon.raccoon_log_file is required "
                        "when racoon.discard_raccoon_text is false"
                    )

                raccoon_log_path = Path(raccoon_log_path)
                raccoon_log_path.parent.mkdir(parents=True, exist_ok=True)
                raccoon_log_file = open(raccoon_log_path, "a", encoding="utf-8")

            try:
                if discard_raccoon_text:
                    subprocess.run(
                        cmd,
                        check=True,
                        env=run_env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        timeout=86400,  # 24 hours. TODO this is hard coded and mostly for testing. Kill job if it's going poorly and running for ages.
                    )
                else:
                    with raccoon_log_file:
                        subprocess.run(
                            cmd,
                            check=True,
                            env=run_env,
                            stdout=raccoon_log_file,
                            stderr=subprocess.STDOUT,
                            text=True,
                            timeout=86400,  # 24 hours. TODO this is hard coded and mostly for testing. Kill job if it's going poorly and running for ages.
                        )
            except subprocess.CalledProcessError as error:
                logger.error(
                    "RACCOON command failed with exit code %s: %s",
                    error.returncode,
                    shlex.join(cmd),
                )
                raise
            except subprocess.TimeoutExpired:  
                logger.error("Job exceeded 24 hours and was killed.")
                logger.error("Command was: %s", ' '.join(cmd))
                raise

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
