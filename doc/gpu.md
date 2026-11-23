# Running MOOSE on GPUs

compgen can run each physics either with its original MOOSE template (`cpu` mode) or with a GPU
version (`gpu` mode). The GPU templates (`template_gpu.i` next to each `template.i`) use Kokkos
residual/Jacobian assembly and Kokkos materials, and keep the PETSc vectors and matrices on the
device (`-vec_type kokkos`, `aijkokkos` matrices, algebraic multigrid). They need a MOOSE build
with Kokkos enabled for the target device and a PETSc built with Kokkos and hypre for that
device.

## The GPU templates

Every physics has a GPU template that solves the same discrete problem as its CPU template, so
results agree to solver tolerance:

| Physics (2d and 3d) | Kokkos formulation |
| --- | --- |
| `elastic` | QuasiStatic Physics with `use_kokkos = true` (small kinematics, B-bar, strain constraints), `KokkosComputeIsotropicLinearElasticStress` |
| `thermal_expansion` | As `elastic`, with stress constraints and `KokkosComputeThermalExpansionEigenstrain` |
| `plastic` | `KokkosHomogenizedTotalLagrangianStressDivergence` (large kinematics, F-bar, mixed constraints), `KokkosComputeSimoHughesJ2PlasticityStress` |
| `thermal_conductivity` | `KokkosHeatConductionHomogenized` |
| `thermal_conductivity_with_interface` | `KokkosHeatConductionHomogenized` and `KokkosHeatPenaltyInterface` |

The mechanics templates use the Kokkos homogenization system: the macro-gradient scalar
variable and its constraints are assembled on the device. The scalar variable couples to every
displacement degree of freedom, so the linear solver splits it off with a Schur-complement
field split. The displacement block uses PETSc's GAMG: BoomerAMG on that block sometimes
failed on Intel GPUs (the same input would converge on one run and fail with a NaN on the
next). The displacement block is solved accurately in each outer iteration (CG to a relative
tolerance of 1e-4, preconditioned by GAMG with aggressive coarsening off and 3 Chebyshev/Jacobi
smoothing steps), so the outer FGMRES (modified Gram-Schmidt, restart 100) needs only a few
iterations. Applying one GAMG cycle per outer iteration instead took hundreds of outer
iterations and was about 2x slower. `[Problem]/rigid_body_near_null_space_displacements` gives
GAMG the rigid body modes of the displacements as the near nullspace of the displacement split,
along with its block size, which cuts the CG iterations by about 9x. The `plastic` templates
use FGMRES instead of CG for the displacement block, because the large-kinematics F-bar tangent
is not symmetric; if the inner CG of another template stalls, make the same change. The thermal templates
use BoomerAMG on the whole system, with the same Krylov settings. The strain, stress and invariant outputs
are computed by Kokkos materials and aux kernels. For the thermal templates, the fluxes and
gradients written to the output are recomputed on the host from the converged temperature
(output only, after the solve).

`compgen.moose.supports_mode(physics, "gpu")` reports whether a physics has a GPU template; a
physics without one raises a `ValueError` in gpu mode.

## Configuration

Set the mode and device in the `moose` section of the system configuration:

```json
"moose": {
    "executable": "${MOOSE_DIR}/modules/solid_mechanics/solid_mechanics-opt",
    "options": [],
    "mode": "gpu",
    "device": "xpu"
}
```

- `mode`: `"cpu"` (default) or `"gpu"`.
- `device`: the compute device, required in gpu mode (for example `xpu` for Intel GPUs or
  `cuda` for NVIDIA). compgen passes it to MOOSE as `--compute-device=<device>`.
- `executable`: the same applications as in cpu mode (`solid_mechanics-opt` for the
  mechanics physics, `heat_transfer-opt` for the thermal ones), built with Kokkos.

The optional `gpu` section controls how runs are placed on a node's devices:

```json
"gpu": {
    "devices_per_node": 12,
    "ranks_per_run": 1,
    "visible_devices_env": "ZE_AFFINITY_MASK",
    "cpu_bind": ["1-8", "9-16", "...one core range per device..."],
    "environment": {"ONEAPI_DEVICE_SELECTOR": "level_zero:gpu", "ZES_ENABLE_SYSMAN": "1"}
}
```

- `ranks_per_run`: MPI ranks per MOOSE run, one device per rank. Default: `mpi.ranks`, or 1.
- `devices_per_node`: devices (GPU tiles on Aurora) available to compgen. compgen checks that
  `nthreads * ranks_per_run` fits.
- `visible_devices_env`: environment variable that selects a rank's device
  (`ZE_AFFINITY_MASK` on Intel GPUs, `CUDA_VISIBLE_DEVICES` on NVIDIA,
  `ROCR_VISIBLE_DEVICES` on AMD).
- `cpu_bind`: optional CPU core range for each device. A run's ranks are bound to the cores of
  their devices with `--cpu-bind=list:...` (the syntax of Aurora's `mpiexec`).
- `environment`: extra environment variables for the MOOSE runs. On Intel GPUs,
  `ZES_ENABLE_SYSMAN=1` is required: without it the device matrix-matrix product used by the
  Schur-complement preconditioner fails.
- `wrapper`: optional replacement for the per-rank binding wrapper (see below).

### How runs are mapped to devices

Each of the `nthreads` workers gets a slot `s` (0 to `nthreads - 1`) and uses devices
`s * ranks_per_run` to `(s + 1) * ranks_per_run - 1`, so concurrent runs never share a
device. The command for one run is

```
mpiexec -n <ranks_per_run> [mpi.extra_args] [--cpu-bind=list:...] \
    bash compgen/share/gpu_bind.sh <moose> <options> -i input.i ... --compute-device=<device>
```

`gpu_bind.sh` sets `visible_devices_env` to the slot's first device plus the rank's
node-local index, as Aurora's `gpu_tile_compact.sh` does. Without an `mpi` section, a
single-rank run is launched directly through the wrapper.

Examples for one Aurora node (12 tiles):

| Goal | `nthreads` | `gpu.ranks_per_run` |
| --- | --- | --- |
| Many small structures | 12 | 1 |
| Medium meshes | 3 | 4 |
| One large mesh at a time | 1 | 12 |

`demos/complete/machine_config_aurora_gpu.json` is a ready-made system configuration for Aurora
(use it in place of `machine_config.json`; compgen's config merge does not allow one file to
override another's values), and `demos/complete/job_gpu_aurora.sh` is a PBS script that runs a
demo with it:

```
qsub -A <project> -v DEMO=elasticity/2d demos/complete/job_gpu_aurora.sh
```

## Physics settings

A physics directory supports gpu mode when its `settings.json` has a `gpu` block (it may be
empty). The block's entries override the top-level settings in gpu mode:

- `template`: the GPU template (default `template_gpu.i`).
- `material_properties`, `target_substitution`, `target_name`, `zero_name`: as for cpu mode,
  for templates whose input paths differ from the CPU template's. A material substitution can
  be a list of paths that all receive the same value. `target_substitution` can be a list with
  one path per load component (for example the top-level variables `gx gy` of the thermal
  templates).

## Testing

`tests/gpu/test_cpu_gpu_equivalence.py` runs every physics in both modes on the same mesh and
compares the volume averages (every time step for the plastic physics) and the element fields
for every load case. The plastic cases stop at t = 0.2, about 10 steps past yield. It also
checks that 2-rank GPU runs match single-rank runs. It needs a GPU and the Kokkos MOOSE build,
and is skipped unless `COMPGEN_TEST_DEVICE` is set:

```
COMPGEN_TEST_DEVICE=xpu COMPGEN_TEST_MPI=mpiexec MOOSE_DIR=... pytest tests/gpu
```

The executables are `$MOOSE_DIR/modules/<module>/<module>-opt`; `COMPGEN_TEST_MOOSE` uses one
executable (for example a combined application) for every physics. `COMPGEN_TEST_MPI` enables
the multi-rank checks. On Aurora, also set `ZES_ENABLE_SYSMAN=1`.
