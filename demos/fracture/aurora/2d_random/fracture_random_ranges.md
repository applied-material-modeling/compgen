# Random material sampling ranges - 2D fracture sweep

These are the sampling specs used in `config_fracture.json` via
`materials.DistributionMaterialGenerator`. A fresh draw is taken for every
simulation, and the drawn values are recorded in each output `.h5` (under the
`material_properties` group), so the sweep is self-documenting.

Consistent unit system: **MPa - mm - N (- tonne - s)**.
  stress / modulus / strength -> MPa
  length                      -> mm
  energy release rate (Gc)    -> N/mm  (= kJ/m^2)
  density                     -> g/cm^3 (recorded only; see note)

## Distributions

`uniform`    - even in linear space (good for bounded, single-decade quantities).
`loguniform` - even in log space, i.e. every decade equally likely (correct for
               quantities spanning many orders of magnitude across materials).
`fixed`      - constant on every draw.

## Bulk phases A and B (identical specs, drawn independently for A and B)

| Property        | Distribution | Range           | Unit  | Rationale |
|-----------------|--------------|-----------------|-------|-----------|
| youngs_modulus  | uniform      | [1000, 500000]  | MPa   | Advisor range [0, 500000], floored at 1000 (1 GPa) to avoid degenerate near-zero-stiffness solves. Revert to 0 if desired. |
| poissons_ratio  | uniform      | [0.01, 0.49]    | -     | Advisor range. Kept < 0.5 to avoid the incompressible limit (bulk modulus blows up). |
| density         | uniform      | [0.5, 23.0]     | g/cm^3| Advisor range (~foam to ~osmium). Recorded only - no effect on the quasi-static solve. |
| l               | fixed        | 0.015           | mm    | Phase-field regularization length. SHARED between A and B (single template variable), and must stay resolved by the mesh (element ~0.0039 at 256^2), so not randomized. |
| Gc              | loguniform   | [0.005, 300]    | N/mm  | Fracture energy release rate. Spans glass/ceramic (~0.005-0.1) through polymers (~0.3) to ductile metals (~10-300 kJ/m^2). From fracture-toughness tables (Gc = K_Ic^2 / E). |
| psic            | loguniform   | [0.5, 300]      | MPa   | Critical strain-energy density (strength-like). From tensile-strength tables, but capped so specimens can fracture within the 5% applied-strain loading window (see caveat). |

## Interface / cohesive zone (material_AB)

| Property        | Distribution | Range           | Unit  | Rationale |
|-----------------|--------------|-----------------|-------|-----------|
| GI_c            | loguniform   | [0.0005, 5]     | N/mm  | Mode I interfacial fracture energy. Interfaces are usually weaker than bulk; range covers weak adhesion (~5e-4) to good structural bonds (~5 kJ/m^2). |
| GII_c           | loguniform   | [0.0005, 5]     | N/mm  | Mode II interfacial fracture energy, same envelope as GI_c. |
| normal_strength | loguniform   | [1, 300]        | MPa   | Cohesive tensile (normal) strength of the interface. |
| shear_strength  | loguniform   | [1, 300]        | MPa   | Cohesive shear strength of the interface. |
| eta             | uniform      | [1.0, 3.0]      | -     | Mixed-mode / regularization exponent (dimensionless), around the shipped value 1.5. |

## Caveats / notes

- **Loading window couples to psic.** The template applies a displacement ramp
  `function='t'` to `end_time=5e-2` on a domain `L=1.0`, i.e. max ~5% applied
  strain. Available elastic strain-energy density is ~0.5*E*(0.05)^2 = 0.00125*E,
  so for stiff materials psic up to a few hundred MPa can still fracture, but
  soft + high-psic draws may not crack in-window. If too few debug runs
  fracture, narrow the `psic` upper bound or raise `end_time`.
- **Interface vs bulk.** Draws are independent, so occasionally the interface
  will be stronger/tougher than the bulk (bulk/cohesive failure dominates
  instead of debonding). That is expected when exploring the full space; bias
  the interface ranges lower if you specifically want debonding-dominated cases.
- **`l` is shared and fixed.** Both A and B map `l` to the same template
  variable; the current physics does not support independent per-phase `l`.
- **density is recorded-only** in this quasi-static setup - it never enters the
  solve, and for a truly consistent MPa-mm-N system it would need units of
  tonne/mm^3 (aluminum = 2.7e-9), not the g/cm^3 magnitudes stored here.
- **Reproducibility.** Draws use Python's global `random` (unseeded), so runs
  are not bit-reproducible; this is fine because every draw is recorded in its
  output file.
