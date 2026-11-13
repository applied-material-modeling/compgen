# Copyright 2026, UChicago Argonne, LLC
# All Rights Reserved
# Software Name: compgen
# By: Argonne National Laboratory
# OPEN SOURCE LICENSE (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import os
import sys

sys.path.append("..")

import numpy as np
import matplotlib.pyplot as plt

from compgen import mesh, runner

# Toggle to False to skip CUBIT/Sculpt and emit a plain voxel mesh instead.
RUN_SCULPT = True

# Where to drop the mesh + preview image (next to this script, regardless of cwd).
HERE = os.path.dirname(os.path.abspath(__file__))
MESH_OUT = os.path.join(HERE, "2d_mesher.exo")
PREVIEW_OUT = os.path.join(HERE, "2d_mesher_input.png")
MESH_IMG_OUT = os.path.join(HERE, "2d_mesher_output.png")

# A meshing-only config: generation + filtering + mesh, no executor/materials.
# `refinement > 0` exercises fabio's smooth-interface path: the generator emits a
# fine image at N * 2**refinement and the mesher coarsens it to N as fractional
# volume fractions (Sculpt -ims). Set refinement to 0 for the direct binary path.
CONFIG = {
    "L": [1.0, 1.0],
    "generator": {
        "type": "gen.ParticleGenerator",
        "params": {
            "random_seed": 0,
            "N": [128, 128],
            "refinement": 3,
            "vf": 0.3,
            "kind": "ellipses",
            "shape_params": {
                "size_m": [0.15, 0.50],
                "size_s": [0.0, 0.5],
                "ratio_m": [0.5, 1.0],
                "ratio_s": [0.0, 0.5],
            },
            # buffer > 0 => impenetrable particles (min surface-to-surface
            # clearance, enforced by overlap-minimization). None => penetrable.
            "buffer": 0.6,
            "max_iter": 2000,
            "dt": 0.0001,
        },
    },
    "filtering": [
        {"type": "filters.make_periodic", "params": {"margin": 8, "shift": True}},
    ],
    "mesh": {
        "type": "mesh.generate_mesh",
        "params": {"run_sculpt": RUN_SCULPT, "quality_check": RUN_SCULPT},
    },
    "mesh_file": MESH_OUT,
    # Mirrors elasticity/config.json; only consulted when RUN_SCULPT is True.
    # Requires $CUBIT_DIR to point at a CUBIT/Sculpt install.
    "sculpt": {
        "executable": "${CUBIT_DIR}/bin/psculpt",
        "mpi": "${CUBIT_DIR}/bin/mpiexec",
        "rank_command": "-np",
        "epu": "${CUBIT_DIR}/bin/epu",
        "environment": {
            "OPAL_LIBDIR": "${CUBIT_DIR}/bin/mpi/lib",
            "OPAL_PREFIX": "${CUBIT_DIR}/bin/mpi",
        },
        "options": ["-df", "0", "-S", "3", "-CS", "5"],
    },
    "mpi": {"executable": "mpirun", "rank_command": "-np", "ranks": "2"},
    # Default scratch location (local /tmp). The mesher moves its result to
    # `mesh_file` with shutil.move, which handles a temp dir and an output that
    # live on different filesystems (e.g. local /tmp scratch vs. an NFS project).
    "storage": {"delete_temp_dir": True},
}


def _expandvars(obj):
    """Expand ``${VAR}`` in every string in a nested config.

    The real pipeline gets this for free: ``utils.load_json`` runs
    ``os.path.expandvars`` over the raw JSON text before parsing. Because this
    demo builds ``CONFIG`` as an inline dict, we have to do the same expansion
    ourselves so ``${CUBIT_DIR}`` in the ``sculpt`` section resolves to a real
    path instead of reaching ``subprocess`` verbatim.
    """
    if isinstance(obj, dict):
        return {k: _expandvars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expandvars(v) for v in obj]
    if isinstance(obj, str):
        return os.path.expandvars(obj)
    return obj


CONFIG = _expandvars(CONFIG)


def save_mesh_image(mesh_path, out_png):
    """Render the generated 2D mesh to a PNG: element edges filled by material.

    Reads the Exodus mesh with pyvista (same reader the pipeline uses for its
    quality check) and draws the elements with matplotlib -- which renders
    reliably on a headless node, unlike VTK's off-screen OpenGL path. The Exodus
    reader returns one block per material, so we color each block distinctly.
    """
    import pyvista
    from matplotlib.collections import PolyCollection

    def leaves(dataset):
        # read_exodus nests the element blocks inside MultiBlock(s); flatten to
        # the leaf grids (one per material block).
        if isinstance(dataset, pyvista.MultiBlock):
            out = []
            for i in range(dataset.n_blocks):
                out += leaves(dataset[i])
            return out
        return [dataset] if dataset is not None else []

    blocks = leaves(pyvista.read_exodus(mesh_path))

    polys, colors, pts_all = [], [], []
    cmap = plt.get_cmap("tab10")
    for bi, blk in enumerate(blocks):
        pts = np.asarray(blk.points)[:, :2]  # 2D mesh -> project onto x-y
        if pts.size:
            pts_all.append(pts)
        color = cmap(bi % 10)
        for conn in getattr(blk, "cells_dict", {}).values():
            polys.extend(pts[conn])  # (ncells, k) -> list of (k, 2) polygons
            colors.extend([color] * len(conn))

    fig, ax = plt.subplots()
    ax.add_collection(
        PolyCollection(polys, facecolors=colors, edgecolors="k", linewidths=0.2)
    )
    if pts_all:
        allpts = np.concatenate(pts_all)
        ax.set_xlim(allpts[:, 0].min(), allpts[:, 0].max())
        ax.set_ylim(allpts[:, 1].min(), allpts[:, 1].max())
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"output mesh ({len(polys)} elements, {len(blocks)} blocks)")
    fig.savefig(out_png, bbox_inches="tight", dpi=150)
    plt.close(fig)


def main():
    """Generate a structure, filter it, mesh it, and render the mesh to PNG."""
    if RUN_SCULPT and not os.environ.get("CUBIT_DIR"):
        print(
            "WARNING: RUN_SCULPT is True but $CUBIT_DIR is not set -- Sculpt will "
            "likely fail. Set $CUBIT_DIR, or flip RUN_SCULPT to False for a plain "
            "voxel mesh.\n"
        )

    # 1) Structure. setup_generator handles the `refinement` knob: it pops it from
    #    params, scales N to the fine resolution, and records it on the generator.
    print("Generating structure...")
    generator = runner.setup_generator(CONFIG["generator"])
    refinement = generator.refinement
    img = next(generator)  # fine image at N * 2**refinement
    print(f"  drew fine image of shape {img.shape} (refinement={refinement})")

    # 2) Filters -- applied on the fine image, exactly as run_single does.
    for spec in CONFIG["filtering"]:
        filter_func = runner.get_object_from_module(spec["type"])
        img = filter_func(img, **spec.get("params", {}))
        print(f"  applied {spec['type']}")

    # Save a preview of the material image at mesh resolution (coarsened when
    # refining), so you can eyeball what got meshed.
    factor = 2**refinement
    coarse = (
        mesh.downsample_vfrac(img, factor) > 0.5
        if refinement
        else np.asarray(img, bool)
    )
    plt.imshow(coarse.T, cmap="gray", origin="lower")
    plt.axis("off")
    plt.title(f"input structure ({coarse.shape[0]}x{coarse.shape[1]})")
    plt.savefig(PREVIEW_OUT, bbox_inches="tight", dpi=150)
    plt.close()
    print(f"  wrote input preview -> {PREVIEW_OUT}")

    # 3) Mesh -- and stop. No executor, no materials, no solve.
    print("Meshing...")
    mesh_func = runner.get_object_from_module(CONFIG["mesh"]["type"])
    mesh_func(
        img,
        CONFIG["mesh_file"],
        L=CONFIG["L"],
        settings=CONFIG,
        refinement=refinement,
        **CONFIG["mesh"].get("params", {}),
    )
    print(f"  mesh written -> {MESH_OUT}")

    # 4) Render the mesh we just wrote, so you can eyeball the elements without
    #    opening Paraview.
    print("Rendering mesh image...")
    save_mesh_image(MESH_OUT, MESH_IMG_OUT)
    print(f"  wrote mesh image -> {MESH_IMG_OUT}")

    print("\nDone (executor not run).")


if __name__ == "__main__":
    main()
