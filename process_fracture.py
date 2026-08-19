"""
Combined step1 + step2: for each .h5 file in ../fracture, in one pass:

  1. Compute homogenized ("generalized") scalar quantities at full float64
     precision (before any downcast) -- see step1_compute_generalized.py for
     the quantities computed and why full precision matters here.
  2. Copy every dataset into the output file, downcasting float64 -> float32
     and applying Blosc2/zstd compression -- see
     step2_compress_float32_simple.py for the same logic previously run as a
     separate pass over a pre-copied file.
  3. Write the generalized quantities (still float64, never downcast) into
     a generalized/responses and generalized/stimuli group on the output
     file.

Usage:
    python process_fracture.py

Reads all .h5 files from ../fracture and writes the processed copies to
./output (both relative to this file's directory). Re-running skips files
that already have a copy in ./output.
"""
import os
import time as time_module
import warnings
import h5py
import numpy as np
import hdf5plugin

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "fracture")
OUT_DIR = os.path.join(os.path.dirname(__file__), "output")

DAMAGE_THRESHOLD = 0.5
GENERALIZED_CHUNK_BYTES = 16 * 1024 * 1024

COMPRESSION = hdf5plugin.Blosc2(cname="zstd", clevel=9, filters=hdf5plugin.Blosc2.SHUFFLE)
REL_ERR_EPS = 1e-8  # ignore values below this magnitude when computing relative error
COMPRESSION_CHUNK_BYTES = 16 * 1024 * 1024  # keep chunks small enough for Blosc2's internal buffer
SMALL_DATASET_ELEMENTS = 1024  # below this, skip compression (Blosc2 errors on tiny chunks)


# ---- step 1: generalized quantities (full float64 precision) --------------

def quad_areas(coords, connectivity):
    """Shoelace formula for planar quads, vectorized over all elements."""
    verts = coords[connectivity].astype(np.float64)  # (E, 4, 2)
    x, y = verts[:, :, 0], verts[:, :, 1]
    x_next = np.roll(x, -1, axis=1)
    y_next = np.roll(y, -1, axis=1)
    return 0.5 * np.abs(np.sum(x * y_next - x_next * y, axis=1))  # (E,)


def von_mises_plane(sxx, syy, sxy):
    return np.sqrt(np.maximum(sxx**2 - sxx * syy + syy**2 + 3 * sxy**2, 0.0))


def pick_block(shape, itemsize, target_bytes):
    per_step_bytes = itemsize
    for d in shape[1:]:
        per_step_bytes *= d
    per_step_bytes = max(per_step_bytes, 1)
    return max(1, min(shape[0], target_bytes // per_step_bytes))


def compute_generalized(src):
    coords = src["unstructured_mesh/coords"][:]
    connectivity = src["unstructured_mesh/connectivity"][:]
    material = src["unstructured_mesh/element_fields/material/data"][0]  # (E,) bool
    stress_ds = src["unstructured_mesh/element_fields/responses/cauchy_stress/data"]
    d_interface_ds = src["unstructured_mesh/element_fields/stimuli/d_interface/data"]
    d_node_ds = src["unstructured_mesh/node_fields/stimuli/d/data"]
    T = stress_ds.shape[0]

    areas = quad_areas(coords, connectivity)  # (E,)
    total_area = areas.sum()
    area_true = areas[material].sum()
    area_false = areas[~material].sum()

    mean_stress = np.zeros((T, 3))
    mean_stress_true = np.zeros((T, 3))
    mean_stress_false = np.zeros((T, 3))
    max_vm_undamaged = np.full(T, np.nan)
    mean_d_interface = np.zeros(T)
    damaged_area_fraction = np.zeros(T)
    mean_d_node = np.zeros(T)

    block = min(
        pick_block(stress_ds.shape, stress_ds.dtype.itemsize, GENERALIZED_CHUNK_BYTES),
        pick_block(d_interface_ds.shape, d_interface_ds.dtype.itemsize, GENERALIZED_CHUNK_BYTES),
        pick_block(d_node_ds.shape, d_node_ds.dtype.itemsize, GENERALIZED_CHUNK_BYTES),
    )

    for start in range(0, T, block):
        end = min(start + block, T)
        stress_block = stress_ds[start:end]          # (b, E, 3)
        d_iface_block = d_interface_ds[start:end]     # (b, E)
        d_node_block = d_node_ds[start:end]           # (b, N)

        for i in range(end - start):
            t = start + i
            sxx, syy, sxy = stress_block[i, :, 0], stress_block[i, :, 1], stress_block[i, :, 2]
            d_iface = d_iface_block[i]

            mean_stress[t] = [
                np.sum(areas * sxx) / total_area,
                np.sum(areas * syy) / total_area,
                np.sum(areas * sxy) / total_area,
            ]
            mean_stress_true[t] = [
                np.sum(areas[material] * sxx[material]) / area_true,
                np.sum(areas[material] * syy[material]) / area_true,
                np.sum(areas[material] * sxy[material]) / area_true,
            ]
            mean_stress_false[t] = [
                np.sum(areas[~material] * sxx[~material]) / area_false,
                np.sum(areas[~material] * syy[~material]) / area_false,
                np.sum(areas[~material] * sxy[~material]) / area_false,
            ]

            undamaged = d_iface < DAMAGE_THRESHOLD
            if undamaged.any():
                vm = von_mises_plane(sxx[undamaged], syy[undamaged], sxy[undamaged])
                max_vm_undamaged[t] = vm.max()

            mean_d_interface[t] = np.sum(areas * d_iface) / total_area
            damaged_area_fraction[t] = np.sum(areas[d_iface > DAMAGE_THRESHOLD]) / total_area
            mean_d_node[t] = d_node_block[i].mean()

    return {
        "mean_stress": mean_stress,
        "mean_stress_true": mean_stress_true,
        "mean_stress_false": mean_stress_false,
        "max_vm_undamaged": max_vm_undamaged,
        "mean_d_interface": mean_d_interface,
        "damaged_area_fraction": damaged_area_fraction,
        "mean_d_node": mean_d_node,
    }, T


def write_generalized(dst, quantities):
    gen = dst.require_group("generalized")
    responses = gen.require_group("responses")
    stimuli = gen.require_group("stimuli")

    resp = responses.create_group("cauchy_stress")
    resp.attrs["dim"] = 2
    resp.attrs["type"] = "symmetric_rank_two_tensor"
    resp.attrs["description"] = (
        "Homogenized quantities computed from the full float64 cauchy_stress "
        "field prior to any precision downcast, area-weighted using element "
        "areas derived from unstructured_mesh/coords and connectivity."
    )
    fc = resp.create_group("field_components")
    fc.attrs["0"] = "stress_xx"
    fc.attrs["1"] = "stress_yy"
    fc.attrs["2"] = "stress_xy"
    resp.create_dataset("mean", data=quantities["mean_stress"])
    resp.create_dataset("mean_phase_true", data=quantities["mean_stress_true"])
    resp.create_dataset("mean_phase_false", data=quantities["mean_stress_false"])
    resp.create_dataset("max_von_mises_undamaged", data=quantities["max_vm_undamaged"])
    resp.attrs["max_von_mises_undamaged_threshold"] = DAMAGE_THRESHOLD

    d_grp = stimuli.create_group("d")
    d_grp.attrs["location"] = "node"
    d_grp.attrs["type"] = "scalar"
    d_grp.attrs["description"] = "Simple (unweighted) mean of the nodal bulk phase-field damage."
    d_grp.create_dataset("mean", data=quantities["mean_d_node"])

    d_iface_grp = stimuli.create_group("d_interface")
    d_iface_grp.attrs["type"] = "scalar"
    d_iface_grp.attrs["damage_threshold"] = DAMAGE_THRESHOLD
    d_iface_grp.attrs["description"] = "Area-weighted mean interface damage and damaged-area fraction."
    d_iface_grp.create_dataset("mean", data=quantities["mean_d_interface"])
    d_iface_grp.create_dataset("damaged_area_fraction", data=quantities["damaged_area_fraction"])


# ---- step 2: float32 downcast + compression --------------------------------

def pick_chunk_shape(shape, itemsize):
    if len(shape) == 0 or shape[0] == 0:
        return None
    per_step_bytes = itemsize
    for d in shape[1:]:
        per_step_bytes *= d
    per_step_bytes = max(per_step_bytes, 1)
    steps = max(1, min(shape[0], COMPRESSION_CHUNK_BYTES // per_step_bytes))
    return (steps,) + shape[1:]


def copy_dataset(src_ds, dst_group, name, err):
    data = src_ds[()]
    if data.dtype == np.float64:
        f32 = data.astype(np.float32)
        if data.size:
            diff = np.abs(data - f32)
            err["max_abs"] = max(err["max_abs"], float(diff.max()))
            mask = np.abs(data) > REL_ERR_EPS
            if mask.any():
                err["max_rel"] = max(err["max_rel"], float((diff[mask] / np.abs(data[mask])).max()))
        data = f32
    chunks = pick_chunk_shape(data.shape, data.itemsize) if data.size >= SMALL_DATASET_ELEMENTS else None
    if chunks is None:
        dst_group.create_dataset(name, data=data)
    else:
        dst_group.create_dataset(name, data=data, chunks=chunks, **COMPRESSION)


def copy_group(src_group, dst_group, err):
    for key, val in src_group.attrs.items():
        dst_group.attrs[key] = val
    for name, item in src_group.items():
        if isinstance(item, h5py.Group):
            copy_group(item, dst_group.create_group(name), err)
        elif isinstance(item, h5py.Dataset):
            copy_dataset(item, dst_group, name, err)


def human(nbytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return f"{nbytes:.2f}{unit}"
        nbytes /= 1024
    return f"{nbytes:.2f}PB"


# ---- driver -----------------------------------------------------------------

def process_file(fname):
    src_path = os.path.join(SRC_DIR, fname)
    dst_path = os.path.join(OUT_DIR, fname)
    orig_size = os.path.getsize(src_path)

    err = {"max_abs": 0.0, "max_rel": 0.0}
    with h5py.File(src_path, "r") as src, h5py.File(dst_path, "w") as dst:
        quantities, T = compute_generalized(src)
        copy_group(src, dst, err)
        write_generalized(dst, quantities)

    comp_size = os.path.getsize(dst_path)
    ratio = orig_size / comp_size if comp_size else float("inf")
    print(f"  {human(orig_size)} -> {human(comp_size)} ({ratio:.2f}x)  "
          f"max_abs_err={err['max_abs']:.3e}  max_rel_err={err['max_rel']:.3e}")
    return T


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    src_files = sorted(f for f in os.listdir(SRC_DIR) if f.endswith(".h5"))
    if not src_files:
        warnings.warn(f"No .h5 files found in {SRC_DIR}")
        return

    for fname in src_files:
        dst_path = os.path.join(OUT_DIR, fname)
        if os.path.exists(dst_path):
            print(f"=== {fname} === (skipping, already processed)")
            continue
        print(f"=== {fname} ===")
        t0 = time_module.time()
        try:
            T = process_file(fname)
        except Exception as e:
            warnings.warn(f"Failed to process {fname}: {e}")
            continue
        print(f"  wrote {T} timesteps in {time_module.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
