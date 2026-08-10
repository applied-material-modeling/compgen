#!/usr/bin/env python3

# brb2026/07/24 I had Claude make this based on plot_h5_results_mada_style.py and plot_h5_results.py. I have not verified it. 

import argparse
import os
from pathlib import Path

import h5py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as tri

def plot_h5_result(filename, time_index=-1, output_path=None):
    """
    Plot comprehensive results from an HDF5 fracture simulation file.
    
    Args:
        filename: Path to .h5 file
        time_index: Time step to plot (default: -1 for last)
        output_path: Optional output path for PNG (default: next to .h5 file)
    """
    with h5py.File(filename, "r") as f:
        # Load mesh data
        coords = f["unstructured_mesh/coords"][:]
        conn = f["unstructured_mesh/connectivity"][:]
        
        # Load field data at specified time step
        damage = f["unstructured_mesh/node_fields/stimuli/d/data"][time_index, :]
        cauchy_stress = f["unstructured_mesh/element_fields/responses/cauchy_stress/data"][time_index, :]
        d_interface = f["unstructured_mesh/element_fields/stimuli/d_interface/data"][time_index, :]

        ### Can use this to see what else is available to plot. 
        # target = "unstructured_mesh/element_fields"
        # for k1 in f[target].keys():
        #     print(k1)
        #     for k2 in f[f"{target}/{k1}"].keys():
        #         print(f"  {k2}")
        
        # Extract stress components
        stress_xx = cauchy_stress[:, 0]
        stress_yy = cauchy_stress[:, 1]
        stress_xy = cauchy_stress[:, 2] if cauchy_stress.shape[1] > 2 else np.zeros_like(stress_xx)
        
        # # Compute von Mises stress (for 2D plane stress)
        # von_mises = np.sqrt(stress_xx**2 - stress_xx*stress_yy + stress_yy**2 + 3*stress_xy**2)
        
    # Split quads into triangles for visualization
    triangles = np.vstack([conn[:, [0, 1, 2]], conn[:, [0, 2, 3]]])
    
    # Create triangulation object
    triang = tri.Triangulation(coords[:, 0], coords[:, 1], triangles)
    
    # Setup figure with 2x3 grid
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
    
    # Add title with file info and stress ranges
    fig.suptitle(
        f"{Path(filename).name} | Time Index: {time_index}\n"
        f"σ_xx: [{stress_xx.min():.3e}, {stress_xx.max():.3e}] | "
        f"σ_yy: [{stress_yy.min():.3e}, {stress_yy.max():.3e}] | "
        f"σ_xy: [{stress_xy.min():.3e}, {stress_xy.max():.3e}]",
        fontsize=12,
        fontweight='bold'
    )
    
    # Helper function to plot
    def plot_field(ax, data, title, cmap, is_nodal=True):
        if is_nodal:
            # Nodal data - use shading='flat' with vertex colors
            tpc = ax.tripcolor(triang, data, cmap=cmap, shading='gouraud')
        else:
            # Element data - duplicate for each triangle
            data_tri = np.concatenate([data, data])
            tpc = ax.tripcolor(triang, data_tri, cmap=cmap, shading='flat')
        
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        return tpc
    
    # Plot 1: Damage Field (nodal)
    ax1 = fig.add_subplot(gs[0, 0])
    tpc1 = plot_field(ax1, damage, 'Damage (d)', 'Reds', is_nodal=True)
    fig.colorbar(tpc1, ax=ax1, label='Damage', fraction=0.046)
    
    # Plot 2: Stress XX (element)
    ax2 = fig.add_subplot(gs[0, 1])
    tpc2 = plot_field(ax2, stress_xx, 'Cauchy Stress σ_xx', 'RdBu_r', is_nodal=False)
    fig.colorbar(tpc2, ax=ax2, label='Stress [Pa]', fraction=0.046)
    
    # Plot 3: Stress YY (element)
    ax3 = fig.add_subplot(gs[0, 2])
    tpc3 = plot_field(ax3, stress_yy, 'Cauchy Stress σ_yy', 'RdBu_r', is_nodal=False)
    fig.colorbar(tpc3, ax=ax3, label='Stress [Pa]', fraction=0.046)
    
    # Plot 4: Stress XY (element)
    ax4 = fig.add_subplot(gs[1, 0])
    tpc4 = plot_field(ax4, stress_xy, 'Cauchy Stress σ_xy (Shear)', 'PuOr_r', is_nodal=False)
    fig.colorbar(tpc4, ax=ax4, label='Stress [Pa]', fraction=0.046)
    
    # Plot 5: Interface Damage (element)
    ax5 = fig.add_subplot(gs[1, 1])
    tpc5 = plot_field(ax5, d_interface, 'Interface Damage (d_interface)', 'Reds', is_nodal=False)
    fig.colorbar(tpc5, ax=ax5, label='Interface Damage', fraction=0.046)
    
    # Plot 6: Mesh visualization
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.triplot(triang, 'k-', lw=0.3, alpha=0.5)
    ax6.plot(coords[:, 0], coords[:, 1], 'ro', markersize=2, alpha=0.6)
    ax6.set_title(f'Mesh Structure\n{coords.shape[0]} nodes, {conn.shape[0]} elements', 
                  fontsize=11, fontweight='bold')
    ax6.set_xlabel('X')
    ax6.set_ylabel('Y')
    ax6.set_aspect('equal')
    ax6.grid(True, alpha=0.3)
    
    # Save figure
    if output_path is None:
        output_path = Path(filename).with_suffix('.png')
    else:
        output_path = Path(output_path)
    
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved plot to {output_path}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Plot comprehensive summary of compgen fracture HDF5 results."
    )
    parser.add_argument(
        "h5_file",
        nargs="?",
        help="Path to .h5 result file (or processes all .h5 files in directory if omitted)"
    )
    parser.add_argument(
        "--time-index",
        type=int,
        default=-1,
        help="Time index to plot (default: -1 for last timestep)"
    )
    parser.add_argument(
        "--output",
        help="Optional PNG output path"
    )
    parser.add_argument(
        "--directory",
        default=".",
        help="Directory to search for .h5 files if h5_file not specified"
    )
    
    args = parser.parse_args()
    
    if args.h5_file:
        # Process single file
        h5_path = Path(args.h5_file).resolve()
        if not h5_path.exists():
            raise FileNotFoundError(f"File not found: {h5_path}")
        
        print(f"Plotting {h5_path.name}...")
        plot_h5_result(h5_path, time_index=args.time_index, output_path=args.output)
    else:
        # Process all .h5 files in directory
        directory = Path(args.directory).resolve()
        h5_files = sorted(directory.glob("*.h5"))
        
        if not h5_files:
            raise FileNotFoundError(f"No .h5 files found in {directory}")
        
        print(f"Found {len(h5_files)} .h5 files in {directory}")
        for h5_file in h5_files:
            print(f"\nPlotting {h5_file.name}...")
            try:
                plot_h5_result(h5_file, time_index=args.time_index)
            except Exception as e:
                print(f"  ✗ Error processing {h5_file.name}: {e}")


if __name__ == "__main__":
    main()