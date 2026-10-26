# Local RACCOON Debugging Summary — 2026-10-23

## Problems observed

- Embedded MOOSE FParser JIT compilation could not find `mpicxx`.
- After compilation was made to work, the generated shared object could not be loaded:
  `failed to map segment from shared object`.
- The controlled fracture run did not yet provide a confirmed successful end-to-end result.

## Fixes applied

- Updated `compgen/racoon.py` to prepend `${CONDA_PREFIX}/bin` to the subprocess `PATH`, making the conda MPI compiler wrapper available to the embedded JIT compiler.
- Diagnosed the loader failure as an executable-memory restriction: `/tmp` is mounted `noexec`.
- Changed the local configuration to use `/home/bbrunsvik/compgen_tmp` for temporary working directories, where JIT shared objects can be loaded.
- Confirmed that JIT objects compile and load when RACCOON runs from the home filesystem.

## Recommended next steps

1. Let the current controlled fracture run finish and check its final exit status.
2. Review the Python/CompGen log:
   `/tmp/brb/compgen_local_es02.lanl.gov.log`
3. If the run fails again, inspect the final RACCOON error after the JIT stage; it may be an input, solver, MPI, or runtime issue rather than a JIT-loading issue.
4. Confirm that results were written under `/tmp/brb/fracture_simulations`.
5. Only after the controlled case succeeds, run the full fracture sweep.

## Relevant files and diagnostics

- Python/CompGen log: `/tmp/brb/compgen_local_es02.lanl.gov.log`
- Launcher stdout: `/tmp/brb/final_local_stdout.log`
- Launcher stderr: `/tmp/brb/final_local_stderr.log`
- JIT temporary directory: `/home/bbrunsvik/compgen_tmp`
- Local configuration: `demos/3D_ES/local_machine_config.json`
- RACCOON environment handling: `compgen/racoon.py`
