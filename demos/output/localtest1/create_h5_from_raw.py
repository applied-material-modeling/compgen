#!/usr/bin/env python3
"""
create_h5_from_raw.py

Fast generation of MOOSE/compgen compliant HDF5 results from raw simulation files.
Bypasses the slow PyVista coordinate matching bottleneck in `exoutil.py` by using
direct NetCDF4 vectorized coordinate alignment, completing in seconds rather than hours.

Outputs:
  - <output_prefix>.h5 (frame-sampled, e.g. 20 frames)
  - <output_prefix>_all_frames.h5 (all simulation frames, if requested)
"""

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import sys
import time

import netCDF4
import numpy as np

# Ensure compgen package is importable
repo_root = Path(__file__).resolve().parents[3]  # compgen-fracture/compgen
sys.path.insert(0, str(repo_root))

from compgen import frame_sampling, generalized, hdfwriter, runner
from compgen.moose import extract_physics_data, simplify_mesh


def decode_nc_names(var):
    """Decode fixed-width char arrays into a list of strings."""
    names = []
    for row in var[:]:
        if hasattr(row, "tobytes"):
            raw_str = row.tobytes().decode("utf-8", errors="ignore")
        else:
            raw_str = "".join(
                c.decode("utf-8", errors="ignore") if isinstance(c, bytes) else c
                for c in row
            )
        names.append(raw_str.split("\x00")[0].strip())
    return names


def build_node_alignment_map(mesh_exo_path, output_exo_path, decimals=8):
    """
    Build a vectorized index mapping from output_exo nodes to reference mesh nodes.
    
    Split interface nodes (created by cohesive zone breaking) are mapped such that
    the primary node index and secondary split node indices are identified once,
    allowing np.maximum resolution to be applied in a single vectorized NumPy operation.
    """
    with netCDF4.Dataset(mesh_exo_path, "r") as m_ds, netCDF4.Dataset(
        output_exo_path, "r"
    ) as o_ds:
        m_x = m_ds.variables["coordx"][:]
        m_y = m_ds.variables["coordy"][:]
        o_x = o_ds.variables["coordx"][:]
        o_y = o_ds.variables["coordy"][:]

    o_map = defaultdict(list)
    for idx, (x, y) in enumerate(zip(o_x, o_y)):
        key = (round(float(x), decimals), round(float(y), decimals))
        o_map[key].append(idx)

    num_mesh_nodes = len(m_x)
    primary_indices = np.empty(num_mesh_nodes, dtype=np.int32)
    split_mesh_indices = []
    split_output_indices = []

    for i, (x, y) in enumerate(zip(m_x, m_y)):
        key = (round(float(x), decimals), round(float(y), decimals))
        idxs = o_map.get(key)
        if not idxs:
            raise KeyError(f"Mesh node {i} at ({x}, {y}) was not found in output Exodus file.")
        primary_indices[i] = idxs[0]
        if len(idxs) > 1:
            split_mesh_indices.append(i)
            split_output_indices.append(idxs[1])

    return (
        primary_indices,
        np.array(split_mesh_indices, dtype=np.int32),
        np.array(split_output_indices, dtype=np.int32),
    )


def extract_raw_fields_fast(mesh_exo_path, output_exo_path, decimals=8):
    """
    Extract time array, element fields, and aligned node fields directly using netCDF4.
    """
    print(f"[*] Reading mesh topology from '{mesh_exo_path}'...")
    mesh_dict = simplify_mesh(mesh_exo_path)

    print(f"[*] Building node alignment mapping from '{output_exo_path}'...")
    t0 = time.time()
    primary_idx, split_mesh_idx, split_out_idx = build_node_alignment_map(
        mesh_exo_path, output_exo_path, decimals=decimals
    )
    print(
        f"    -> Mapped {len(primary_idx)} reference nodes ({len(split_mesh_idx)} split interface nodes) in {time.time() - t0:.2f}s"
    )

    print(f"[*] Extracting transient fields from '{output_exo_path}'...")
    t0 = time.time()
    with netCDF4.Dataset(output_exo_path, "r") as ds:
        times = np.asarray(ds.variables["time_whole"][:], dtype=np.float64)
        node_vars = decode_nc_names(ds.variables["name_nod_var"])
        elem_vars = decode_nc_names(ds.variables["name_elem_var"])

        def get_elem_var(var_name):
            idx = elem_vars.index(var_name) + 1
            b1 = ds.variables[f"vals_elem_var{idx}eb1"][:]
            b2 = ds.variables[f"vals_elem_var{idx}eb2"][:]
            return np.concatenate([b1, b2], axis=1)

        # Element fields: d_interface and cauchy_stress (stress_xx, stress_yy, stress_xy)
        print("    -> Reading element field 'd_interface'...")
        d_interface = get_elem_var("d_interface")

        print("    -> Reading element field 'cauchy_stress' (stress_xx, stress_yy, stress_xy)...")
        sxx = get_elem_var("stress_xx")
        syy = get_elem_var("stress_yy")
        sxy = get_elem_var("stress_xy")
        cauchy_stress = np.stack([sxx, syy, sxy], axis=-1)

        # Node field: d (damage)
        print("    -> Reading and aligning node field 'd'...")
        d_idx = node_vars.index("d") + 1
        raw_d = ds.variables[f"vals_nod_var{d_idx}"][:]
        aligned_d = raw_d[:, primary_idx]
        if len(split_mesh_idx) > 0:
            aligned_d[:, split_mesh_idx] = np.maximum(
                aligned_d[:, split_mesh_idx], raw_d[:, split_out_idx]
            )

    print(f"    -> Extraction complete in {time.time() - t0:.2f}s")

    mesh_dict["element_fields"]["stimuli"] = {
        "d_interface": {
            "type": "scalar",
            "shape": tuple(),
            "data": d_interface,
        }
    }
    mesh_dict["element_fields"]["responses"] = {
        "cauchy_stress": {
            "type": "symmetric_rank_two_tensor",
            "shape": (3,),
            "data": cauchy_stress,
        }
    }
    mesh_dict["node_fields"] = {
        "stimuli": {
            "d": {
                "type": "scalar",
                "shape": tuple(),
                "data": aligned_d,
            }
        },
        "responses": {},
    }

    return mesh_dict, times


def load_material_and_output_config(config_path=None):
    """Load configuration from json file or use standard defaults."""
    default_mat_A = {
        "youngs_modulus": 68000.0,
        "poissons_ratio": 0.35,
        "density": 5.0,
        "l": 0.015,
        "Gc": 20.0,
        "psic": 90.0,
    }
    default_mat_B = {
        "youngs_modulus": 401000.0,
        "poissons_ratio": 0.19,
        "density": 5.0,
        "l": 0.015,
        "Gc": 0.036,
        "psic": 0.3,
    }
    default_mat_AB = {
        "GI_c": 0.00228,
        "GII_c": 0.00097,
        "normal_strength": 75.6,
        "shear_strength": 19.4,
        "eta": 1.5,
    }
    output_settings = {
        "write_files": True,
        "add_density": True,
        "output_prefix": "local_result",
        "frame_sampling": {
            "max_frames": 20,
            "write_full_result": True,
        },
    }

    if config_path and os.path.isfile(config_path):
        with open(config_path, "r") as f:
            cfg = json.load(f)
        mat_A = cfg.get("material_A", {}).get("params", default_mat_A)
        mat_B = cfg.get("material_B", {}).get("params", default_mat_B)
        mat_AB = cfg.get("material_AB", {}).get("params", default_mat_AB)
        out_cfg = cfg.get("output", output_settings)
        return {"A": mat_A, "B": mat_B, "AB": mat_AB}, out_cfg

    return {"A": default_mat_A, "B": default_mat_B, "AB": default_mat_AB}, output_settings


def create_h5(
    mesh_exo="mesh.exo",
    output_exo="output_0.e",
    output_csv="output_0.csv",
    config_json="../../fracture_predefined.json",
    output_prefix=None,
    max_frames=None,
    write_full=None,
):
    mat_props, output_settings = load_material_and_output_config(config_json)

    if output_prefix is not None:
        output_settings["output_prefix"] = output_prefix
    if max_frames is not None:
        output_settings.setdefault("frame_sampling", {})["max_frames"] = int(max_frames)
    if write_full is not None:
        output_settings.setdefault("frame_sampling", {})["write_full_result"] = bool(write_full)

    physics_name = "2d/fracture"
    print(f"[*] Processing physics metadata for '{physics_name}'...")
    physics_data = extract_physics_data(physics_name)

    simple_mesh, times = extract_raw_fields_fast(mesh_exo, output_exo)

    # Compute volume-weighted composite density if requested
    density_val = None
    if output_settings.get("add_density", True):
        mat_mask = simple_mesh["element_fields"]["material"]["data"][0]
        vf = np.sum(mat_mask) / float(mat_mask.size)
        rho_A = mat_props["A"].get("density", 5.0)
        rho_B = mat_props["B"].get("density", 5.0)
        density_val = vf * rho_A + (1.0 - vf) * rho_B

    result = {
        "physics": physics_data,
        "time": times,
        "unstructured_mesh": simple_mesh,
        "generalized": {"stimuli": {}, "responses": {}},
        "material_properties": mat_props,
    }
    if density_val is not None:
        result["density"] = float(density_val)

    prefix = output_settings.get("output_prefix", "local_result")
    target_filename = f"{prefix}.h5"

    print(f"[*] Writing HDF5 results using official compgen pipeline...")
    t0 = time.time()
    written_files = runner.write_result_files(target_filename, result, output_settings)
    print(f"    -> Done in {time.time() - t0:.2f}s!")
    print(f"[+] Successfully written files:")
    for f in written_files:
        size_mb = os.path.getsize(f) / (1024 * 1024)
        print(f"    - {f} ({size_mb:.2f} MB)")

    return written_files


def main():
    parser = argparse.ArgumentParser(
        description="Fast generator for MOOSE/compgen HDF5 result files."
    )
    parser.add_argument(
        "--mesh", default="mesh.exo", help="Path to mesh.exo (default: mesh.exo)"
    )
    parser.add_argument(
        "--output-exo", default="output_0.e", help="Path to output_0.e (default: output_0.e)"
    )
    parser.add_argument(
        "--output-csv", default="output_0.csv", help="Path to output_0.csv (default: output_0.csv)"
    )
    parser.add_argument(
        "--config",
        default="../../fracture_predefined.json",
        help="Path to fracture_predefined.json (optional)",
    )
    parser.add_argument(
        "--prefix",
        default="local_result",
        help="Output prefix (default: local_result)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=20,
        help="Max frames for sampled output (default: 20)",
    )
    parser.add_argument(
        "--write-full",
        action="store_true",
        default=True,
        help="Also write full result file containing all frames (default: True)",
    )

    args = parser.parse_args()
    create_h5(
        mesh_exo=args.mesh,
        output_exo=args.output_exo,
        output_csv=args.output_csv,
        config_json=args.config,
        output_prefix=args.prefix,
        max_frames=args.max_frames,
        write_full=args.write_full,
    )


if __name__ == "__main__":
    main()
