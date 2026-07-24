# brb2026/07/24 plot_h5_results.py does not work. This was what we used to plot results with MADA. It seems to show damage field OK. I have not verified it. 

import h5py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import os

def plot_h5_result(filename):
    with h5py.File(filename, "r") as f:
        # Load mesh data
        coords = f["unstructured_mesh/coords"][:]
        conn = f["unstructured_mesh/connectivity"][:]
        
        # Load field data (taking the last time step)
        d_nodal = f["unstructured_mesh/node_fields/stimuli/d/data"][-1, :]
        stress_yy = f["unstructured_mesh/element_fields/responses/cauchy_stress/data"][-1, :, 1]
        
        # Split quads into triangles
        triangles = np.vstack([conn[:, [0, 1, 2]], conn[:, [0, 2, 3]]])
        
        # Plotting
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        
        # Plot Damage Field
        t0 = tri.Triangulation(coords[:, 0], coords[:, 1], triangles)
        tpc0 = axes[0].tripcolor(t0, d_nodal, cmap="Reds", shading="flat")
        fig.colorbar(tpc0, ax=axes[0], label="Damage (d)")
        axes[0].set_title("Damage Field (Last Timestep)")
        axes[0].set_aspect('equal')
        
        # Plot Stress YY
        stress_tri = np.concatenate([stress_yy, stress_yy])
        tpc1 = axes[1].tripcolor(t0, stress_tri, cmap="jet", shading="flat")
        fig.colorbar(tpc1, ax=axes[1], label="Stress YY")
        axes[1].set_title("Cauchy Stress YY (Last Timestep)")
        axes[1].set_aspect('equal')
        
        plt.tight_layout()
        out_name = os.path.basename(filename).replace(".h5", ".png")
        plt.savefig(out_name, dpi=300)
        print(f"Saved plot to {out_name}")
        plt.close()

results_dir = "/home/bbrunsvik/Documents/ains/code/compgen/demos/output" # "output"
h5_files = [f for f in os.listdir(results_dir) if f.endswith(".h5")]

for h5_file in h5_files:
    print(f"Plotting {h5_file}...")
    plot_h5_result(os.path.join(results_dir, h5_file))