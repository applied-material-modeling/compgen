# 2D fracture demo

## Dependencies

- Conda environment: `/project/ai4ns_composites/fracture_code/conda_envs/raccoon`.
- Compiled RACCOON executable: `/project/ai4ns_composites/fracture_code/raccoon/raccoon-opt`.
- Compiled MOOSE: already included by the RACCOON build; not required separately at runtime.

## Paths to inspect or change after pulling

Information provided like this: 
- `Filename`
    - `Variable`:`recommendation`

- `config_machine.json`: 
    - `racoon/executable`: `/project/ai4ns_composites/fracture_code/raccoon/raccoon-opt`.
    - `temp_dir`: `/var/tmp/brb/compgen` On ES server, I suggest `/var/tmp/USER_NAME/compgen`
    - `log_file`: `/home/bbrunsvik/projects/ai4ns/compgen/demos/fracture/ES/2d/simulations/logs/compgen_local.log` set this to your own compgen directory. 
- `config_fracture.json`: 
    -  `output_dir `: `/home/bbrunsvik/projects/ai4ns/compgen/demos/fracture/ES/2d/simulations/logs/compgen_local.log` set this to your own compgen directory. 
- `run_fracture_predefined_local.sh`: 
    - `RACCOON_DIR`: defaults to `/project/ai4ns_composites/fracture_code/raccoon`; override it for another checkout.
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

- `/project/ai4ns_composites/fracture_code/conda_envs/raccoon`: Conda environment.
- `/project/ai4ns_composites/fracture_code/raccoon`: compiled RACCOON checkout.

The launcher does not require a pre-generated `ADRealMonolithic.h`. If the
RACCOON input invokes MOOSE's runtime FParser JIT, `compgen/racoon.py`
configures the compiler and library paths from `CONDA_PREFIX`; otherwise no
JIT compilation is performed.