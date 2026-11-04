# Local RACCOON Debugging Summary — 2026-10-23

## Problems observed

- Embedded MOOSE FParser JIT compilation could not find `mpicxx`.
- After compilation was made to work, the generated shared object could not be loaded:
  `failed to map segment from shared object`.
- The controlled fracture run did not yet provide a confirmed successful end-to-end result.

## Fixes applied

- Updated `compgen/racoon.py` to prepend `${CONDA_PREFIX}/bin` to the subprocess `PATH`, making the conda MPI compiler wrapper available to the embedded JIT compiler.
- Diagnosed the loader failure as an executable-memory restriction: `/tmp` is mounted `noexec`.
- Changed the local configuration to use the demo's `simulations/tmp` directory for temporary working directories, where JIT shared objects can be loaded.
- Confirmed that JIT objects compile and load when RACCOON runs from the home filesystem.

## Recommended next steps

1. Let the current controlled fracture run finish and check its final exit status.
2. Review the Python/CompGen log under `simulations/logs/`.
3. If the run fails again, inspect the final RACCOON error after the JIT stage; it may be an input, solver, MPI, or runtime issue rather than a JIT-loading issue.
4. Confirm that results were written under `simulations/output/`.
5. Only after the controlled case succeeds, run the full fracture sweep.

## Relevant files and diagnostics

- Python/CompGen log: `simulations/logs/`
- Launcher stdout/stderr: the terminal running the launcher
- JIT temporary directory: `simulations/tmp/`
- Local configuration: `demos/fracture/ES/2d/config_machine.json`
- RACCOON environment handling: `compgen/racoon.py`
