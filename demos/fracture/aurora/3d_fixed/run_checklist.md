# Aurora 3D fixed-material fracture run checklist

- `config_fracture.json`:
  - The current long-running sweep uses `number=400` and `nthreads=2`; the
    large number keeps the workers running until the walltime limit.
  - Confirm the `32^3` setup-check resolution before increasing it.
  - Increase `generator.params.N` only after the setup check succeeds.
  - Confirm `output.output_dir` before submitting a production run.
  - Confirm the 3D entries: `L` has three values, `mesh.generate_mesh_3d`, and `3d/fracture`.
- `config_machine.json`:
  - Confirm the RACOON, MOOSE, and MPI executable paths.
  - Confirm that 50 MPI ranks fit the allocated Aurora node/resource layout.
  - With `nthreads=2`, up to 100 MPI ranks may be active concurrently.
  - Confirm `log_file` before submitting.
- `submit_job.sh`:
  - Confirm the node count and walltime for the selected 3D resolution.
  - The current setup uses one node, two concurrent workers, and 50 RACOON
    MPI ranks per worker.
- `dummy_dsh.sh`:
  - Check the log file location.
- Before submitting the full run, use `submit_job_debug.sh`:
  - It requests one node for one hour on the `debug` queue.
  - The 3D setup-check may stop at the walltime limit; that is expected.