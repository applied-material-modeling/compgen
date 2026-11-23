# Parallel plotting

Run from this directory:

```bash
cd /home/bbrunsvik/projects/ai4ns/compgen/demos/fracture/ES/2d_md_test/plotting
./plot_cases_parallel.sh
```

This starts one `plot.py` process for each case (`case0` through `case10`) at
the same time. Each case writes its plots under its own simulation output
directory, so the cases do not overwrite one another.

To run selected cases:

```bash
./plot_cases_parallel.sh case0 case3 case10
```

By default, each case uses one internal interpolation worker. To use more
workers per case, set `INNER_WORKERS`:

```bash
INNER_WORKERS=6 ./plot_cases_parallel.sh
```

Logs are written to `logs/caseN.log`; combined launcher output is in
`plot_cases_parallel.log`. The generated GIFs, interpolated HDF5 files, and
material plots are written below `../simulations/caseN/output/`.

To monitor the run:

```bash
pgrep -af 'plot.py --case'
tail -f plot_cases_parallel.log
```

The launcher exits successfully only when all requested cases finish. Press
`Ctrl-C` in the foreground to stop the launcher and plotting processes.

## Post-meshing verification

To run the actual configured generator, filtering, and Exodus mesh-generation
path without starting RACOON:

```bash
cd /home/bbrunsvik/projects/ai4ns/compgen/demos/fracture/ES/2d_md_test_prefracture
/home/bbrunsvik/.conda/envs/moose_genesis/bin/python \
    plotting/plot_mesh_preview.py
```

This writes `visualizations/mesh_preview.png` and keeps the generated Exodus
mesh at `visualizations/mesh_case1.exo` locally for inspection. The figure
compares the filtered bitmap with the actual finite-element material blocks
read back from Exodus and overlays the configured initial fracture.
