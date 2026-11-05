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
    - `storage` and `log_file` are selected per case in `config_case1.json` or `config_case2.json`.
- `config_case1.json` and `config_case2.json`:
    - Store the independent material/interface parameter sets.
    - Store separate output, log, and temporary paths under `simulations/case1` or `simulations/case2`.
- `run_fracture_predefined_local.sh`:
    - `RACCOON_DIR`: defaults to `/project/ai4ns_composites/fracture_code/raccoon`; override it for another checkout.
    - Pass `case1` or `case2` as the first argument when running one case directly.
- `run_fracture_tmux.sh`:
    - Starts one detached tmux session for every `config_case*.json` file.
    - Use `tmux ls` to list sessions and `tmux kill-session -t fracture-case1` to cancel a case.
- `plotting/plot.py`:
    - Set `CASES_TO_PLOT` to `("case1",)`, `("case2",)`, or both cases.
    - Set `PLOT_RESULTS` and `PLOT_MATERIAL_STRUCTURE` to enable or disable
      each type of plot.
    - `GRID_SIZES` and `FPS` optionally control plot resolution and animation speed.

## Run

From this directory, run one case directly with:

```bash
./run_fracture_predefined_local.sh case1
```

To start all cases in separate background tmux sessions, run:

```bash
./run_fracture_tmux.sh
```

Each case writes to a separate directory:

```text
simulations/case1/{output,logs,tmp}
simulations/case2/{output,logs,tmp}
```

## Plot

After a successful run, from this directory:

```bash
python plotting/plot.py
```

## Access to grant on this machine

- `/project/ai4ns_composites/fracture_code/conda_envs/raccoon`: Conda environment.
- `/project/ai4ns_composites/fracture_code/raccoon`: compiled RACCOON checkout.

The launcher does not require a pre-generated `ADRealMonolithic.h`. If the
RACCOON input invokes MOOSE's runtime FParser JIT, `compgen/racoon.py`
configures the compiler and library paths from `CONDA_PREFIX`; otherwise no
JIT compilation is performed.