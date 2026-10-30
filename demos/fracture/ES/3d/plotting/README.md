# 3D plotting

Each plotting script uses the newest source result in
`../simulations/output/` by default. Generated files named
`interpolated_*.h5` are ignored when selecting the newest result.

Run the plotters from this directory (or provide the scripts’ paths from
elsewhere):

```bash
python plot_material_structure.py
python plot_results.py
python plot_stress_xx_center_slices.py
python plot_interface_damage_slices.py
```

To plot a specific result, pass `--h5-file` to any script. The path may be
absolute or relative to the current working directory:

```bash
python plot_material_structure.py --h5-file ../simulations/output/fracture_example_0.h5
python plot_results.py --h5-file /path/to/result.h5
python plot_stress_xx_center_slices.py --h5-file /path/to/result.h5
python plot_interface_damage_slices.py --h5-file /path/to/result.h5
```

Plots are written in a directory beside the selected HDF5 file, named after
the file without its `.h5` suffix. The material-structure PNG remains beside
the HDF5 file as it did previously. The results plotter does not interpolate
to a finer grid: node fields are plotted at their native node resolution and
element fields at their native element resolution. For a 64-element mesh,
these are 65x65 and 64x64 x-y projections, respectively. It writes the
native projections to `native_xy_projection.h5`.

`plot_interface_damage_slices.py` writes `interface_damage_slices.gif`. It
shows four native x-y element-center layers from the minimum-z material face
to the z-center. The y axis is vertical because the fracture setup pulls in
the y direction. The selected layers are the closest native locations to the
face, two evenly spaced positions between the face and center, and the
center; no interpolation is used.