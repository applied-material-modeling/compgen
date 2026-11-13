# What's new in `fabio` (vs. the branch point)

> Change notes for the `fabio` branch — an overview for reviewers and users of
> what changed and why, ahead of the merge into `main`.

**Baseline:** everything below is described relative to `main` as it stood when
`fabio` was branched — commit `41109cf` *"Enforce tests, linting, and formatting
(#6)"*, dated **2026-03-13**. That is the point of comparison; later commits that
landed on `main` independently are **not** covered here (they're handled in the
merge notes).

Scope of the branch: **21 commits**, **54 files**, ~**+2850 / −505** lines across
the library, tests, and physics templates.

---

## At a glance (the casual version)

`fabio` turns the pipeline from "generate a structure, mesh it, solve it once"
into a **robust, batch-oriented generator** that can be trusted to produce *N*
usable results unattended. Five themes:

1. **More ways to make a microstructure.** New generators for particle/disk
   packings, Voronoi grain structures, and statistical reconstruction from a
   target (via `mcrpy`).

2. **Higher-quality solutions.** Two independent improvements to what comes out
   of the solver: (a) *better meshing* — the smooth-interface path produces
   fewer staircase artifacts at phase boundaries, which matters most for
   plasticity, where jagged interfaces create spurious stress concentrations;
   and (b) *corrected mechanics constraints* — the templates dropped extra
   pinned nodes that over-constrained the periodic fluctuation field, and 2D
   plasticity now applies a load whose Cauchy stress is diagonal in the load
   axes (as 3D already did), with the out-of-plane stress σ_zz recorded.

3. **It doesn't fall over anymore.** A generated structure that fails to mesh is
   automatically *replaced* (draw another) instead of silently dropping a result;
   a solve that hangs is killed on a timeout; mesh quality is checked before
   wasting a solve on it. You ask for 10 results, you get 10 (or a clear report
   of why not). *(Auto-replacement covers generator and mesher failures; retrying
   a failed **executor** run is left for future work. Predefined structures, e.g.
   from `FromNumpyGenerator`, are never replaced: a failure stays in place as `-1`
   so results line up with the input file. A structure with any failed load case
   counts as failed, unless `moose.allow_partial_loads` is set.)*

4. **Richer randomization.** Material properties can be drawn from configurable
   per-property distributions instead of single fixed values.

5. **One consistent "image" everywhere.** Structures are boolean (two-phase)
   from end to end. Filters reject anything that isn't binary instead of quietly
   corrupting it, so a mistake fails loudly and early.

Everything is covered by new test suites, and the tests run deterministically on
CPU.

---

## Breakdown by theme

Same five themes as *At a glance*, in the same order. A single code module can
serve more than one theme, so a few modules appear under more than one heading
(each under a labeled sub-section).

### 1. More ways to make a microstructure — `compgen/gen.py`
The largest change (~+990 lines). New generator classes. Every parameter below is
also a config-file key under `generator.params`; a value given as `[min, max]`
(where noted) is sampled per draw. All accept `random_seed`.

- **`ParticleGenerator(N, vf, kind, shape_params, buffer=None, dt=0.001,
  max_iter=1000, tol=1e-9)`** — places (and optionally rearranges) particles.
  Requires PyTorch: `pip install compgen[particles]`.
  - `N` — grid resolution; must be equal in every dimension.
  - `vf` — target volume fraction. Particles are added until their *analytic*
    areas/volumes sum to `vf`, so it is the realized fraction **only for
    impenetrable particles** (`buffer > 0`, non-overlapping); with penetrable
    particles (`buffer=None`) overlaps are double-counted in that sum, so the
    rasterized structure lands *below* `vf`. Scalar or `[min, max]`.
  - `kind` — shape: 2D `laminae2`/`disks`/`ellipses`; 3D `laminae3`/`fibers`/
    `spheres`/`spheroids`.
  - `shape_params` — per-shape geometry as mean/spread pairs: `size_*` (axis
    length), `ratio_*` (aspect ratio), `theta_*` (2D angle), `az_*`/`el_*` (3D
    orientation); `*_m` = mean, `*_s` = half-width (omit `_s` for a fixed value).
  - `buffer` — min surface-to-surface clearance; **`None` = penetrable (overlaps
    allowed, no rearrangement); `>0` = impenetrable** (overlap-minimization on).
  - `dt`, `max_iter`, `tol` — overlap-minimization controls (used only when
    `buffer` is set). See `demos/2d_mesher.py` for a worked config.

  `buffer` is an **approximate** target: the clearance is reached by iterative
  overlap-relaxation (gradient steps over `max_iter` iterations toward tolerance
  `tol`), not a hard geometric constraint, so the realized minimum clearance only
  *approaches* the requested value — and a draw that fails to converge is rejected
  and redrawn.

- **`VoronoiGenerator(N, grain_size, thickness, lloyd_iter=0, invert=True)`** —
  periodic Voronoi grain structures.
  - `grain_size` — grain diameter in normalized `[0, 1]` (scalar or `[min, max]`);
    seed count derives as `round((1 / grain_size) ** dim)`.
  - `thickness` — boundary thickness as a fraction of grain size (scalar or range).
  - `lloyd_iter` — Lloyd relaxation iterations (`0` = irregular Poisson-Voronoi;
    a few = more equiaxed, uniform grains). Like the other params it may be given
    as `[min, max]` and sampled per draw; the sampled value is rounded to an
    integer.
  - `invert` — randomly swap the two phases (default `True`).

- **`Reconstruction2D(N, target_path, descriptors=None, limit_to=16)`** —
  statistical reconstruction via `mcrpy` (the "incorporated mcrpy" + "multi-target
  reconstruction" work).
  - `target_path` — a `.npy` target, or a folder of `.npy` targets (multi-target).
  - `descriptors` — `{name: weight}` map, default `{"Correlations": 1.0}`.
  - `limit_to` — descriptor-convolution limit.

### 2. Higher-quality solutions — `compgen/mesh.py`, physics templates, `compgen/runner.py`
Two independent improvements to what the solver receives.

**(a) Better meshing — smooth interface** (`mesh.py`, ~+210 lines):

- **`refinement` / `downsample_vfrac`** — the smooth-interface path: a fine
  binary image at `N·2**refinement` is coarsened into fractional volume fractions
  and meshed via SCULPT's `-ims` path, instead of the direct binary `-ice` path.
  Fewer staircase artifacts at phase boundaries (matters most for plasticity).
- **`normalize_mesh`, `_write_micro`, `sculpt(..., sculpt_input="ice"|"ims")`** —
  the "new meshing style" refactor supporting both paths.
- **Refinement plumbing** (`runner.py`) — the `refinement` knob is read from the
  generator config and threaded through to the mesher; the generator emits the
  fine image while output is projected back to the `N` grid.

`refinement` lives under `generator.params` (the runner pops it and tells the
mesher the factor). Example from `../compgen-tests/elasticity/config.json` — a
128² Voronoi structure meshed through the smooth-interface path at refinement 2:

```json
"L": [1.0, 1.0],
"generator": {
    "type": "gen.VoronoiGenerator",
    "params": {
        "random_seed": 0,
        "N": [128, 128],
        "refinement": 2,
        "grain_size": [0.2, 0.6],
        "thickness": [0.05, 0.3],
        "lloyd_iter": [1.0, 5.0]
    }
},
"mesh": {
    "type": "mesh.generate_mesh",
    "params": {"run_sculpt": true}
}
```

At refinement 2 the generator rasterizes at 512² (128·2²) and `downsample_vfrac`
coarsens it to 128 fractional volume fractions for Sculpt's `-ims` path.

> **Known limitation.** `refinement` scales `N` only. Parameters measured in
> pixels are not scaled: `SpinodalGenerator.l`, `mean_filter.radius` and
> `make_periodic.margin`. With the same config, features come out `2**refinement`
> times smaller relative to the domain, so refinement changes the microstructure,
> not just the interface smoothness. Until this is fixed, multiply those
> parameters by `2**refinement` by hand when you turn refinement on. A future
> version will scale them automatically. `refinement` also requires a generator
> with an `N` parameter; using it with e.g. `FromNumpyGenerator` now raises an
> error.

**(b) Corrected mechanics constraints** (`compgen/physics/**/template.i`):

- **Removed the rigid-rotation pins.** 2D dropped the `up` nodeset and its
  `apply_up_x` Dirichlet BC; 3D dropped the `up`/`forward` nodesets and their
  `apply_up_*` BCs. Rigid *translation* is still removed by pinning the `center`
  node. The displacement variables hold the periodic fluctuation, which cannot
  contain a rigid rotation, so the pins did not remove rotation; they only forced
  the fluctuation to match at two nodes, which applies spurious point forces in a
  two-phase cell.
- **2D plastic: macroscopic constraint changed so the Cauchy stress is diagonal.**
  `constraint_types` (read column-major: `xx yx zx xy yy zy xz yz zz`) went from
  `stress stress none stress stress ...` to `stress stress none strain stress ...`:
  F_xy = 0 replaces P_xy = 0. With all four entries stress-controlled, P was
  diagonal but the cell could rotate, giving Cauchy shear stress of up to ~3 % of
  the load on anisotropic cells. With F lower triangular and P_yx = 0, the Cauchy
  stress J⁻¹ P Fᵀ is diagonal and rigid rotation is fixed.
- **3D plastic: same constraint convention as 2D.** 3D used the mirror choice
  (F_yx = F_zx = F_zy = 0). It now fixes F_xy = F_xz = F_yz = 0 with
  P_yx = P_zx = P_zy = 0, matching 2D. Both choices give a diagonal Cauchy
  stress, but they leave the cell with a slightly different rigid rotation
  (about 0.01 rad), which on strongly anisotropic structures changes strains by
  up to ~17 %. Using one convention keeps 2D and 3D results comparable. No 3D
  plastic data had been generated with the old convention.
- **2D plastic: out-of-plane stress now recorded.** The 2D model is plane strain
  (no stretching along z), so a reaction stress σ_zz builds up: roughly 40–80 %
  of σ_xx + σ_yy, and it affects yielding. It is now stored as an extra stimulus,
  `cauchy_stress_zz` (generalized value and full field). The existing
  `cauchy_stress` stimulus keeps its three in-plane components, so existing
  readers are unaffected. σ_zz cannot be reconstructed reliably from the stored
  in-plane fields in plasticity, so older 2D plastic datasets do not contain it.
- Plastic and thermal-expansion templates: dead-block removal and whitespace
  consistency.

### 3. It doesn't fall over anymore — `compgen/runner.py`, `compgen/mesh.py`, `compgen/moose.py`
The reliability rework, spread across three modules.

**Orchestration** (`runner.py`, ~+320 lines):

- **Bounded-window backfill pool.** Instead of `zip(...) + pool.map`, `run()`
  draws structures lazily up to a budget (`cap = max_attempts_factor × number`)
  and keeps ≤ `nthreads` tasks in flight under the invariant
  `succeeded + in_flight ≤ number`. This delivers exactly `number` successes and
  lets the pool drain cleanly (`close()/join()`, nothing to `terminate()`).
- **Failure sentinels** `MESH_FAILED` / `EXEC_FAILED` (pickling-safe instances):
  mesh failures are *backfilled* (retry with a fresh draw); executor failures
  consume a slot and are *dropped* (executor retry is future work).
- **Non-retryable filter errors.** `FilterInputError`/`TypeError` from a filter
  abort the run (redrawing can't fix a config error); the filter chain is also
  resolved up front so a bad `type` fails immediately, not per-worker.
- **Logging** — centralized in `setup_logging(config)`, called from both `run()`
  and `run_single` (so pool workers initialize logging themselves).
  *(This piece was aligned with `main`'s later refactor during merge prep.)*

**Mesh gating** (`mesh.py`):

- **New exceptions** `SculptError` and `MeshQualityError`, surfaced to the runner
  so meshing failures become retryable `MESH_FAILED`s.
- **`mesh_quality(exofile, min_qual=0.1)`** — a post-mesh quality gate; a bad mesh
  is rejected before a solve is attempted (the "mesher retry mechanism").

**Solver execution** (`moose.py`, ~+120 lines):

- **`_run_moose_command(cmd, env, capture, timeout_s)`** — runs MOOSE in its own
  session and **kills the whole process group on timeout** (plain
  `subprocess.run(timeout=)` only kills the direct child, e.g. `mpirun`, orphaning
  the real workers). Timeout is configured in minutes (`moose.timeout`; ≤0 = off).
- **`problem_id` tagging** — failures/timeouts are greppable per problem.

### 4. Richer randomization — `compgen/materials.py`
(~+160 lines.) **Per-property random distributions:**

- **`PropertySpec(low, high, distribution)`** plus parsing/validation helpers
  (`_parse_interval`, `_parse_distribution`, `_parse_spec`, `_sample`).
- Each property can specify an `interval` and an optional `distribution` (with
  accepted-spelling normalization and clear errors for unknown names/keys),
  instead of a single fixed value.

**Distributions.** Two are supported over an interval `[low, high]`:

- `uniform` (default) — every value in the interval is equally likely.
- `loguniform` — the *logarithm* is uniform, i.e. each draw is
  `exp(uniform(log(low), log(high)))`. Every **order of magnitude** in the
  interval gets equal weight, so `[1, 1000]` spends as many draws in `[1, 10]` as
  in `[100, 1000]` — the right choice for properties that span decades (stiffness
  or conductivity *contrast* between phases). Requires a **strictly positive**
  interval (`log` of `≤ 0` is undefined); a degenerate `low == high` returns
  exactly that value. Every property consumes one random draw, degenerate or
  not, so seeded runs reproduce the same material streams as before.

A property is written either as a bare `[low, high]` (uniform) or as an object
with an explicit `distribution`:

```json
"material_A": {
    "type": "materials.RandomMaterialGenerator",
    "params": {
        "youngs_modulus": {
            "interval": [1.0, 1000.0],
            "distribution": "loguniform"
        },
        "poissons_ratio": [-0.2, 0.49]
    }
}
```

Here `youngs_modulus` is drawn log-uniformly across three decades, while
`poissons_ratio` uses the plain-interval (uniform) shorthand.

### 5. One consistent "image" everywhere — `compgen/filters.py`, `compgen/gen.py`, `compgen/utils.py`
Boolean (two-phase) images from end to end, enforced at every boundary.

**Filters** (`filters.py`, ~+250 lines) — **take and return `bool`**:

- **`_as_binary(img, name)`** — rejects any non-{0,1} input rather than coercing
  it (different filters would reduce it differently). Backed by two new
  exceptions: **`FilterInputError`** and **`NonBinaryImageError`**.
- **`make_orthogonal`** and **`make_periodic`** — moved here from `gen.py`.
  `make_periodic` gained an opt-in `shift=True` option that circular-shifts each
  axis to minimize the seam-overwrite cost before enforcing periodicity. The
  default is `shift=False`, so existing configs produce the same structures as
  before.
- **`defeature`** — removes connected islands below a size threshold (both
  phases), with periodic (toroidal) connected-component labeling so a feature
  that wraps the domain edge counts as one.
- **`mean_filter`** — gained periodic (wrap-padded) smoothing.

**Generators** (`gen.py`):

- **`FromNumpyGenerator`** now normalizes its output to `bool` (binarizes
  grayscale input), so loaded structures obey the same contract as generated ones.
- `make_orthogonal` **moved out** of `gen.py` into `filters.py` (above).

**Utilities** (`utils.py`):

- **`standardize_image(image, shape=None, dtype=None)`** — the single choke-point
  that enforces the shape/dtype (bool) contract used by generators and filters.

---

## Demos
- **`demos/2d_mesher.py`** — generate a 2D structure, filter it, and emit a `.exo`
  mesh **without running the executor** (mirrors `run_single`'s generate → filter
  → mesh stages, then stops). Config mirrors the particle case of
  `../compgen-tests/thermal/randmat_thermal/randmat_thermal_particles`
  (generator/filtering/mesh/sculpt, no executor/materials): `ParticleGenerator`
  with **impenetrable** ellipses (`buffer=0.6` → overlap-minimized clearance),
  then `make_periodic`. `RUN_SCULPT=True` uses CUBIT/Sculpt (`-ims` smooth
  interface when `refinement > 0`, needs `$CUBIT_DIR`); `RUN_SCULPT=False` writes
  a plain voxel mesh with no external dependency. Requires PyTorch. Writes three
  files next to the script: `2d_mesher.exo` (the mesh), `2d_mesher_input.png`
  (the input structure), and `2d_mesher_output.png` (the rendered mesh).
