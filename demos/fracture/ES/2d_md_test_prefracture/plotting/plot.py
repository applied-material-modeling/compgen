#!/home/bbrunsvik/.conda/envs/moose_genesis/bin/python

import glob
import os
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import h5py
import hdf5plugin
import numpy as np
import matplotlib.pyplot as plt
import imageio
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch, Polygon
from matplotlib.collections import PatchCollection
from scipy.interpolate import LinearNDInterpolator

# User settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SIMULATIONS_DIR = os.path.join(SCRIPT_DIR, "..", "simulations")
# Available generated cases. Select a subset in CASES_TO_PLOT if needed.
CASES = tuple(f"case{i}" for i in range(11))
CASES_TO_PLOT = CASES
# Enable or disable each type of plot here.
PLOT_RESULTS = True
PLOT_MATERIAL_STRUCTURE = True
GRID_SIZES = [125]
FPS = 5.0
# Interpolate independent fields in separate processes.
PARALLEL_FIELDS = True
MAX_WORKERS = 10

# Setup matplotlib styling
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'figure.titlesize': 14
})


def interpolate_field_to_grid(coords, connectivity, data, is_node, grid_size):
    """
    Interpolates a field (either node or element centered) onto a regular square grid of size grid_size x grid_size.
    
    Args:
        coords: numpy array of shape (N_nodes, 2)
        connectivity: numpy array of shape (N_elements, 4)
        data: numpy array of shape (N_steps, N_nodes) or (N_steps, N_elements)
        is_node: True if data is node-centered, False if element-centered
        grid_size: integer, target resolution (e.g. 125 or 512)
        
    Returns:
        grid_x: 1D array of x coordinates, shape (grid_size,)
        grid_y: 1D array of y coordinates, shape (grid_size,)
        interpolated_data: numpy array of shape (N_steps, grid_size, grid_size)
    """
    min_x, max_x = coords[:, 0].min(), coords[:, 0].max()
    min_y, max_y = coords[:, 1].min(), coords[:, 1].max()
    
    grid_x = np.linspace(min_x, max_x, grid_size)
    grid_y = np.linspace(min_y, max_y, grid_size)
    X, Y = np.meshgrid(grid_x, grid_y)
    
    if is_node:
        points = coords
    else:
        # Centroids
        points = coords[connectivity].mean(axis=1)
        
    num_steps = data.shape[0]
    interpolated_data = np.zeros((num_steps, grid_size, grid_size))
    
    # Initialize the interpolator with the first step's data
    interp = LinearNDInterpolator(points, data[0].astype(np.float64), fill_value=0.0)
    interpolated_data[0] = interp(X, Y)
    
    for t in range(1, num_steps):
        # Re-use Delaunay triangulation by assigning to interp.values
        interp.values = data[t].astype(np.float64).reshape(-1, 1)
        interpolated_data[t] = interp(X, Y)
        
    return grid_x, grid_y, interpolated_data


def interpolate_field_job(job):
    """Worker entry point for field-level multiprocessing."""
    name, coords, connectivity, data, is_node, grid_size = job
    grid_x, grid_y, grid_data = interpolate_field_to_grid(
        coords, connectivity, data, is_node, grid_size
    )
    return name, grid_x, grid_y, grid_data


def generate_gif(grid_data, grid_x, grid_y, vmin, vmax, cmap, title, output_path, symmetric=False, fps=5):
    """
    Generates a GIF from the 3D grid data.
    """
    num_time_steps = grid_data.shape[0]
    extent = [grid_x[0], grid_x[-1], grid_y[0], grid_y[-1]]
    
    # Calculate limits if not provided
    if vmin is None or vmax is None:
        global_min = np.nanmin(grid_data)
        global_max = np.nanmax(grid_data)
        if symmetric:
            max_abs = max(abs(global_min), abs(global_max))
            if max_abs == 0:
                max_abs = 1.0
            vmin = -max_abs
            vmax = max_abs
        else:
            if vmin is None:
                vmin = global_min
            if vmax is None:
                vmax = global_max
            if vmin == vmax:
                vmax += 1e-5
            
    frames = []
    
    # Set up matplotlib figure
    fig, ax = plt.subplots(figsize=(6, 5), dpi=150)
    
    # Plot first frame to initialize
    im = ax.imshow(grid_data[0], origin='lower', extent=extent,
                   vmin=vmin, vmax=vmax, cmap=cmap)
    
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_xlim(grid_x[0], grid_x[-1])
    ax.set_ylim(grid_y[0], grid_y[-1])
    
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=9)
    
    # Main loop over all time steps
    for t in range(num_time_steps):
        im.set_data(grid_data[t])
        ax.set_title(f"{title}\nTime Step: {t+1}/{num_time_steps}", pad=10)
        fig.tight_layout()
        fig.canvas.draw()
        image = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
        frames.append(image)
        
    plt.close(fig)
    
    # Save frames as GIF
    imageio.mimsave(output_path, frames, duration=1.0/fps, loop=0)


def process_h5_file(h5_path, grid_sizes=[125, 512], fps=5):
    h5_filename = os.path.basename(h5_path)
    h5_stem = os.path.splitext(h5_filename)[0]
    current_dir = os.path.dirname(os.path.abspath(h5_path))
    output_dir = os.path.join(current_dir, h5_stem)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n==========================================")
    print(f"Processing H5 file: {h5_filename}")
    print(f"Output directory: {output_dir}")
    print(f"==========================================")
    
    with h5py.File(h5_path, 'r') as f:
        # Load mesh coords & connectivity
        coords = f['unstructured_mesh/coords'][:]
        connectivity = f['unstructured_mesh/connectivity'][:]
        
        # Load fields if they exist
        fields_info = {}
        
        # damage (node field)
        if 'unstructured_mesh/node_fields/stimuli/d/data' in f:
            fields_info['damage'] = {
                'data': f['unstructured_mesh/node_fields/stimuli/d/data'][:],
                'is_node': True,
                'cmap': 'magma',
                'title': 'Damage (d)',
                'symmetric': False,
                'vmin': 0.0,
                'vmax': 1.0
            }
            
        # d_interface (element field)
        if 'unstructured_mesh/element_fields/stimuli/d_interface/data' in f:
            fields_info['d_interface'] = {
                'data': f['unstructured_mesh/element_fields/stimuli/d_interface/data'][:],
                'is_node': False,
                'cmap': 'magma',
                'title': 'Interface Damage (d_interface)',
                'symmetric': False,
                'vmin': 0.0,
                'vmax': 1.0
            }
            
        # psie_active (element field)
        if 'unstructured_mesh/element_fields/stimuli/psie_active/data' in f:
            fields_info['psie_active'] = {
                'data': f['unstructured_mesh/element_fields/stimuli/psie_active/data'][:],
                'is_node': False,
                'cmap': 'viridis',
                'title': r'Active Elastic Energy Density ($\psi_e$)',
                'symmetric': False,
                'vmin': None,
                'vmax': None
            }
            
        # cauchy_stress (element field)
        if 'unstructured_mesh/element_fields/responses/cauchy_stress/data' in f:
            stress_data = f['unstructured_mesh/element_fields/responses/cauchy_stress/data'][:]
            fields_info['stress_xx'] = {
                'data': stress_data[:, :, 0],
                'is_node': False,
                'cmap': 'RdBu_r',
                'title': r'Cauchy Stress Component $\sigma_{xx}$',
                'symmetric': True,
                'vmin': None,
                'vmax': None
            }
            fields_info['stress_yy'] = {
                'data': stress_data[:, :, 1],
                'is_node': False,
                'cmap': 'RdBu_r',
                'title': r'Cauchy Stress Component $\sigma_{yy}$',
                'symmetric': True,
                'vmin': None,
                'vmax': None
            }
            fields_info['stress_xy'] = {
                'data': stress_data[:, :, 2],
                'is_node': False,
                'cmap': 'RdBu_r',
                'title': r'Cauchy Stress Component $\sigma_{xy}$',
                'symmetric': True,
                'vmin': None,
                'vmax': None
            }

        # material (element field, usually static, so shape is (1, N_elements))
        if 'unstructured_mesh/element_fields/material/data' in f:
            fields_info['material'] = {
                'data': f['unstructured_mesh/element_fields/material/data'][:],
                'is_node': False,
                'cmap': 'gray',
                'title': 'Material',
                'symmetric': False,
                'vmin': None,
                'vmax': None,
                'skip_gif': True
            }

    for size in grid_sizes:
        print(f"\n  Interpolating fields to {size}x{size} grid...")
        interpolated_fields = {}
        grid_x, grid_y = None, None

        jobs = [
            (name, coords, connectivity, info["data"], info["is_node"], size)
            for name, info in fields_info.items()
        ]
        if PARALLEL_FIELDS and len(jobs) > 1:
            worker_count = min(MAX_WORKERS, len(jobs))
            print(f"    Interpolating {len(jobs)} fields with {worker_count} workers")
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                field_results = executor.map(interpolate_field_job, jobs)
                field_results = list(field_results)
        else:
            field_results = map(interpolate_field_job, jobs)

        for name, grid_x, grid_y, grid_data in field_results:
            info = fields_info[name]
            print(f"    Field: {name}")
            interpolated_fields[name] = grid_data
            
            if not info.get('skip_gif', False):
                gif_filename = f"{name}_{size}x{size}.gif"
                gif_path = os.path.join(output_dir, gif_filename)
                print(f"    Generating GIF: {gif_filename}")
                generate_gif(
                    grid_data=grid_data,
                    grid_x=grid_x,
                    grid_y=grid_y,
                    vmin=info['vmin'],
                    vmax=info['vmax'],
                    cmap=info['cmap'],
                    title=info['title'],
                    output_path=gif_path,
                    symmetric=info['symmetric'],
                    fps=fps
                )
                
        # Save the interpolated arrays into an HDF5 file
        h5_out_path = os.path.join(output_dir, f"interpolated_{size}x{size}.h5")
        print(f"  Saving interpolated grid data to {os.path.basename(h5_out_path)}...")
        with h5py.File(h5_out_path, 'w') as f_out:
            f_out.create_dataset('x', data=grid_x)
            f_out.create_dataset('y', data=grid_y)
            for name, grid_data in interpolated_fields.items():
                f_out.create_dataset(name, data=grid_data, compression="gzip", compression_opts=4)


def load_material_mesh(h5_path):
    with h5py.File(h5_path, "r") as h5:
        mesh = h5["unstructured_mesh"]
        coords = np.asarray(mesh["coords"])
        connectivity = np.asarray(mesh["connectivity"], dtype=np.int64)
        material = np.asarray(mesh["element_fields"]["material"]["data"])[0]

    if coords.shape[1] < 2:
        raise ValueError("The mesh must have at least two coordinate dimensions.")
    if connectivity.ndim != 2 or connectivity.shape[1] not in (3, 4):
        raise ValueError("This plotter supports triangular or quadrilateral elements.")
    if material.shape[0] != connectivity.shape[0]:
        raise ValueError("Material data and connectivity have different sizes.")

    return coords[:, :2], connectivity, material


def material_label_position(coords, connectivity, material, material_id):
    centers = coords[connectivity].mean(axis=1)
    selected = centers[np.isclose(material, material_id)]
    if selected.size == 0:
        return None
    mean_position = selected.mean(axis=0)
    nearest = np.argmin(np.linalg.norm(selected - mean_position, axis=1))
    return selected[nearest]


def plot_material_structure(h5_path, output_path):
    coords, connectivity, material = load_material_mesh(h5_path)
    material_ids = np.rint(material).astype(int)
    patches = [Polygon(coords[element], closed=True) for element in connectivity]
    collection = PatchCollection(
        patches,
        cmap=ListedColormap(["#4C78A8", "#F2B134"]),
        linewidth=0.0,
        edgecolor="none",
    )
    collection.set_array(material_ids)
    collection.set_clim(-0.5, 1.5)

    figure, axis = plt.subplots(figsize=(9, 8), constrained_layout=True)
    axis.add_collection(collection)
    axis.set_xlim(coords[:, 0].min(), coords[:, 0].max())
    axis.set_ylim(coords[:, 1].min(), coords[:, 1].max())
    axis.set_aspect("equal")
    axis.set_xlabel("x")
    axis.set_ylabel("y")
    axis.set_title(f"Material structure\n{h5_path.name}")
    axis.legend(
        handles=[
            Patch(facecolor="#F2B134", edgecolor="none", label="Aluminum (Al)"),
            Patch(facecolor="#4C78A8", edgecolor="none", label="Silicon carbide (SiC)"),
        ],
        loc="upper right",
        framealpha=0.95,
    )

    for material_id, label, color, offset in (
        (1, "Al", "#7A4B00", (28, -28)),
        (0, "SiC", "#123B63", (-28, 28)),
    ):
        position = material_label_position(
            coords, connectivity, material_ids, material_id
        )
        if position is not None:
            axis.annotate(
                label,
                xy=position,
                xytext=offset,
                textcoords="offset points",
                color=color,
                fontsize=13,
                fontweight="bold",
                ha="center",
                va="center",
                bbox={
                    "boxstyle": "round,pad=0.25",
                    "facecolor": "white",
                    "edgecolor": color,
                    "alpha": 0.9,
                },
                arrowprops={"arrowstyle": "->", "color": color, "linewidth": 1.2},
            )

    axis.margins(x=0.02, y=0.02)
    figure.savefig(output_path, dpi=250, bbox_inches="tight")
    plt.close(figure)
    print(f"Saved material plot to {output_path}")


def h5_files_for_case(case):
    input_dir = os.path.join(SIMULATIONS_DIR, case, "output")
    return [
        path for path in sorted(glob.glob(os.path.join(input_dir, "*.h5")))
        if not os.path.basename(path).startswith("interpolated_")
    ]


def main(argv=None):
    global MAX_WORKERS

    parser = argparse.ArgumentParser(description="Plot fracture simulation H5 output.")
    parser.add_argument(
        "--case",
        nargs="+",
        choices=CASES,
        metavar="CASE",
        help="Only plot the specified case(s), for example: --case case3 case10.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        metavar="N",
        help=f"Maximum field-interpolation workers (default: {MAX_WORKERS}).",
    )
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    MAX_WORKERS = args.workers
    cases_to_plot = tuple(args.case) if args.case else CASES_TO_PLOT

    h5_files = []
    for case in cases_to_plot:
        h5_files.extend(h5_files_for_case(case))
    
    if not h5_files:
        searched = ", ".join(
            os.path.join(SIMULATIONS_DIR, case, "output") for case in cases_to_plot
        )
        print(f"No H5 files found in: {searched}")
        return
        
    for h5_path in h5_files:
        if PLOT_RESULTS:
            process_h5_file(h5_path, grid_sizes=GRID_SIZES, fps=FPS)
        if PLOT_MATERIAL_STRUCTURE:
            path = Path(h5_path)
            plot_material_structure(
                path, path.with_name(f"{path.stem}_material_structure.png")
            )
        
    print("\nAll H5 files processed successfully!")


if __name__ == "__main__":
    main()
