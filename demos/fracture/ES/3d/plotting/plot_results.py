import os
import argparse
from pathlib import Path

try:
    import h5py
    import hdf5plugin  # Registers compression filters used by CompGen output.
except ImportError:  # Plotting dependencies are only required when processing HDF5.
    h5py = None
import numpy as np
import matplotlib.pyplot as plt
import imageio

from plotting_utils import add_h5_file_argument, get_plot_output_dir, resolve_h5_file

# User settings
FPS = 5.0
PLOT_STRESS_ONLY = False
STRESS_COMPONENTS_TO_PLOT = ("xx",)
PLOT_FRACTURE_ONLY = True

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


def project_field_to_native_xy(coords, connectivity, data, is_node):
    """Project a native 3D field onto its native x-y locations.

    This keeps the locations already present in the HDF5 file. Since this
    plotter is an x-y overview of a 3D result, values at repeated x-y
    locations are averaged through z; no interpolation or finer grid is
    locations. Node fields therefore retain the 65 x 65 node grid for a
    64-element mesh, while element fields retain the 64 x 64 element grid.
    """
    if coords.ndim != 2 or coords.shape[1] not in (2, 3):
        raise ValueError("Expected mesh coordinates with shape (nodes, 2) or (nodes, 3).")
    if connectivity.ndim != 2 or connectivity.shape[1] not in (4, 8):
        raise ValueError("Expected quadrilateral or hexahedral connectivity.")
    if data.ndim != 2:
        raise ValueError("Expected field data with shape (time, locations).")

    projected_coords = coords[:, :2]
    if is_node:
        points = projected_coords
    else:
        points = projected_coords[connectivity].mean(axis=1)

    points, data = aggregate_projected_values(points, data)
    grid_x = np.unique(points[:, 0])
    grid_y = np.unique(points[:, 1])
    if len(points) != len(grid_x) * len(grid_y):
        raise ValueError("Native x-y projection does not form a complete rectangular grid.")

    x_indices = np.searchsorted(grid_x, points[:, 0])
    y_indices = np.searchsorted(grid_y, points[:, 1])
    native_data = np.empty((data.shape[0], len(grid_y), len(grid_x)), dtype=data.dtype)
    native_data[:, y_indices, x_indices] = data
    return grid_x, grid_y, native_data


def aggregate_projected_values(points, data, decimals=12):
    """Average field values at repeated x-y locations in a 3D projection."""
    keys = np.round(points, decimals=decimals)
    unique_keys, inverse = np.unique(keys, axis=0, return_inverse=True)
    aggregated = np.zeros((data.shape[0], len(unique_keys)), dtype=np.float64)
    for index in range(len(unique_keys)):
        aggregated[:, index] = data[:, inverse == index].mean(axis=1)
    return unique_keys, aggregated


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


def process_h5_file(h5_path, fps=5):
    h5_filename = os.path.basename(h5_path)
    output_dir = str(get_plot_output_dir(Path(h5_path)))
    
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
        if (not PLOT_STRESS_ONLY and 'unstructured_mesh/node_fields/stimuli/d/data' in f):
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
        if (not PLOT_STRESS_ONLY and 'unstructured_mesh/element_fields/stimuli/d_interface/data' in f):
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
        if (not PLOT_STRESS_ONLY and not PLOT_FRACTURE_ONLY
                and 'unstructured_mesh/element_fields/stimuli/psie_active/data' in f):
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
        if (not PLOT_FRACTURE_ONLY
                and 'unstructured_mesh/element_fields/responses/cauchy_stress/data' in f):
            stress_data = f['unstructured_mesh/element_fields/responses/cauchy_stress/data'][:]
            if stress_data.ndim != 3 or stress_data.shape[2] != 6:
                raise ValueError(
                    "3D cauchy_stress must have six components ordered "
                    "xx, yy, zz, yz, xz, xy."
                )
            stress_components = ('xx', 'yy', 'zz', 'yz', 'xz', 'xy')
            for index, component in enumerate(stress_components):
                if component not in STRESS_COMPONENTS_TO_PLOT:
                    continue
                fields_info[f'stress_{component}'] = {
                    'data': stress_data[:, :, index],
                    'is_node': False,
                    'cmap': 'RdBu_r',
                    'title': rf'Cauchy Stress Component $\sigma_{{{component}}}$',
                    'symmetric': True,
                    'vmin': None,
                    'vmax': None
                }
        # material (element field, usually static, so shape is (1, N_elements))
        if (not PLOT_STRESS_ONLY and not PLOT_FRACTURE_ONLY
                and 'unstructured_mesh/element_fields/material/data' in f):
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

    native_fields = {}
    native_coordinates = {}
    for name, info in fields_info.items():
        print(f"    Field: {name}")
        grid_x, grid_y, native_data = project_field_to_native_xy(
            coords, connectivity, info['data'], info['is_node']
        )
        native_fields[name] = native_data
        native_coordinates[name] = (grid_x, grid_y)

        if not info.get('skip_gif', False):
            resolution = f"{len(grid_x)}x{len(grid_y)}"
            gif_filename = f"{name}_{resolution}.gif"
            gif_path = os.path.join(output_dir, gif_filename)
            print(f"    Generating native-resolution GIF: {gif_filename}")
            generate_gif(
                grid_data=native_data,
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

    # Store the native x-y projections for reproducibility. Fields retain
    # their native node (65x65) or element (64x64) resolution.
    h5_out_path = os.path.join(output_dir, "native_xy_projection.h5")
    print(f"  Saving native projected data to {os.path.basename(h5_out_path)}...")
    with h5py.File(h5_out_path, 'w') as f_out:
        for name, native_data in native_fields.items():
            group = f_out.create_group(name)
            grid_x, grid_y = native_coordinates[name]
            group.create_dataset('x', data=grid_x)
            group.create_dataset('y', data=grid_y)
            group.create_dataset('data', data=native_data, compression="gzip", compression_opts=4)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_h5_file_argument(parser)
    args = parser.parse_args()
    h5_path = resolve_h5_file(args.h5_file)
    process_h5_file(str(h5_path), fps=FPS)
    print("\nH5 file processed successfully!")


if __name__ == "__main__":
    main()
