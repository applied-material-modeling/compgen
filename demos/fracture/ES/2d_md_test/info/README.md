# Generate case configurations

`energy_summary.csv` contains one tensile (mode I) and one shear (mode II) row
for each case 1–10. Generate the corresponding configurations with:

```bash
python info/generate_configs_from_energy_summary.py
```

The script uses `config_case0.json` as the baseline and writes
`config_case1.json` through `config_case10.json` in the demo directory. It
converts GPa to MPa for interface strengths and J/m² to N/mm for interface
fracture energies. `config_case0.json` is not modified.