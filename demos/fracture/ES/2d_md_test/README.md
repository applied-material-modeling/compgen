# 2D MD fracture cases

This demo runs Alan's two interface-parameter sets from one folder. Set
`which_case` to `case1` or `case2` near the top of
`run_fracture_predefined_local.sh`, then run:

```bash
./run_fracture_predefined_local.sh
```

The selected values are read from `config_case1.json` or `config_case2.json`;
the shared physics template is unchanged. Each case keeps its generated output,
logs, and temporary files separate under `simulations/case1/` or
`simulations/case2/`. These generated files are ignored by Git.