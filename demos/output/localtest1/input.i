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

[GlobalParams]
  displacements = 'disp_x disp_y'
[]

[MultiApps]
  [fracture]
    type = TransientMultiApp
    input_files = 'fracture.i'
    cli_args = 'psic_A=${psic_A};Gc_A=${Gc_A};psic_B=${psic_B};Gc_B=${Gc_B};l=${l}'
    execute_on = 'TIMESTEP_BEGIN'
  []
[]

[Transfers]
  [from_fracture]
    type = MultiAppGeneralFieldShapeEvaluationTransfer
    from_multi_app = fracture
    variable = 'd'
    source_variable = 'd'
  []
  [to_fracture]
    type = MultiAppGeneralFieldShapeEvaluationTransfer
    to_multi_app = fracture
    variable = 'psie_active'
    source_variable = 'psie_active'
  []
[]

[Problem]
  type = ReferenceResidualProblem
  extra_tag_vectors = 'react'
[]

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

[Physics]
  [SolidMechanics]
    [CohesiveZone]
      [interface]
        boundary = 'interface'
        strain = SMALL
      []
    []
  []
[]

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

[Variables]
  [disp_x]
  []
  [disp_y]
  []
[]

[AuxVariables]
  [d]
  []
  [d_interface]
    order = CONSTANT
    family = MONOMIAL
    [AuxKernel]
      type = MaterialRealAux
      property = damage
      boundary = 'interface'
      execute_on = 'TIMESTEP_END'
      check_boundary_restricted = false
    []
  []
  [psie_active]
    order = CONSTANT
    family = MONOMIAL
    [AuxKernel]
      type = ADMaterialRealAux
      property = psie_active
      execute_on = 'INITIAL TIMESTEP_END'
    []
  []
  [react_y]
    [AuxKernel]
      type = ReactionForceAux
      vector_tag = 'react'
      v = 'disp_y'
    []
  []
  [stress_xx]
    order = CONSTANT
    family = MONOMIAL
  []
  [stress_yy]
    order = CONSTANT
    family = MONOMIAL
  []
  [stress_xy]
    order = CONSTANT
    family = MONOMIAL
  []
[]

[AuxKernels]
  [stress_xx_aux]
    type = ADRankTwoAux
    variable = stress_xx
    rank_two_tensor = stress
    index_i = 0
    index_j = 0
    execute_on = 'TIMESTEP_END'
  []

  [stress_yy_aux]
    type = ADRankTwoAux
    variable = stress_yy
    rank_two_tensor = stress
    index_i = 1
    index_j = 1
    execute_on = 'TIMESTEP_END'
  []

  [stress_xy_aux]
    type = ADRankTwoAux
    variable = stress_xy
    rank_two_tensor = stress
    index_i = 0
    index_j = 1
    execute_on = 'TIMESTEP_END'
  []
[]

[Kernels]
  [solid_x]
    type = ADStressDivergenceTensors
    variable = disp_x
    component = 0
    extra_vector_tags = 'react'
  []
  [solid_y]
    type = ADStressDivergenceTensors
    variable = disp_y
    component = 1
    extra_vector_tags = 'react'
  []
[]

[BCs]
  [fix_x]
    type = FunctionDirichletBC
    variable = disp_x
    boundary = 'left'
    function = 0
  []
  [fix_y]
    type = FunctionDirichletBC
    variable = disp_y
    boundary = 'bottom'
    function = 0
  []
  [pull_y]
    type = FunctionDirichletBC
    variable = disp_y
    boundary = 'top'
    function = 't'
    preset = false
  []
[]

[Constraints]
  [ev_x]
    type = EqualValueBoundaryConstraint
    secondary = 'right'
    variable = 'disp_x'
    penalty = 1e6
  []
[]

[Materials]
  [bulk_properties_A]
    type = ADGenericConstantMaterial
    prop_names = 'K G l Gc psic'
    prop_values = '${K_A} ${G_A} ${l} ${Gc_A} ${psic_A}'
    block = 'mat_a'
  []
  [bulk_properties_B]
    type = ADGenericConstantMaterial
    prop_names = 'K G l Gc psic'
    prop_values = '${K_B} ${G_B} ${l} ${Gc_B} ${psic_B}'
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
  [elasticity]
    type = SmallDeformationIsotropicElasticity
    bulk_modulus = K
    shear_modulus = G
    phase_field = d
    degradation_function = g
    decomposition = NONE
  []
  [strain]
    type = ADComputeSmallStrain
  []
  [stress]
    type = ComputeSmallDeformationStress
    elasticity_model = elasticity
  []
[]

[Postprocessors]
  [R_y]
    type = NodalSum
    variable = react_y
    boundary = 'top'
  []
  [R_y_max]
    type = TimeExtremeValue
    postprocessor = 'R_y'
    value_type = max
    outputs = none
  []
[]

[UserObjects]
  [stop]
    type = Terminator
    expression = 'R_y < R_y_max * 0.8'
    fail_mode = HARD
    message = 'onset of softening has begun'
  []
[]

[Executioner]
  type = Transient
  solve_type = 'NEWTON'
  petsc_options = '-ksp_converged_reason'
  petsc_options_iname = '-pc_type -pc_factor_mat_solver_package'
  petsc_options_value = 'lu       superlu_dist'
  
  # Initial time step size
  dt = 2e-4
  
  # Limits to prevent the time step from getting too small or too large
  dtmin = 1e-8
  dtmax = 1e-2
  
  end_time = 5e-2
  nl_abs_tol = 1e-08
  nl_rel_tol = 1e-04
  nl_max_its = 8
  automatic_scaling = true
  reuse_preconditioner = true
  # Adaptive Time Stepper Sub-block
  [TimeStepper]
    type = IterationAdaptiveDT
    dt = 2e-4
    optimal_iterations = 6
    iteration_window = 1
    growth_factor = 1.2
    cutback_factor = 0.5
  []
  [Quadrature]
    order = SECOND
  []
[]

[Outputs]
  exodus = true
  csv = true
  print_linear_residuals = false

  [checkpoint]
    type = Checkpoint
    execute_on = 'FINAL'
    wall_time_interval = 10000000
    num_files = 999999
  []
[]
