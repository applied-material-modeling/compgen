[Mesh]
  [fmg]
    type = FileMeshGenerator
    file = 'mesh.exo'
  []

  [sidesets]
    type = SideSetsFromNormalsGenerator
    input = fmg
    normals = '-1 0 0
                1 0 0
                0 -1 0
                0 1 0'
    new_boundary = 'left right bottom top'
  []

  [bmb]
    type = BreakMeshByBlockGenerator
    input = sidesets
    add_interface_on_two_sides = true
    block_pairs = 'mat_a mat_b'
    interface_name = 'interface'
    split_interface = false
  []
[]

[Variables]
  [d]
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
  # Enforces d_{n+1} >= d_n.
  [irreversibility]
    type = VariableOldValueBounds
    variable = bounds_dummy
    bounded_variable = d
    bound_type = lower
  []

  # Enforces d <= 1.
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
    material_property_names = 'Gc psic xi c0 l'
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

[Postprocessors]
  [max_d]
    type = NodalExtremeValue
    variable = d
    value_type = max
  []

  [min_d]
    type = NodalExtremeValue
    variable = d
    value_type = min
  []

  [max_psie_active]
    type = ElementExtremeValue
    variable = psie_active
    value_type = max
  []
[]

[Executioner]
  type = Transient

  solve_type = NEWTON
  petsc_options_iname = '-pc_type -pc_hypre_type -ksp_type -snes_type'
  petsc_options_value = 'hypre     boomeramg      cg        vinewtonrsls'
  automatic_scaling = true

  nl_rel_tol = 1e-06
  nl_abs_tol = 1e-08
  nl_max_its = 50

  dt = 1e12

  [Quadrature]
    order = CONSTANT
  []
[]

[Outputs]
  exodus = true
  csv = true
  print_linear_residuals = false
[]
