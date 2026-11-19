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
## Pre-fracture geometry

Cases 1, 5, and 10 contain a horizontal initial cohesive fracture that enters
from the left edge and extends 40% of the model width. The fracture is centered at
`prefracture_y_fraction = 0.5` and is 10 pixels wide. During ellipse generation,
any candidate ellipse that touches this corridor is discarded and another
candidate is sampled, so the requested ellipse volume fraction remains the
target rather than being filled by inclusions near the fracture.

The corridor parameters are generator parameters:

```json
"prefracture_length_fraction": 0.4,
"prefracture_y_fraction": 0.5,
"prefracture_width": 10.0
```

`plotting/plot_ellipse_preview.py` creates a starting-geometry verification
figure with the ellipse exclusion corridor outlined in red and the initial
cohesive fracture drawn as a thick black line. The fracture is initialized in
the phase-field sub-application using `CohesiveDamageIC`; it is not represented
as a third material in the binary mesh. The corridor ensures later ellipses
cannot overlap the initial crack.

To run the requested cases after reviewing the preview:

```bash
./run_fracture_predefined_local.sh case1
./run_fracture_predefined_local.sh case5
./run_fracture_predefined_local.sh case10
```
