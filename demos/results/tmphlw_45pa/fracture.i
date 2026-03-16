[Mesh]
  [base]
    type = FileMeshGenerator
    file = '/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/mesh.exo'
  []
  [sidesets]
    type = SideSetsFromNormalsGenerator
    input = base
    normals = '-1 0 0
                1 0 0
                0 -1 0
                0 1 0'
    new_boundary = 'left right bottom top'
  []
[]

[Variables]
  [d]
     [InitialCondition]
       type = CohesiveDamageIC
       d0 = 1
       l = ${l}
      x1 = '0.44078692 0.39129596 0.21462229 0.11871791 0.18965978 0.07105262 1.00000000 0.04380781 1.00000000 0.15540042'
      y1 = '0.48033990 0.64808932 0.75567782 0.88646737 0.38807691 0.31602254 0.27676368 0.87025265 0.86773327 0.56711007'
      x2 = '0.50687880 0.32529110 0.27266660 0.20455904 0.12671590 0.00000000 0.98023468 0.00000000 0.96182833 0.01031626'
      y2 = '0.55356824 0.68151310 0.72239211 0.88046180 0.32628120 0.27676368 0.26584271 0.86773327 0.86553802 0.60828581'
      z1 = '0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000'
      z2 = '0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000'
     []
  []
[]

[AuxVariables]
  [bounds_dummy]
  []
  [psie_active]
    order = CONSTANT
    family = MONOMIAL
  []
[]

[Bounds]
  [irreversibility]
    type = VariableOldValueBounds
    variable = bounds_dummy
    bounded_variable = d
    bound_type = lower
  []
  [upper]
    type = ConstantBounds
    variable = bounds_dummy
    bounded_variable = d
    bound_type = upper
    bound_value = 1
  []
[]

[Kernels]
  [pff_diff]
    type = ADPFFDiffusion
    variable = d
  []
  [pff_source]
    type = ADPFFSource
    variable = d
    free_energy = psi
  []
[]

[BCs]
  [Periodic]
    [x]
      auto_direction = 'x y'
      variable = 'd'
    []
  []
[]

[Materials]
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
  [crack_geometric]
    type = CrackGeometricFunction
    property_name = alpha
    expression = d
    phase_field = d
  []
  [degradation]
    type = RationalDegradationFunction
    property_name = g
    phase_field = d
    parameter_names = 'p a2 a3 eta'
    parameter_values = '2 1 0 1e-6'
    material_property_names = 'Gc psic xi c0 l '
  []
  [psi]
    type = ADDerivativeParsedMaterial
    property_name = psi
    expression = 'alpha*Gc/c0/l+g*psie_active'
    coupled_variables = 'd psie_active'
    material_property_names = 'alpha(d) g(d) Gc c0 l'
    derivative_order = 1
  []
[]

[Executioner]
  type = Transient
  solve_type = NEWTON
  petsc_options_iname = '-pc_type -snes_type'
  petsc_options_value = 'lu vinewtonrsls'
  automatic_scaling = true
  nl_rel_tol = 1e-08
  nl_abs_tol = 1e-10
  dt = 1e12
[]

[Outputs]
[]
