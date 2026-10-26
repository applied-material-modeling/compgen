import os
import glob
import h5py
import hdf5plugin
import numpy as np
import matplotlib.pyplot as plt
import imageio
from scipy.interpolate import LinearNDInterpolator

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
        
        for name, info in fields_info.items():
            print(f"    Field: {name}")
            grid_x, grid_y, grid_data = interpolate_field_to_grid(
                coords, connectivity, info['data'], info['is_node'], size
            )
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Interpolate H5 simulation results to regular grids and generate GIFs.")
    parser.add_argument('--fps', type=float, default=5.0, help="Frames per second for GIFs.")
    args = parser.parse_args()
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    h5_files = sorted(glob.glob(os.path.join(current_dir, "*.h5")))
    # Exclude any interpolated files
    h5_files = [f for f in h5_files if not os.path.basename(f).startswith("interpolated_")]
    
    if not h5_files:
        print(f"No H5 files found in {current_dir}")
        return
        
    for h5_path in h5_files:
        process_h5_file(h5_path, grid_sizes=[125], fps=args.fps) # grid_sizes=[125, 512]
        
    print("\nAll H5 files processed successfully!")


if __name__ == "__main__":
    main()
