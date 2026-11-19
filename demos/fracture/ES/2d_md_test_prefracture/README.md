# 2D MD fracture cases

This demo runs the numeric interface-parameter cases from one folder. To run
one case directly, pass its case name to the launcher:

```bash
./run_fracture_predefined_local.sh case3
```

To start one detached tmux session for every `config_case*.json` file, run:

```bash
./run_fracture_tmux.sh
```

The sessions are named `fracture-case0` through `fracture-case10`. Monitor one
with `tmux attach -t fracture-case3`, list them with `tmux ls`, and cancel one
with `tmux kill-session -t fracture-case3`. Each session ends when its launcher
finishes.

The selected values are read from `config_case0.json` through
`config_case10.json`; the shared physics template is unchanged. Each case keeps
its generated output, logs, and temporary files separate under the matching
`simulations/caseN/` directory. These generated files are ignored by Git.

## Material assignment

The generator uses `True` for material A and `False` for material B when it
builds the mesh. In these configs, material A is aluminum (`E=68000`,
`nu=0.35`) and material B is silicon carbide (`E=401000`, `nu=0.19`). The
`vf` continues to mean the volume fraction of material A, so these configs use
`"vf": 0.8`. The `generator.params.inclusion_material` setting is `"B"`:
the remaining 20% ellipse phase is SiC (material B), and the 80% material-A
phase is the Al matrix. The default remains `"A"` for other existing
configurations.