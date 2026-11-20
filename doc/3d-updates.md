# What's new since PR #8

> Major changes after PR #8 ([fabio-updates.md](fabio-updates.md)): PR #14 and
> the `3D_voronoi-fix` branch. Details are in the docstrings.

## At a glance

1. **3D Voronoi**: exact periodic walls or struts, with one geometry for 2D and 3D.
2. **Three independent resolutions**: generator, mesh and output grids each
   have their own `N`, replacing `refinement`.
3. **Resolution-independent parameters**: lengths are fractions of the generated
   cell, and margins are in mesh cells.
4. **Periodic meshes MOOSE can solve**: opposite faces are snapped to match
   exactly, and broken meshes are rejected.
5. **Run summary**: failures by reason, timings and utilization at the end of
   every run.

> **Old configs need updating** (see [Migrating a config](#migrating-a-config)):
> `refinement` is gone, `N` and `L` are scalars, `dim` is required, and filter
> lengths changed units.

## 1. `VoronoiGenerator` in 3D

- One geometry in 2D and 3D: the exact periodic tessellation, built from the
  seeds and their periodic copies. Walls have exactly uniform width: a pixel or
  voxel is a wall when it lies within $w/2$ of a Voronoi face, with
  $w$ = `thickness * grain_size`.
- `mode` (3D only): `"faces"` (default) gives walls; `"edges"` gives an
  open-cell strut network, with capsules of diameter $w$ along the Voronoi
  edges.
- A grain that meets its own periodic copy has a boundary there, like any other
  pair of grains.
- `torch` is now a required dependency (it is used by `ParticleGenerator`).

## 2. Three resolutions

| key | meaning |
|---|---|
| `dim` | 2 or 3 (required) |
| `L` | side of the square/cubic domain |
| `generator.params.N` | $N_\text{gen}$: pixels per side of the generated image |
| `mesh.params.N` | $N_\text{mesh}$: mesh cells per side (default $N_\text{gen}$) |
| `output.grid_extractor.params.N` | $N_\text{out}$: output grid cells per side (default $N_\text{mesh}$) |

- **Square/cubic cells only.** Every `N` and `L` is a single number;
  generators and `FromNumpyGenerator` reject other shapes.
- **Generate → mesh.** Each mesh cell gets the exact area/volume fraction of
  material A that it covers, for any ratio $N_\text{gen}/N_\text{mesh}$, and
  Sculpt always meshes these fractions (`-ims`). A finer generator
  ($N_\text{gen} = 4$–$8 \times N_\text{mesh}$) gives smoother interfaces.
- **Mesh → output.** Every field is sampled at the centers of the
  $N_\text{out}$ grid, from the nearest mesh element. `material` is now the
  material of the solved mesh; `material_generated` is the generated image on
  the same grid, for comparison. `add_density` uses `material`.
- **Start-up checks.** The run stops if $N_\text{gen} < N_\text{mesh}$ (the mesh
  cannot be finer than the image), or if `dim`, `L` or a generator shape is
  invalid. It warns if $N_\text{out} < N_\text{mesh}/2$ (sampling then skips most
  mesh cells and aliases). The log records `N_gen -> N_mesh -> N_out`.
- **`make_orthogonal`** mirrors the generated cell into $2 \times 2$
  ($\times 2$) copies that fill the same domain $[0, L]$. Generator parameters
  (`N` and every length) and filter lengths refer to the unreplicated cell, of
  side $L/2$; `L`, `mesh.params.N` and the output `N` refer to the domain,
  which holds $2N_\text{gen}$ pixels per side (the start-up check uses
  $2N_\text{gen} \ge N_\text{mesh}$). The log states this at start-up.

Example (3D, 256³ generated, 96³ mesh, 128³ output):

```json
"dim": 3,
"L": 1.0,
"generator": {"type": "gen.SpinodalGenerator",
              "params": {"N": 256, "vf": [0.1, 0.9], "l": [0.4, 2.0], "bandwidth": [0.25, 0.75]}},
"filtering": [{"type": "filters.make_periodic", "params": {"margin_cells": 2.5}}],
"mesh": {"type": "mesh.generate_mesh",
         "params": {"N": 96, "run_sculpt": true, "max_snap_move": 0.3}},
"output": {"grid_extractor": {"type": "mesh.extract_grid_from_mesh", "params": {"N": 128}}}
```

## 3. Resolution-independent parameters

Changing $N_\text{gen}$ no longer changes the microstructure:

- **Fractions of the generated cell**: `SpinodalGenerator.l`, the
  `TwoPointGenerator` lengths, `mean_filter.radius` (the old 3 pixels at
  $N = 128$ is `0.0234`), and `defeature.min_size` (now the radius of the
  threshold disk/ball).
- **Mesh cells**: `make_periodic.margin_cells` (was `margin`, in pixels)
  overwrites $\lceil$`margin_cells`$\cdot N_\text{gen}/N_\text{mesh}\rceil$ pixel
  layers. Use at least 2 with face snapping.
- The runner passes $N_\text{gen}$ and $N_\text{mesh}$ of the unreplicated cell
  to the filters, so these sizes are the same before and after
  `make_orthogonal`.
- New filter options: `mean_filter` `method="fft"` (exact and 7–30× faster,
  cost independent of the radius); `make_periodic` `center=True` (splits the
  seam jump over both ends of the copied block; use with `shift=True`).

## 4. Periodic meshes MOOSE can solve (`compgen/mesh.py`)

- **Face snapping** (`mesh.params.max_snap_move`, off by default). Sculpt
  smooths opposite faces differently, and even a $10^{-3}$ mismatch can stop
  MOOSE's periodic BCs from converging. The max-face nodes are moved onto their
  min-face partners, by at most `max_snap_move` × element size. A mesh is
  rejected and redrawn when its faces cannot be paired: non-flat faces, node
  counts that differ, nodes without a mutual nearest partner, side topology
  that differs, or a move above the cap. Needs flat faces (Sculpt `-S 2`/`-S 3`)
  and `margin_cells >= 2`. In tests at $N_\text{mesh} = 32$–$128$ it removed
  every executor failure (0 of 116 structures, against 8 of 20 before).
- **Non-finite node coordinates** (Sculpt sometimes emits NaN nodes) are always
  rejected.
- The Jacobian check runs after snapping, on the mesh MOOSE sees.

## 5. Run summary (`compgen/runner.py`)

At the end of every run (also when aborted) the log gets a summary: status,
successes against requested, draws, mesh failures by reason (Sculpt, Jacobian,
each snap check, …) and executor failures, each with its share of attempts,
plus wall time, time per success and worker utilization.

## Notebooks

- `demos/generators_overview.ipynb`: samples from every generator in 2D and 3D.
- `demos/generator_viewer.ipynb`: one sample from a pasted `generator` and
  `filtering` config, with the drawn parameters and what each filter changed.

## Migrating a config

| old | new |
|---|---|
| `"L": [1, 1, 1]` | `"dim": 3`, `"L": 1` |
| `"N": [32, 32, 32], "refinement": 3` | `generator.params.N = 256`, `mesh.params.N = 32`, `output.grid_extractor.params.N = 32` |
| `make_periodic` `"margin": 2` (pixels) | `"margin_cells"` (mesh cells) |
| `mean_filter` `"radius": 3` (pixels) | `"radius": 3 / N` |
| `defeature` `"min_size": 20` (cells) | radius $r$ with $\pi (rN)^2 \approx 20$ |
| `SpinodalGenerator` `"l"` (pixels) | `"l" / N` |
