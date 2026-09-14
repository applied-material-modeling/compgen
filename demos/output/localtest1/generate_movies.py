#!/usr/bin/env python3
"""
Generate 300 DPI GIF movies from an Exodus II simulation output file (e.g. output_0.e).

Supported fields:
  - stress_xx: Cauchy stress xx (bwr / blue-white-red colormap)
  - stress_xy: Cauchy stress xy (bwr / blue-white-red colormap)
  - stress_yy: Cauchy stress yy (bwr / blue-white-red colormap)
  - damage: Phase field damage 'd' (hot colormap, 0 to 1)
  - d_interface: Cohesive zone / interface damage (hot colormap, 0 to 1)

Environment:
  Designed for conda environment 'racoon' (uses pyvista, vtk, imageio, numpy, tqdm).
"""

import argparse
import os
import sys
import time
from pathlib import Path
import numpy as np
import pyvista as pv
from tqdm import tqdm

# Configure PyVista for headless/offscreen rendering
pv.OFF_SCREEN = True

# Target field definitions and default visual styles
TARGET_FIELDS = {
    # 'stress_xx': {
    #     'source': 'cell',
    #     'var_key': 'stress_xx',
    #     'display_name': 'Cauchy Stress σ_xx',
    #     'cmap': 'bwr',
    #     'default_clim': [-4000.0, 4000.0],
    #     'symmetric': True,
    #     'fmt': '%.0f',
    #     'unit': 'MPa',
    # },
    # 'stress_xy': {
    #     'source': 'cell',
    #     'var_key': 'stress_xy',
    #     'display_name': 'Cauchy Stress σ_xy',
    #     'cmap': 'bwr',
    #     'default_clim': [-2700.0, 2700.0],
    #     'symmetric': True,
    #     'fmt': '%.0f',
    #     'unit': 'MPa',
    # },
    # 'stress_yy': {
    #     'source': 'cell',
    #     'var_key': 'stress_yy',
    #     'display_name': 'Cauchy Stress σ_yy',
    #     'cmap': 'bwr',
    #     'default_clim': [-8500.0, 8500.0],
    #     'symmetric': True,
    #     'fmt': '%.0f',
    #     'unit': 'MPa',
    # },
    # 'damage': {
    #     'source': 'point',
    #     'var_key': 'd',
    #     'display_name': 'Damage (d)',
    #     'cmap': 'hot',
    #     'default_clim': [0.0, 1.0],
    #     'symmetric': False,
    #     'fmt': '%.2f',
    #     'unit': '',
    # },
    'd_interface': {
        'source': 'cell',
        'var_key': 'd_interface',
        'display_name': 'Interface Damage (d_interface)',
        'cmap': 'hot',
        'default_clim': [0.0, 1.0],
        'symmetric': False,
        'fmt': '%.2f',
        'unit': '',
    },
}


def extract_field_data(grid, field_name):
    """Extract scalar field array from a combined PyVista UnstructuredGrid."""
    spec = TARGET_FIELDS[field_name]
    source = spec['source']
    var_key = spec['var_key']

    if source == 'point':
        if var_key in grid.point_data:
            return grid.point_data[var_key]
        elif 'd' in grid.point_data:
            return grid.point_data['d']
        else:
            raise KeyError(f"Nodal field '{var_key}' not found in mesh point_data: {list(grid.point_data.keys())}")

    elif source == 'cell':
        if field_name == 'stress_xx':
            if 'stress_xx' in grid.cell_data:
                return grid.cell_data['stress_xx']
            elif 'stress_x' in grid.cell_data:
                # VTK packs multi-component variables into vector arrays
                arr = grid.cell_data['stress_x']
                return arr[:, 0] if arr.ndim > 1 else arr
            else:
                raise KeyError("Neither 'stress_xx' nor 'stress_x' found in cell_data")

        elif field_name == 'stress_xy':
            if 'stress_xy' in grid.cell_data:
                return grid.cell_data['stress_xy']
            elif 'stress_x' in grid.cell_data:
                arr = grid.cell_data['stress_x']
                return arr[:, 1] if arr.ndim > 1 and arr.shape[1] > 1 else arr
            else:
                raise KeyError("Neither 'stress_xy' nor 'stress_x' found in cell_data")

        elif field_name == 'stress_yy':
            if 'stress_yy' in grid.cell_data:
                return grid.cell_data['stress_yy']
            else:
                raise KeyError(f"'stress_yy' not found in cell_data: {list(grid.cell_data.keys())}")

        elif field_name == 'd_interface':
            if 'd_interface' in grid.cell_data:
                return grid.cell_data['d_interface']
            else:
                raise KeyError(f"'d_interface' not found in cell_data: {list(grid.cell_data.keys())}")

    raise ValueError(f"Unknown field: {field_name}")


def determine_field_clim(reader, field_name, time_indices, scan_all=False):
    """Determine fixed colormap limits for the field across the animation frames."""
    spec = TARGET_FIELDS[field_name]
    if not scan_all and spec['default_clim'] is not None:
        return spec['default_clim']

    print(f"Scanning range across selected steps for '{field_name}'...")
    min_val = float('inf')
    max_val = float('-inf')

    # Sample up to 20 frames across the sequence to quickly estimate or confirm bounds
    sample_indices = np.linspace(0, len(time_indices) - 1, min(20, len(time_indices)), dtype=int)
    for sample_idx in sample_indices:
        t_idx = time_indices[sample_idx]
        reader.set_active_time_point(t_idx)
        root = reader.read()
        grid = root[0].combine()
        data = extract_field_data(grid, field_name)
        min_val = min(min_val, float(np.nanmin(data)))
        max_val = max(max_val, float(np.nanmax(data)))

    if spec['symmetric']:
        bound = max(abs(min_val), abs(max_val))
        return [-bound, bound]
    elif 'damage' in field_name:
        return [0.0, 1.0]
    else:
        return [min_val, max_val]


def generate_movie(
    exo_file,
    field_name,
    output_path,
    stride=1,
    fps=20,
    dpi=300,
    fig_width_in=6.0,
    fig_height_in=6.0,
    apply_displacements=False,
    clim=None,
):
    """Generate a single GIF movie for the specified field."""
    spec = TARGET_FIELDS[field_name]
    window_width = int(round(fig_width_in * dpi))
    window_height = int(round(fig_height_in * dpi))

    reader = pv.get_reader(exo_file)
    reader.enable_all_point_arrays()
    reader.enable_all_cell_arrays()
    if apply_displacements:
        reader.enable_displacements()
    else:
        reader.disable_displacements()

    time_values = reader.time_values
    n_total_steps = len(time_values)
    time_indices = list(range(0, n_total_steps, stride))
    if time_indices[-1] != n_total_steps - 1:
        time_indices.append(n_total_steps - 1)

    # Determine color limits
    if clim is None:
        clim = determine_field_clim(reader, field_name, time_indices)

    print(f"\n[{field_name.upper()}] Rendering {len(time_indices)} frames -> {output_path}")
    print(f"  Resolution: {window_width}x{window_height} ({dpi} DPI, {fig_width_in}\"x{fig_height_in}\")")
    print(f"  Colormap: {spec['cmap']}, Limits: [{clim[0]:.2f}, {clim[1]:.2f}], FPS: {fps}")

    # Initialize Plotter
    pl = pv.Plotter(off_screen=True, window_size=[window_width, window_height])
    pl.set_background('white')

    # Read the first step to initialize the actor
    reader.set_active_time_point(time_indices[0])
    root = reader.read()
    grid = root[0].combine()
    first_data = extract_field_data(grid, field_name)

    # Store scalars under an explicit field name on grid
    is_nodal = (spec['source'] == 'point')
    if is_nodal:
        grid.point_data[field_name] = first_data
    else:
        grid.cell_data[field_name] = first_data

    # Colorbar / scalar bar configuration
    unit_str = f" [{spec['unit']}]" if spec['unit'] else ""
    sbar_title = f"{spec['display_name']}{unit_str}"
    sargs = {
        'title': sbar_title,
        'vertical': True,
        'n_labels': 5,
        'color': 'black',
        'title_font_size': 24,
        'label_font_size': 20,
        'fmt': spec['fmt'],
    }

    actor = pl.add_mesh(
        grid,
        scalars=field_name,
        cmap=spec['cmap'],
        clim=clim,
        show_edges=False,
        scalar_bar_args=sargs,
    )

    pl.view_xy()
    pl.camera.SetParallelProjection(True)
    pl.reset_camera()
    pl.camera.zoom(0.92)

    # Open GIF writer
    pl.open_gif(str(output_path), fps=fps)

    # Animation loop
    t0 = time.time()
    for frame_i, t_idx in enumerate(tqdm(time_indices, desc=f"Frames ({field_name})")):
        reader.set_active_time_point(t_idx)
        step_root = reader.read()
        step_grid = step_root[0].combine()
        data = extract_field_data(step_grid, field_name)

        if is_nodal:
            grid.point_data[field_name] = data
        else:
            grid.cell_data[field_name] = data

        current_time = time_values[t_idx]
        header_text = f"{spec['display_name']} | Step {t_idx} | t = {current_time*1000:.2f} ms"
        pl.add_text(header_text, position='upper_left', color='black', font_size=16, name='frame_header')

        pl.write_frame()

    pl.close()
    elapsed = time.time() - t0
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Saved: {output_path} ({file_size_mb:.2f} MB in {elapsed:.1f}s, {len(time_indices)/elapsed:.1f} fps)")


def main():
    parser = argparse.ArgumentParser(
        description="Generate 300 DPI GIF movies from Exodus II file (output_0.e) using the 'racoon' environment."
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="output_0.e",
        help="Path to the Exodus II input file (default: output_0.e)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default=".",
        help="Directory to save the generated GIF movies (default: current directory)",
    )
    parser.add_argument(
        "-f", "--fields",
        nargs="+",
        choices=list(TARGET_FIELDS.keys()) + ["all"],
        default=["all"],
        help="Fields to generate GIF movies for (choices: stress_xx, stress_xy, stress_yy, damage, d_interface, all; default: all)",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=1,
        help="Step stride (e.g. 1 = every step, 2 = every second step; default: 1)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=20.0,
        help="Playback speed in frames per second (default: 20)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Target DPI for figure resolution (default: 300)",
    )
    parser.add_argument(
        "--fig-size",
        type=float,
        nargs=2,
        default=[6.0, 6.0],
        metavar=("WIDTH", "HEIGHT"),
        help="Figure dimensions in inches (default: 6.0 6.0; at 300 DPI this produces 1800x1800 px)",
    )
    parser.add_argument(
        "--apply-displacements",
        action="store_true",
        help="Deform the mesh coordinates according to displacements (default: False)",
    )
    parser.add_argument(
        "--auto-clim",
        action="store_true",
        help="Scan simulation steps to compute exact global min/max limits rather than pre-calibrated limits",
    )

    args = parser.parse_args()

    exo_path = Path(args.input)
    if not exo_path.exists():
        print(f"Error: Input file '{exo_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fields_to_process = list(TARGET_FIELDS.keys()) if "all" in args.fields else args.fields

    print("=" * 70)
    print("EXODUS II X DPI GIF MOVIE GENERATOR")
    print("=" * 70)
    print(f"Input file:       {exo_path.resolve()}")
    print(f"Output directory: {out_dir.resolve()}")
    print(f"Selected fields:  {', '.join(fields_to_process)}")
    print(f"Stride:           {args.stride}")
    print(f"FPS:              {args.fps}")
    print(f"DPI:              {args.dpi}")
    print(f"Figure size (in): {args.fig_size[0]} x {args.fig_size[1]}")
    print(f"Resolution (px):  {int(round(args.fig_size[0] * args.dpi))} x {int(round(args.fig_size[1] * args.dpi))}")
    print("=" * 70)

    start_total = time.time()
    for field in fields_to_process:
        out_file = out_dir / f"movie_{field}.gif"
        clim = None if not args.auto_clim else determine_field_clim(pv.get_reader(str(exo_path)), field, [], scan_all=True)
        generate_movie(
            exo_file=str(exo_path),
            field_name=field,
            output_path=out_file,
            stride=args.stride,
            fps=args.fps,
            dpi=args.dpi,
            fig_width_in=args.fig_size[0],
            fig_height_in=args.fig_size[1],
            apply_displacements=args.apply_displacements,
            clim=clim,
        )

    total_time = time.time() - start_total
    print("\n" + "=" * 70)
    print(f"All movies successfully created in {total_time:.1f}s ({total_time/60:.2f} min)!")
    print("Generated files:")
    for field in fields_to_process:
        gif_file = out_dir / f"movie_{field}.gif"
        if gif_file.exists():
            print(f"  - {gif_file.name} ({gif_file.stat().st_size / (1024*1024):.2f} MB)")
    print("=" * 70)


if __name__ == "__main__":
    main()
