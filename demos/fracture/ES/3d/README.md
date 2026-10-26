# 3D fracture / elastic-solid demo

This is the 3D counterpart of the predefined elastic-solid fracture sweep.
It generates a hexahedral mesh, uses `3d/fracture`, and writes simulation
outputs, logs, and temporary files under `simulations/`.

Run locally with:

```bash
./demos/fracture/ES/3d/run_fracture_predefined_local.sh
```

The default resolution is intentionally modest (`32^3`) so the first run can
be used as a setup check. Increase `generator.params.N` after the executable
and input have been validated.
