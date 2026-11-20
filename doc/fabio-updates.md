# What's new in `fabio` (PR #8)

> Change notes for the `fabio` branch, merged into `main` as PR #8
> (`17fac2f`). Baseline: `main` at `41109cf` (PR #6, 2026-03-13).
> **Later changes** (3D Voronoi, the three resolutions, periodic face snapping,
> length parameters as fractions of the cell, …) are in
> [3d-updates.md](3d-updates.md); where they replace something below, it is
> marked *(changed, see 3d-updates)*.

## At a glance

1. **More generators**: particle/disk packings, Voronoi grains, statistical
   reconstruction (`mcrpy`).
2. **Better solutions**: smooth-interface meshing (Sculpt `-ims`) and corrected
   mechanics constraints in the MOOSE templates.
3. **Robust batch runs**: failed meshes are redrawn, hung solves are killed,
   bad meshes are rejected before solving. Ask for $N$ results, get $N$ (or a
   clear report of why not).
4. **Random materials**: per-property distributions (`uniform`, `loguniform`).
5. **Boolean images everywhere**: filters reject non-binary input instead of
   silently corrupting it.

## 1. Generators (`compgen/gen.py`)

All parameters are `generator.params` keys; `[min, max]` values are sampled per
draw; all generators take `random_seed`.

- **`ParticleGenerator(N, vf, kind, shape_params, buffer=None, dt, max_iter, tol)`**
  - `kind`: 2D `laminae2`/`disks`/`ellipses`; 3D `laminae3`/`fibers`/`spheres`/`spheroids`.
  - `shape_params`: mean/half-width pairs (`size_*`, `ratio_*`, `theta_*`,
    `az_*`/`el_*`; `*_m` mean, `*_s` half-width).
  - `buffer=None`: penetrable (overlaps allowed, realized fraction below `vf`).
    `buffer > 0`: impenetrable, clearance reached approximately by overlap
    relaxation; a draw that does not converge is redrawn.
- **`VoronoiGenerator(N, grain_size, thickness, lloyd_iter=0, invert=True)`**:
  periodic grain structures with boundaries of width
  `thickness * grain_size`; `lloyd_iter` makes grains more equiaxed; `invert`
  randomly swaps the phases. *(3D modes and exact walls: see 3d-updates.)*
- **`Reconstruction2D(N, target_path, descriptors=None, limit_to=16)`**:
  reconstruction from one `.npy` target or a folder of them.

## 2. Better solutions

**Meshing** (`compgen/mesh.py`): the binary image is reduced to volume
fractions and meshed through Sculpt's `-ims` path, with fewer staircase
artifacts at phase boundaries (matters most for plasticity). PR #8 drove this
with `generator.params.refinement`. *(Changed: `refinement` is gone, see
3d-updates.)*

**Mechanics constraints** (`compgen/physics/**/template.i`):

- **Rigid-rotation pins removed** (2D `up`, 3D `up`/`forward`). They did not
  remove rotation from the periodic fluctuation field, they only applied
  spurious point forces. Translation is still fixed by the `center` node.
- **2D plastic**: $F_{xy} = 0$ replaces $P_{xy} = 0$, so the Cauchy stress is
  diagonal and the cell cannot rotate (before: Cauchy shear up to ~3% of the
  load on anisotropic cells).
- **3D plastic**: same convention as 2D ($F_{xy} = F_{xz} = F_{yz} = 0$), so 2D
  and 3D results are comparable.
- **2D plastic records $\sigma_{zz}$** (plane strain, roughly 40–80% of
  $\sigma_{xx} + \sigma_{yy}$) as the extra stimulus `cauchy_stress_zz`;
  `cauchy_stress` keeps its in-plane components.

## 3. Robust batch runs

- **Backfill** (`runner.py`): structures are drawn lazily up to
  `max_attempts_factor × number`, with at most `nthreads` in flight. A mesh
  failure is redrawn; an executor failure uses its slot and is dropped.
  Predefined structures (`FromNumpyGenerator`) are never redrawn: a failure
  stays in place as `-1`.
- **Filter config errors** (`FilterInputError`, `TypeError`) abort the run
  instead of being redrawn forever.
- **Mesh gating** (`mesh.py`): `SculptError`, and `MeshQualityError` when the
  minimum scaled Jacobian is $\le 0.1$; both trigger a redraw.
- **MOOSE timeout** (`moose.py`, `moose.timeout` in minutes): kills the whole
  process group, not just `mpirun`. A structure with a failed load case counts
  as failed unless `moose.allow_partial_loads` is set.

## 4. Random materials (`compgen/materials.py`)

Each property is a `[low, high]` interval (uniform) or an object with a
`distribution`. `loguniform` gives each decade equal weight (strictly positive
intervals only):

```json
"youngs_modulus": {"interval": [1.0, 1000.0], "distribution": "loguniform"},
"poissons_ratio": [-0.2, 0.49]
```

## 5. Boolean images (`compgen/filters.py`, `compgen/utils.py`)

- Filters take and return `bool`; non-binary input raises
  `NonBinaryImageError` (a `FilterInputError`).
- `make_orthogonal` and `make_periodic` moved from `gen.py` to `filters.py`.
  `make_periodic` gained opt-in `shift=True` (circular shift that minimizes
  the overwritten seam).
- New `defeature`: removes small islands of both phases, with periodic
  labeling.
- `mean_filter`: periodic smoothing.
- `FromNumpyGenerator` returns `bool`; `utils.standardize_image` enforces the
  shape/dtype contract.

*(Filter lengths and margins changed units, see 3d-updates.)*

## Demos

`demos/2d_mesher.py`: generate, filter and mesh a 2D particle structure without
running the solver, and render the mesh to PNG.
