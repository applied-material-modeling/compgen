# 2D fracture demo

## Dependencies

- Conda environment: `/home/bbrunsvik/.conda/envs/moose_genesis`.
- Compiled RACCOON executable: `/home/bbrunsvik/code/raccoon/raccoon-opt`.
- Compiled MOOSE: maybe not required at runtime; used to build or rebuild `/home/bbrunsvik/code/raccoon/raccoon-opt`.

## Paths to inspect or change after pulling

Information provided like this: 
- `Filename`
    - `Variable`:`recommendation`

- `local_machine_config.json`: 
    - `racoon/executable`: `/home/bbrunsvik/code/raccoon/raccoon-opt` on the ES server. 
    - `MOOSE_ADFPARSER_JIT_INCLUDE`: `/home/bbrunsvik/code/raccoon/ADRealMonolithic.h` on ES server. 
    - `temp_dir`: `/var/tmp/brb/compgen` On ES server, I suggest `/var/tmp/USER_NAME/compgen`
    - `log_file`: `/home/bbrunsvik/projects/ai4ns/compgen/demos/fracture/ES/2d/simulations/logs/compgen_local.log` set this to your own compgen directory. 
- `fracture_predefined_local.json`: 
    -  `output_dir `: `/home/bbrunsvik/projects/ai4ns/compgen/demos/fracture/ES/2d/simulations/logs/compgen_local.log` set this to your own compgen directory. 
- `run_fracture_predefined_local.sh`: 
    - `RACCOON_DIR`: set to `/home/bbrunsvik/code/raccoon`; replace this with your own absolute RACCOON path.
- `plotting/plot_material_structure.py`: 
    - `H5_FILE`: set this to the result `.h5` file to plot.
- `plotting/plot_results.py`: 
    - `GRID_SIZES` and `FPS`: optionally change plot resolution and animation speed.

## Run

From this directory, run:

```bash
./run_fracture_predefined_local.sh
```

## Plot

After a successful run, from this directory:

```bash
python plotting/plot_results.py
python plotting/plot_material_structure.py
```

## Access to grant on this machine

- `/home/bbrunsvik/.conda/envs/moose_genesis`: shared Conda environment.
- `/home/bbrunsvik/code/raccoon`: compiled RACCOON, including `raccoon-opt` and `ADRealMonolithic.h`.
- `MOOSE`