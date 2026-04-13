template_text = """E_A = 10000
nu_A = 0.2
K_A = '${fparse E_A/3/(1-2*nu_A)}'
G_A = '${fparse E_A/2/(1+nu_A)}'

E_B = 20000
nu_B = 0.3
K_B = '${fparse E_B/3/(1-2*nu_B)}'
G_B = '${fparse E_B/2/(1+nu_B)}'

Gc_A = 0.8
psic_A = 1.87

Gc_B = 1
psic_B = 1.96

l = 0.03

# interface
GI_c = 2
GII_c = 1
N = 35
T = 15
eta = 2.2

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
    file = '/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/mesh.exo'
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
    input = 'sidesets'
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
    viscosity = 0
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
   []
   [stress_yy_aux]
     type = ADRankTwoAux
     variable = stress_yy
     rank_two_tensor = stress
     index_i = 1
     index_j = 1
   []
   [stress_xy_aux]
     type = ADRankTwoAux
     variable = stress_xy
     rank_two_tensor = stress
     index_i = 0
     index_j = 1
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
  dt = 2e-4
  end_time = 0.001
  nl_abs_tol = 1e-08
  nl_rel_tol = 1e-06
  automatic_scaling = true
  reuse_preconditioner = true

  [Quadrature]
    order = CONSTANT
  []
[]

[Outputs]
  exodus = true
  csv = true
  print_linear_residuals = false
[]
"""

fracture_text = """[Mesh]
  [fmg]
    type = FileMeshGenerator
    file = '/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/mesh.exo'
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
  nl_max_its = 50

  dt = 1e12

  [Quadrature]
    order = CONSTANT
  []
[]

[Outputs]
  print_linear_residuals = false
[]
"""

t_path = "/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/compgen/physics/2d/fracture/template.i"
f_path = "/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/compgen/physics/2d/fracture/fracture.i"

with open(t_path, "w") as f:
    f.write(template_text)

with open(f_path, "w") as f:
    f.write(fracture_text)

print("Successfully deployed new PFF+CZM templates with SideSetsFromNormalsGenerator.")
