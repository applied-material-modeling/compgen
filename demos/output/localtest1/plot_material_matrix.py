#!/usr/bin/env python3
"""
Plot the Material Matrix (bulk properties A / Aluminum and bulk properties B / SiC proxies)
at 300 DPI from an Exodus II mesh (e.g. mesh.exo or output_0.e).

Features:
  - High-resolution 300 DPI publication-quality output.
  - Automatically identifies material phases (mat_a / Aluminum proxy and mat_b / SiC proxy).
  - Computes and displays volume fractions (e.g. ~88.8% matrix vs ~11.2% reinforcement).
  - Supports both 'matplotlib' (default, with axes, scale, legend) and 'pyvista' (offscreen VTK).
  - Optional side-by-side constitutive properties table (--show-properties).
  - Handles regular Cartesian meshes (sub-second fast rasterization) as well as arbitrary
    unstructured meshes.
"""

import argparse
import os
import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import matplotlib.patches as mpatches

# Default constitutive bulk properties for Aluminum and SiC proxies
DEFAULT_BULK_PROPERTIES = {
    'mat_a': {
        'name': 'Bulk Properties A',
        'material': 'Aluminum proxy',
        'role': 'Matrix',
        'E': '68.0 GPa',
        'nu': '0.35',
        'K': '75.6 GPa',
        'G': '25.2 GPa',
        'Gc': '20.0 N/mm',
        'psic': '90.0 MPa',
        'l': '0.015 mm',
    },
    'mat_b': {
        'name': 'Bulk Properties B',
        'material': 'SiC proxy',
        'role': 'Reinforcement',
        'E': '401.0 GPa',
        'nu': '0.19',
        'K': '215.6 GPa',
        'G': '168.5 GPa',
        'Gc': '0.036 N/mm',
        'psic': '0.30 MPa',
        'l': '0.015 mm',
    },
}

# Default cohesive zone traction-separation interface properties
DEFAULT_INTERFACE_PROPERTIES = {
    'GI_c': '0.00228 N/mm',
    'GII_c': '0.00097 N/mm',
    'N': '75.6 MPa',
    'T': '19.4 MPa',
    'eta': '1.5',
}



def load_mesh(mesh_path: str):
    """Load Exodus II mesh using PyVista."""
    import pyvista as pv
    if not os.path.isfile(mesh_path):
        raise FileNotFoundError(f"Mesh file not found: {mesh_path}")

    reader = pv.get_reader(mesh_path)
    mesh = reader.read()

    eb = None
    if 'Element Blocks' in mesh.keys():
        eb = mesh['Element Blocks']
    elif len(mesh) > 0 and isinstance(mesh[0], pv.MultiBlock):
        eb = mesh[0]
    else:
        raise ValueError(f"No 'Element Blocks' found in {mesh_path}")

    block_names = list(eb.keys())
    if len(block_names) < 2:
        raise ValueError(f"Expected at least 2 element blocks, found {len(block_names)}: {block_names}")

    # Determine mat_a and mat_b blocks
    name_a = 'mat_a' if 'mat_a' in block_names else block_names[0]
    name_b = 'mat_b' if 'mat_b' in block_names else block_names[1]

    grid_a = eb[name_a]
    grid_b = eb[name_b]

    return grid_a, grid_b, name_a, name_b


def plot_with_matplotlib(
    grid_a,
    grid_b,
    name_a: str,
    name_b: str,
    output_path: str,
    dpi: int = 300,
    color_a: str = '#3B75AF',
    color_b: str = '#D63426',
    title: str = None,
    unit: str = 'mm',
    show_properties: bool = False,
    interface_props: dict = None,
    figsize=None,
):
    """Render publication-quality 300 DPI material matrix plot using Matplotlib."""
    n_a = grid_a.n_cells
    n_b = grid_b.n_cells
    n_total = n_a + n_b
    vol_a = (n_a / n_total) * 100.0
    vol_b = (n_b / n_total) * 100.0

    bounds_a = grid_a.bounds
    bounds_b = grid_b.bounds
    xmin = min(bounds_a[0], bounds_b[0])
    xmax = max(bounds_a[1], bounds_b[1])
    ymin = min(bounds_a[2], bounds_b[2])
    ymax = max(bounds_a[3], bounds_b[3])

    cb = grid_b.cell_centers().points

    # Check if regular Cartesian grid
    ca = grid_a.cell_centers().points
    all_centers = np.vstack([ca, cb])
    ux = np.unique(np.round(all_centers[:, 0], 6))
    uy = np.unique(np.round(all_centers[:, 1], 6))
    is_regular_grid = (len(ux) * len(uy) == n_total)

    label_a = f"{DEFAULT_BULK_PROPERTIES.get(name_a, {}).get('name', 'Bulk Properties A')} ({DEFAULT_BULK_PROPERTIES.get(name_a, {}).get('material', 'Aluminum proxy')}, {vol_a:.1f}% matrix)"
    label_b = f"{DEFAULT_BULK_PROPERTIES.get(name_b, {}).get('name', 'Bulk Properties B')} ({DEFAULT_BULK_PROPERTIES.get(name_b, {}).get('material', 'SiC proxy')}, {vol_b:.1f}% inclusions)"

    cmap = ListedColormap([color_a, color_b])

    if show_properties:
        fig_w, fig_h = figsize if figsize else (12.5, 7.2)
        fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
        gs = fig.add_gridspec(1, 2, width_ratios=[1.1, 0.9], wspace=0.25)
        ax_map = fig.add_subplot(gs[0])
        gs_info = gs[1].subgridspec(2, 1, height_ratios=[1.25, 0.75], hspace=0.32)
        ax_bulk = fig.add_subplot(gs_info[0])
        ax_inter = fig.add_subplot(gs_info[1])
    else:
        fig_w, fig_h = figsize if figsize else (6.5, 6.5)
        fig, ax_map = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
        ax_bulk = None
        ax_inter = None

    if is_regular_grid:
        nx, ny = len(ux), len(uy)
        dx = (xmax - xmin) / nx
        dy = (ymax - ymin) / ny
        mat_grid = np.zeros((ny, nx), dtype=np.uint8)
        ix_b = np.clip(np.floor((cb[:, 0] - xmin) / dx).astype(int), 0, nx - 1)
        iy_b = np.clip(np.floor((cb[:, 1] - ymin) / dy).astype(int), 0, ny - 1)
        mat_grid[iy_b, ix_b] = 1

        ax_map.imshow(
            mat_grid,
            origin='lower',
            extent=[xmin, xmax, ymin, ymax],
            cmap=cmap,
            interpolation='nearest',
        )
    else:
        # Fallback for general unstructured meshes using Triangulation
        tri_a = grid_a.extract_surface().triangulate()
        tri_b = grid_b.extract_surface().triangulate()
        # Rasterize via tripcolor
        pts_a = tri_a.points[:, :2]
        faces_a = tri_a.faces.reshape(-1, 4)[:, 1:4]
        pts_b = tri_b.points[:, :2]
        faces_b = tri_b.faces.reshape(-1, 4)[:, 1:4]
        ax_map.tripcolor(pts_a[:, 0], pts_a[:, 1], faces_a, facecolors=np.zeros(len(faces_a)), cmap=cmap, vmin=0, vmax=1)
        ax_map.tripcolor(pts_b[:, 0], pts_b[:, 1], faces_b, facecolors=np.ones(len(faces_b)), cmap=cmap, vmin=0, vmax=1)

    plot_title = title if title else "Material Phase Distribution\n(Aluminum Matrix & SiC Reinforcements)"
    ax_map.set_title(plot_title, fontsize=13, fontweight='bold', pad=12)
    ax_map.set_xlabel(f"X [{unit}]", fontsize=11, fontweight='semibold', labelpad=8)
    ax_map.set_ylabel(f"Y [{unit}]", fontsize=11, fontweight='semibold', labelpad=8)
    ax_map.set_xlim(xmin, xmax)
    ax_map.set_ylim(ymin, ymax)
    ax_map.set_aspect('equal')

    patch_a = mpatches.Patch(facecolor=color_a, edgecolor='black', linewidth=0.6, label=label_a)
    patch_b = mpatches.Patch(facecolor=color_b, edgecolor='black', linewidth=0.6, label=label_b)

    ax_map.legend(
        handles=[patch_a, patch_b],
        loc='upper center',
        bbox_to_anchor=(0.5, -0.15),
        frameon=True,
        framealpha=0.95,
        edgecolor='#cccccc',
        fontsize=9.5,
        ncol=1,
    )

    if show_properties and ax_bulk is not None and ax_inter is not None:
        # 1. Bulk Properties Table
        ax_bulk.axis('off')
        prop_a = DEFAULT_BULK_PROPERTIES.get(name_a, {})
        prop_b = DEFAULT_BULK_PROPERTIES.get(name_b, {})

        table_data_bulk = [
            ['Bulk Property', 'Mat A (Aluminum)', 'Mat B (SiC)'],
            ['Role', f'Matrix ({vol_a:.1f}%)', f'Inclusions ({vol_b:.1f}%)'],
            ['Young\'s Modulus (E)', prop_a.get('E', '68.0 GPa'), prop_b.get('E', '401.0 GPa')],
            ['Poisson\'s Ratio (ν)', prop_a.get('nu', '0.35'), prop_b.get('nu', '0.19')],
            ['Bulk Modulus (K)', prop_a.get('K', '75.6 GPa'), prop_b.get('K', '215.6 GPa')],
            ['Shear Modulus (G)', prop_a.get('G', '25.2 GPa'), prop_b.get('G', '168.5 GPa')],
            ['Fracture Energy (Gc)', prop_a.get('Gc', '20.0 N/mm'), prop_b.get('Gc', '0.036 N/mm')],
            ['Critical Energy (ψc)', prop_a.get('psic', '90.0 MPa'), prop_b.get('psic', '0.30 MPa')],
            ['Length Scale (l)', prop_a.get('l', '0.015 mm'), prop_b.get('l', '0.015 mm')],
        ]

        t_bulk = ax_bulk.table(
            cellText=table_data_bulk,
            cellLoc='center',
            loc='center',
            colWidths=[0.46, 0.38, 0.38],
        )
        t_bulk.auto_set_font_size(False)
        t_bulk.set_fontsize(8.0)
        t_bulk.scale(1.0, 1.45)

        for (r, c), cell in t_bulk.get_celld().items():
            if r == 0:
                cell.set_facecolor('#D9E1E8')
                cell.set_text_props(weight='bold')
            elif r == 1:
                cell.set_facecolor('#E8F1F9' if c == 1 else ('#FDEDEC' if c == 2 else '#F7F7F7'))
                cell.set_text_props(weight='semibold')
            else:
                cell.set_facecolor('#F4F8FC' if c == 1 else ('#FDF4F4' if c == 2 else '#FFFFFF'))
            cell.set_edgecolor('#CCCCCC')
            cell.set_linewidth(0.6)

        ax_bulk.set_title('Bulk Constitutive Properties', fontsize=11.5, fontweight='bold', pad=8)

        # 2. Interface Traction-Separation Properties Table
        ax_inter.axis('off')
        ip = interface_props if interface_props else DEFAULT_INTERFACE_PROPERTIES
        table_data_inter = [
            ['Interface Property (TSL)', 'Value'],
            ['Normal Fracture Energy (G_I,c)', f"{ip.get('GI_c', '0.00228')} N/mm" if not str(ip.get('GI_c', '')).endswith('N/mm') else str(ip.get('GI_c'))],
            ['Shear Fracture Energy (G_II,c)', f"{ip.get('GII_c', '0.00097')} N/mm" if not str(ip.get('GII_c', '')).endswith('N/mm') else str(ip.get('GII_c'))],
            ['Normal Strength (N)', f"{ip.get('N', '75.6')} MPa" if not str(ip.get('N', '')).endswith('MPa') else str(ip.get('N'))],
            ['Shear Strength (T)', f"{ip.get('T', '19.4')} MPa" if not str(ip.get('T', '')).endswith('MPa') else str(ip.get('T'))],
            ['Mixed-Mode Exponent (η)', f"{ip.get('eta', '1.5')}"],
        ]

        t_inter = ax_inter.table(
            cellText=table_data_inter,
            cellLoc='center',
            loc='center',
            colWidths=[0.65, 0.45],
        )
        t_inter.auto_set_font_size(False)
        t_inter.set_fontsize(8.0)
        t_inter.scale(1.0, 1.45)

        for (r, c), cell in t_inter.get_celld().items():
            if r == 0:
                cell.set_facecolor('#EFE5D8')
                cell.set_text_props(weight='bold')
            else:
                cell.set_facecolor('#FCF9F5' if c == 1 else '#FFFFFF')
            cell.set_edgecolor('#CCCCCC')
            cell.set_linewidth(0.6)

        ax_inter.set_title('Cohesive Zone Interface (Traction-Separation)', fontsize=11.5, fontweight='bold', pad=8)

    plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
    plt.close()


def plot_with_pyvista(
    grid_a,
    grid_b,
    name_a: str,
    name_b: str,
    output_path: str,
    dpi: int = 300,
    fig_width_in: float = 6.0,
    fig_height_in: float = 6.0,
    color_a: str = '#3B75AF',
    color_b: str = '#D63426',
    title: str = None,
):
    """Render 300 DPI material matrix screenshot using PyVista headless offscreen rendering."""
    import pyvista as pv

    pv.OFF_SCREEN = True
    window_width = int(round(fig_width_in * dpi))
    window_height = int(round(fig_height_in * dpi))

    n_a = grid_a.n_cells
    n_b = grid_b.n_cells
    n_total = n_a + n_b
    vol_a = (n_a / n_total) * 100.0
    vol_b = (n_b / n_total) * 100.0

    pl = pv.Plotter(off_screen=True, window_size=[window_width, window_height])
    pl.set_background('white')

    pl.add_mesh(grid_a, color=color_a, show_edges=False)
    pl.add_mesh(grid_b, color=color_b, show_edges=False)

    display_title = title if title else "Material Matrix (Bulk Properties A & B)"
    #pl.add_text(display_title, position='upper_left', color='black', font_size=16)

    # Subtitle with material breakdown
    info_text = (
        f"Blue: Bulk Properties A (Aluminum proxy, {vol_a:.1f}%)\n"
        f"Red:  Bulk Properties B (SiC proxy, {vol_b:.1f}%)"
    )
    pl.add_text(info_text, position=(20, 20), color='black', font_size=12)

    pl.view_xy()
    pl.camera.SetParallelProjection(True)
    pl.reset_camera()
    pl.camera.zoom(0.92)

    pl.screenshot(str(output_path))
    pl.close()


def main():
    parser = argparse.ArgumentParser(
        description="Generate 300 DPI plot of Material Matrix (Bulk Properties A / Aluminum & B / SiC)."
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        default=None,
        help="Input Exodus II mesh file (default: mesh.exo if present, else output_0.e)",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="material_matrix.png",
        help="Output image path (default: material_matrix.png)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Resolution in DPI (default: 300)",
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=['matplotlib', 'pyvista'],
        default='matplotlib',
        help="Plotting engine to use (matplotlib or pyvista; default: matplotlib)",
    )
    parser.add_argument(
        "--show-properties",
        action="store_true",
        help="Display side-by-side constitutive material properties table (matplotlib only)",
    )
    parser.add_argument(
        "--color-a",
        type=str,
        default="#3B75AF",
        help="Hex color for Aluminum proxy / Mat A (default: #3B75AF)",
    )
    parser.add_argument(
        "--color-b",
        type=str,
        default="#D63426",
        help="Hex color for SiC proxy / Mat B (default: #D63426)",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Custom plot title",
    )
    parser.add_argument(
        "--unit",
        type=str,
        default="mm",
        help="Spatial dimension unit for axes (default: mm)",
    )
    parser.add_argument(
        "--GI_c",
        type=float,
        default=0.00228,
        help="Mode I fracture energy GI_c in N/mm (default: 0.00228)",
    )
    parser.add_argument(
        "--GII_c",
        type=float,
        default=0.00097,
        help="Mode II fracture energy GII_c in N/mm (default: 0.00097)",
    )
    parser.add_argument(
        "--N",
        type=float,
        default=75.6,
        help="Normal cohesive strength N in MPa (default: 75.6)",
    )
    parser.add_argument(
        "--T",
        type=float,
        default=19.4,
        help="Shear cohesive strength T in MPa (default: 19.4)",
    )
    parser.add_argument(
        "--eta",
        type=float,
        default=1.5,
        help="Mixed-mode exponent eta (default: 1.5)",
    )

    args = parser.parse_args()

    # Determine input file
    mesh_file = args.input
    if mesh_file is None:
        if os.path.isfile("mesh.exo"):
            mesh_file = "mesh.exo"
        elif os.path.isfile("output_0.e"):
            mesh_file = "output_0.e"
        else:
            print("Error: Could not locate mesh.exo or output_0.e. Please specify -i <path>", file=sys.stderr)
            sys.exit(1)

    print(f"Loading mesh from: {mesh_file}...")
    grid_a, grid_b, name_a, name_b = load_mesh(mesh_file)

    n_a = grid_a.n_cells
    n_b = grid_b.n_cells
    n_total = n_a + n_b
    vol_a = (n_a / n_total) * 100.0
    vol_b = (n_b / n_total) * 100.0

    interface_props = {
        'GI_c': args.GI_c,
        'GII_c': args.GII_c,
        'N': args.N,
        'T': args.T,
        'eta': args.eta,
    }

    print(f"Mesh summary:")
    print(f"  Total elements: {n_total:,}")
    print(f"  {name_a} (Aluminum proxy): {n_a:,} cells ({vol_a:.2f}%)")
    print(f"  {name_b} (SiC proxy):      {n_b:,} cells ({vol_b:.2f}%)")

    print(f"Generating 300 DPI plot using '{args.engine}' -> {args.output}...")
    if args.engine == 'matplotlib':
        plot_with_matplotlib(
            grid_a,
            grid_b,
            name_a,
            name_b,
            args.output,
            dpi=args.dpi,
            color_a=args.color_a,
            color_b=args.color_b,
            title=args.title,
            unit=args.unit,
            show_properties=args.show_properties,
            interface_props=interface_props,
        )
    else:
        plot_with_pyvista(
            grid_a,
            grid_b,
            name_a,
            name_b,
            args.output,
            dpi=args.dpi,
            color_a=args.color_a,
            color_b=args.color_b,
            title=args.title,
        )

    file_size_kb = os.path.getsize(args.output) / 1024.0
    print(f"Successfully generated: {args.output} ({file_size_kb:.1f} KB at {args.dpi} DPI)")


if __name__ == '__main__':
    main()
