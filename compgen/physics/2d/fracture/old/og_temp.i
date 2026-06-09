E_A = 100000
nu_A = 0.3
K_A = '${fparse E_A/3/(1-2*nu_A)}'
G_A = '${fparse E_A/2/(1+nu_A)}'

E_B = 100000
nu_B = 0.3
K_B = '${fparse E_B/3/(1-2*nu_B)}'
G_B = '${fparse E_B/2/(1+nu_B)}'

Gc_A = 1
psic_A = 2.64

Gc_B = 1
psic_B = 2.64

l = 0.03

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
    type = MultiAppCopyTransfer
    from_multi_app = fracture
    variable = 'd'
    source_variable = 'd'
  []
  [to_fracture]
    type = MultiAppCopyTransfer
    to_multi_app = fracture
    variable = 'psie_active'
    source_variable = 'psie_active'
  []
[]

[Problem]
  type = ReferenceResidualProblem
[]

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
  [disp_x]
  []
  [disp_y]
  []
[]

[AuxVariables]
  [d]
  []
  [psie_active]
    order = CONSTANT
    family = MONOMIAL
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
   [psie_active_aux]
     type = ADMaterialRealAux
     variable = psie_active
     property = psie_active
     execute_on = 'INITIAL TIMESTEP_END'
   []
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
  []
  [solid_y]
    type = ADStressDivergenceTensors
    variable = disp_y
    component = 1
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
  [elasticity]
    type = SmallDeformationIsotropicElasticity
    bulk_modulus = K
    shear_modulus = G
    phase_field = d
    degradation_function = g
    decomposition = NONE
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
    type = ADSidesetReaction
    boundary = 'top'
    stress_tensor = 'stress'
    direction = '0 1 0'
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
  petsc_options_iname = '-pc_type -pc_factor_mat_solver_package'
  petsc_options_value = 'lu       superlu_dist'
  dt = 1e-4
  end_time = 4e-4
  automatic_scaling = true
  reuse_preconditioner = true

  [Quadrature]
    order = SECOND
  []
[]

[Outputs]
  exodus = true
  csv = true
[]
