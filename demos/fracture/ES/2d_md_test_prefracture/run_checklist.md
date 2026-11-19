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
    - `storage` and `log_file` are selected per case in `config_case0.json` through `config_case10.json`.
- `config_case0.json` through `config_case10.json`:
    - Store the independent material/interface parameter sets.
    - Store separate output, log, and temporary paths under the matching `simulations/caseN` directory.
- `run_fracture_predefined_local.sh`:
    - `RACCOON_DIR`: defaults to `/project/ai4ns_composites/fracture_code/raccoon`; override it for another checkout.
    - Pass any available numeric case name, such as `case0` or `case10`, as the first argument when running one case directly.
- `run_fracture_tmux.sh`:
    - Starts one detached tmux session for every `config_case*.json` file.
    - Use `tmux ls` to list sessions and `tmux kill-session -t fracture-caseN` to cancel a case.
- `plotting/plot.py`:
    - Set `CASES_TO_PLOT` to the cases whose results should be plotted.
    - Set `PLOT_RESULTS` and `PLOT_MATERIAL_STRUCTURE` to enable or disable
      each type of plot.
    - `GRID_SIZES` and `FPS` optionally control plot resolution and animation speed.

## Run

From this directory, run one case directly with:

```bash
./run_fracture_predefined_local.sh case3
```

To start all cases in separate background tmux sessions, run:

```bash
./run_fracture_tmux.sh
```

Each case writes to a separate directory:

```text
simulations/caseN/{output,logs,tmp}
```

## Plot

After a successful run, from this directory:

```bash
python plotting/plot.py
```

To plot `case0` through `case10` concurrently, from the plotting directory run:

```bash
./plot_cases_parallel.sh
```

The launcher starts one process per case and defaults to one field-interpolation
worker per process. Logs are written to `plotting/logs/caseN.log`. To run only
some cases, pass their names, for example `./plot_cases_parallel.sh case0 case10`.
If the machine has enough resources, the inner worker count can be overridden
with `INNER_WORKERS=2 ./plot_cases_parallel.sh`.

## Access to grant on this machine

- `/project/ai4ns_composites/fracture_code/conda_envs/raccoon`: Conda environment.
- `/project/ai4ns_composites/fracture_code/raccoon`: compiled RACCOON checkout.

The launcher does not require a pre-generated `ADRealMonolithic.h`. If the
RACCOON input invokes MOOSE's runtime FParser JIT, `compgen/racoon.py`
configures the compiler and library paths from `CONDA_PREFIX`; otherwise no
JIT compilation is performed.