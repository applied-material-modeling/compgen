import h5py
import os

def print_structure(name, obj):
    if isinstance(obj, h5py.Dataset):
        print(f"D: {name} (shape: {obj.shape}, dtype: {obj.dtype})")
    elif isinstance(obj, h5py.Group):
        print(f"G: {name}")

results_dir = "results"
h5_files = [f for f in os.listdir(results_dir) if f.endswith(".h5")]

if not h5_files:
    print("No .h5 files found in results folder.")
else:
    sample_file = os.path.join(results_dir, h5_files[0])
    print(f"Inspecting file: {sample_file}")
    with h5py.File(sample_file, "r") as f:
        f.visititems(print_structure)
