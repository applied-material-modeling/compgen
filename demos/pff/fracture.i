[Mesh]
  [fmg]
    type = FileMeshGenerator
    file = 'gold/composite.msh'
  []
[]

[Variables]
  [d]
    [InitialCondition]
      type = CohesiveDamageIC
      d0 = 1
      l = ${l}
      x1 = '0.65849118 0.21118956 0.76815406 0.17174808 0.00000000 0.94960688 0.53517820 0.59178123 0.30652124'
      y1 = '0.27609772 0.30823251 0.08763241 0.77441226 0.51614293 0.47422407 0.55399712 0.16129292 0.43780627'
      x2 = '0.66097391 0.06481996 0.81035711 0.23123602 0.01940184 1.00000000 0.50908298 0.49734976 0.19526557'
      y2 = '0.36756076 0.23339659 0.14170921 0.80507288 0.53228210 0.51614293 0.42338445 0.09061923 0.41139123'
      z1 = '0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000'
      z2 = '0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000 0.00000000'
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
    block = 'A'
  []
  [bulk_properties_B]
    type = ADGenericConstantMaterial
    prop_names = 'l Gc psic'
    prop_values = '${l} ${Gc_B} ${psic_B}'
    block = 'B'
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
  nl_max_its = 50

  dt = 1e12

  [Quadrature]
    order = CONSTANT
  []
[]

[Outputs]
  print_linear_residuals = false
[]
