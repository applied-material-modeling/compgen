# Units in the 2D Fracture-MD Template

ChatGPT analysis 2026/11/04

This note documents the units of the variables at the top of:

```text
/home/bbrunsvik/projects/ai4ns/compgen/compgen/physics/2d/fracture_md_test/template.i
```

## Executive summary

The repository uses a consistent **MPa–mm–N** convention for the fracture
examples. Time is conventionally in seconds when a time dimension is needed,
giving an MPa–mm–N–s system. MOOSE and RACCOON do not attach or enforce units
at runtime: the numbers are interpreted consistently only if all inputs,
meshes, boundary conditions, and outputs use the same convention.

| Variable(s) | Meaning | Unit in this project |
|---|---|---|
| `E_A`, `E_B` | Young's modulus | MPa (`N/mm²`) |
| `nu_A`, `nu_B` | Poisson's ratio | dimensionless |
| `K_A`, `K_B` | Bulk modulus, derived from `E` and `nu` | MPa (`N/mm²`) |
| `G_A`, `G_B` | Shear modulus, derived from `E` and `nu` | MPa (`N/mm²`) |
| `Gc_A`, `Gc_B` | Bulk critical fracture energy/release rate | N/mm (`kJ/m²`) |
| `psic_A`, `psic_B` | Bulk critical energy density/strength-like threshold | MPa (`N/mm²`) |
| `l` | Phase-field regularization length | mm |
| `GI_c`, `GII_c` | Interface critical fracture energies | N/mm (`kJ/m²`) |
| `N`, `T` | Interface normal and shear strengths | MPa (`N/mm²`) |
| `eta` | Mixed-mode exponent | dimensionless |

Useful conversions are:

```text
1 MPa = 1 N/mm²
1 N/mm = 1 kJ/m² = 1000 J/m²
```

## Confidence in the executive-summary units

These confidence levels describe how confident we are that the **intended
CompGen/RACCOON convention** is represented correctly. They do not mean that
MOOSE or RACCOON stores physical unit metadata; the solver treats the values
as numerical quantities and does not enforce a unit system.

| Variable(s) | Unit claimed above | Confidence | Basis and remaining limitation |
|---|---|---|---|
| `E_A`, `E_B` | MPa (`N/mm²`) | **Fully confident** | The values are used as elastic moduli, and repository output documentation explicitly labels the shipped values as 68 and 401 GPa, equivalent to 68,000 and 401,000 MPa. |
| `nu_A`, `nu_B` | Dimensionless | **Fully confident** | Poisson's ratio is a strain ratio and is used in the standard dimensionless isotropic modulus formulas. |
| `K_A`, `K_B` | MPa (`N/mm²`) | **Fully confident** | `K` is calculated directly from `E`; the formula is dimensionless apart from `E`, so it inherits `E`'s units. |
| `G_A`, `G_B` | MPa (`N/mm²`) | **Fully confident** | `G` is calculated directly from `E`; it inherits `E`'s units and is passed to the elasticity material as a shear modulus. |
| `Gc_A`, `Gc_B` | N/mm (`kJ/m²`) | **Fully confident** | The repository explicitly labels these values as N/mm. Raccoon's `RationalDegradationFunction` identifies `Gc` as fracture toughness, and its equations use `Gc/l` and `Gc*l` in the phase-field model, confirming the fracture-energy/length dimensional role. |
| `psic_A`, `psic_B` | MPa (`N/mm²`) | **Fully confident** | The repository explicitly labels these values as MPa. Raccoon's `RationalDegradationFunction` identifies `psic` as the critical fracture energy and uses `Gc/psic` as a dimensionless ratio, confirming that `psic` has the same stress/energy-density dimensions as `Gc/l`. |
| `l` | mm | **Most likely** | The project documents an mm–MPa–s convention and requires `l` to be resolved by the mesh. The template itself has no unit annotation, so this is a convention-based conclusion rather than solver-enforced metadata. |
| `GI_c`, `GII_c` | N/mm (`kJ/m²`) | **Fully confident** | Repository documentation, plotting code, and command-line help explicitly identify both interface energies as N/mm; the cohesive material receives them as fracture energies. |
| `N`, `T` | MPa (`N/mm²`) | **Fully confident** | Repository documentation and plotting code explicitly label normal and shear cohesive strengths as MPa, and the material parameters are peak tractions. |
| `eta` | Dimensionless | **Fully confident** | It is documented as a mixed-mode/regularization exponent; an exponent has no physical units. |

### Why no executive-summary item is marked “Unsure”

There is no checked-in RACCOON/MOOSE source for the cohesive material used by
the interface block, so the interface-specific implementation cannot be
verified from its C++ declaration here. Raccoon does provide the phase-field
source, however, and that source directly supports the `Gc`, `psic`, and `l`
interpretation. The remaining **Most likely** item, `l`, is confirmed by
Raccoon to be a length but its specific millimeter scale comes from the
CompGen project convention and mesh setup rather than from Raccoon metadata.

## Evidence from the Raccoon checkout

The Raccoon source at `/home/bbrunsvik/code/raccoon` contains the phase-field
implementation used by `fracture_md_test`.

### `RationalDegradationFunction.C`

```cpp
params.addClassDescription(
    "Defines the rational degradation function ... where a1 = "
    "Gc/psic * xi/(c0*l). Gc is the fracture toughness, psic is "
    "the critical fracture energy, ... l is the regularization length.");

params.set<std::string>("expression") =
    "(1-d)^p/((1-d)^p+(Gc/psic*xi/c0/l)*d*...)*(1-eta)+eta";
```

This is direct source evidence that:

- `Gc` is a fracture-energy/toughness quantity;
- `psic` is a critical fracture-energy/energy-density quantity;
- `l` is a regularization length;
- `Gc/psic` participates as a dimensionless ratio in the constitutive
  function.

### `ADPFFDiffusion.C`

```cpp
params.addClassDescription(
    "The diffusion term ... is $(grad w, 2*Gc*l/c0 grad d)$.");

return 2 * _Gc[_qp] * _l[_qp] / _c0[_qp] * value;
```

This independently confirms that Raccoon uses `Gc` and `l` as the fracture
toughness and regularization-length scales in the phase-field diffusion term.
With the CompGen convention `l = mm`, `Gc = N/mm` gives `Gc/l = N/mm² = MPa`
and `Gc*l = N`, which is dimensionally consistent with the corresponding
weak-form scaling.

### Interface-material limitation

A focused search of `/home/bbrunsvik/code/raccoon` did not find the source or
documentation for `BiLinearMixedModeTraction`. Therefore the units of
`GI_c`, `GII_c`, `normal_strength`, `shear_strength`, `penalty_stiffness`, and
`viscosity` remain based on CompGen's explicit labels, template usage, and
dimensional reasoning rather than direct Raccoon material source.

## Source template

The variables documented here are defined as follows:

```ini
E_A = 68000.0
nu_A = 0.35
K_A = '${fparse E_A/3/(1-2*nu_A)}'
G_A = '${fparse E_A/2/(1+nu_A)}'

E_B = 401000.0
nu_B = 0.19
K_B = '${fparse E_B/3/(1-2*nu_B)}'
G_B = '${fparse E_B/2/(1+nu_B)}'

Gc_A = 20.0
psic_A = 90.0

Gc_B = 0.036
psic_B = 0.3

l = 0.015

# interface
GI_c = 0.00228
GII_c = 0.00097
N = 378.0
T = 97.0
# original N = 7560.0
# original T = 1940.0
eta = 1.5
```

## Bulk elastic parameters

### `E_A`, `E_B`: Young's moduli

The template derives `K` and `G` from `E` and `nu`:

```ini
K_A = '${fparse E_A/3/(1-2*nu_A)}'
G_A = '${fparse E_A/2/(1+nu_A)}'
```

The derived moduli are passed to:

```ini
[elasticity]
  type = SmallDeformationIsotropicElasticity
  bulk_modulus = K
  shear_modulus = G
  phase_field = d
  degradation_function = g
[]
```

Because strain is dimensionless, `E`, `K`, and `G` have stress units. In this
project those units are **MPa**, equivalently **N/mm²**. The repository's
material display code labels the shipped values as `68.0 GPa` and `401.0 GPa`,
which are the same values as `68000 MPa` and `401000 MPa`.

### `nu_A`, `nu_B`: Poisson's ratios

Poisson's ratio is a ratio of strains and is **dimensionless**. The formulas

```text
K = E / [3(1 - 2 nu)]
G = E / [2(1 + nu)]
```

are standard isotropic relationships, so `K` and `G` inherit the MPa units of
`E`.

## Bulk fracture parameters

### `Gc_A`, `Gc_B`: bulk critical fracture energy

The phase-field subproblem receives these values as material properties:

```ini
[bulk_properties_A]
  type = ADGenericConstantMaterial
  prop_names = 'l Gc psic'
  prop_values = '${l} ${Gc_A} ${psic_A}'
  block = 'mat_a'
[]

[bulk_properties_B]
  type = ADGenericConstantMaterial
  prop_names = 'l Gc psic'
  prop_values = '${l} ${Gc_B} ${psic_B}'
  block = 'mat_b'
[]
```

The free-energy expression is:

```ini
[psi]
  type = ADDerivativeParsedMaterial
  property_name = psi
  expression = 'alpha*Gc/c0/l+g*psie_active'
  coupled_variables = 'd psie_active'
  material_property_names = 'alpha(d) g(d) Gc c0 l'
  derivative_order = 1
[]
```

With dimensionless phase-field quantities and `Gc/l` contributing an energy
density/stress, `Gc` must be energy per area:

```text
Gc / l = (N/mm) / mm = N/mm² = MPa
```

Therefore `Gc_A` and `Gc_B` are **N/mm**, equivalently **kJ/m²**. They are not
J/m² numerically:

```text
Gc_A = 20.0 N/mm = 20.0 kJ/m² = 20000 J/m²
Gc_B = 0.036 N/mm = 0.036 kJ/m² = 36 J/m²
```

The repository's plotting code independently labels these values `20.0 N/mm`
and `0.036 N/mm`.

### `psic_A`, `psic_B`: critical bulk energy density

`psic` is passed alongside `Gc` and `l`:

```ini
prop_names = 'l Gc psic'
prop_values = '${l} ${Gc_A} ${psic_A}'
```

It is also named as an input to the degradation model:

```ini
[degradation]
  type = RationalDegradationFunction
  property_name = g
  phase_field = d
  parameter_names = 'p a2 a3 eta'
  parameter_values = '2 1 0 1e-6'
  material_property_names = 'Gc psic xi c0 l '
[]
```

`psic` is a critical energy-density/strength-like quantity, not the fracture
energy `Gc`. In the repository's convention it is **MPa**, equivalently
**N/mm²**. The material display code labels the values `90.0 MPa` and
`0.30 MPa`.

## Phase-field length

### `l`: regularization length

```ini
l = 0.015
```

`l` is the phase-field crack-width/regularization length and is used in `Gc/l`.
It is therefore a length; the project convention makes it **mm**:

```text
l = 0.015 mm = 15 micrometres
```

The mesh must resolve this length scale. `l` is shared by materials A and B;
the current template does not support independent `l_A` and `l_B` values.

## Interface parameters

The mechanical template assigns the A–B interface to the cohesive material:

```ini
[Materials]
  [tsl]
    type = BiLinearMixedModeTraction
    boundary = 'interface'
    penalty_stiffness = 1e6
    GI_c = ${GI_c}
    GII_c = ${GII_c}
    normal_strength = ${N}
    shear_strength = ${T}
    eta = ${eta}
    viscosity = 1e-5
  []
[]
```

The settings file maps configuration names to these variables:

```json
"interface_material_properties": [
    "GI_c", "GII_c", "normal_strength", "shear_strength", "eta"
],
"interface_substitutions": [
    "GI_c", "GII_c", "N", "T", "eta"
]
```

### `GI_c`, `GII_c`: interface fracture energies

The repository's interface documentation and plotting code label these values
as **N/mm**. Thus:

```text
GI_c, GII_c: N/mm = kJ/m²
GI_c  = 0.00228 N/mm = 2.28 J/m²
GII_c = 0.00097 N/mm = 0.97 J/m²
```

### `N`: interface normal strength

```ini
N = 378.0
normal_strength = ${N}
```

`normal_strength` is the peak normal traction in the cohesive
traction–separation law. Traction has stress units, so `N` is **MPa**, or
**N/mm²**. The current value is `378 MPa`; the benchmark configuration and
plotting code use the same number and label it `378.0 MPa`.

### `T`: interface shear strength

```ini
T = 97.0
shear_strength = ${T}
```

`shear_strength` is the peak tangential/shear traction, so it has the same
units as `N`:

```text
T = 97 MPa = 97 N/mm²
```

The commented values `N = 7560.0` and `T = 1940.0` are alternate strengths
in the same MPa convention, not a different unit system.

### `eta`: mixed-mode exponent

```ini
eta = 1.5
eta = ${eta}
```

The repository describes `eta` as a mixed-mode/viscous-regularization
exponent. It is **dimensionless**.

## Constants in the interface material block

These constants are not in the top parameter list, but they affect the unit
interpretation of the cohesive law.

### `penalty_stiffness = 1e6`

```ini
penalty_stiffness = 1e6
```

This relates traction to displacement jump before damage. With traction in MPa
and displacement jump in mm, its inferred unit is:

```text
MPa/mm = N/mm³
```

The repository does not explicitly label this unit, and MOOSE does not enforce
it. This is a dimensional inference from the traction–separation role of the
parameter.

### `viscosity = 1e-5`

```ini
viscosity = 1e-5
```

The checked-out CompGen repository does not contain the implementation of
`BiLinearMixedModeTraction`, and the repository does not label this
parameter's units. If it is used in the usual traction-rate regularization,
where viscous traction is proportional to displacement-jump rate, the inferred
unit would be:

```text
(MPa/mm) s = MPa s/mm
```

This is not confirmed without the exact RACCOON/MOOSE material source. For now,
`viscosity` should be treated as a numerical regularization parameter within
the chosen MPa–mm–N–s convention.

## Evidence and limitations

### Direct evidence in this checkout

- `E`, `K`, and `G` are used by `SmallDeformationIsotropicElasticity`.
- `Gc`, `psic`, and `l` are used by the phase-field subproblem.
- `Gc` appears divided by `l` in the free-energy expression.
- `GI_c`, `GII_c`, `N`, and `T` are passed to the cohesive material.
- Repository documentation and plotting code label moduli/strengths as MPa or
  GPa and fracture energies as N/mm.
- The supplied configuration uses the same numeric values and mappings.

### Dimensional inference

- `Gc/l` having stress/energy-density units establishes `Gc` as N/mm when `l`
  is mm.
- `penalty_stiffness` is inferred as MPa/mm from traction divided by opening.
- The unit of `viscosity` depends on the exact material implementation and is
  not confirmed by the checked-in source.

MOOSE does not enforce a unit system. This document therefore describes the
consistent convention evidenced by the CompGen inputs, comments, and output
tools; it does not claim that the solver stores physical unit metadata.
