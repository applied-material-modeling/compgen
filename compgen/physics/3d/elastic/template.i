# 3D elastic solid under periodic boundary conditions

[GlobalParams]
  displacements = 'disp_x disp_y disp_z'
[]

[Mesh]
  [base]
    type = FileMeshGenerator
    file = 'mesh.exo'
  []

  [sidesets]
    type = SideSetsFromNormalsGenerator
    input = base
    normals = '-1 0 0 
                1 0 0 
                0 -1 0 
                0 1 0
                0 0 -1
                0 0 1'
    new_boundary = 'left right bottom top back front'
  []

  [center]
    type = ExtraNodesetGenerator
    input = sidesets
    coord = '0.5 0.5 0.5'
    use_closest_node = true
    new_boundary = 'center'
  []

  [up]
    type = ExtraNodesetGenerator
    input = center
    coord = '0.5 0.75 0.5'
    use_closest_node = true
    new_boundary = 'up'
  []

  [forward]
    type = ExtraNodesetGenerator
    input = up
    coord = '0.5 0.5 0.75'
    use_closest_node = true
    new_boundary = 'forward'
  []
[]

[Physics]
  [SolidMechanics]
    [QuasiStatic]
      [all]
        strain = SMALL
        add_variables = true
        new_system = true
        formulation = TOTAL
        volumetric_locking_correction = true
        constraint_types =  'strain none none strain strain none strain strain strain' 
        targets = 'value zero zero zero zero zero'
        generate_output = 'cauchy_stress_xx cauchy_stress_xy cauchy_stress_xz cauchy_stress_yy '
                          'cauchy_stress_yz cauchy_stress_zz '
                          'mechanical_strain_xx mechanical_strain_xy mechanical_strain_xz mechanical_strain_yy '
                          'mechanical_strain_yz mechanical_strain_zz '

      []
    []
  []
[]

[Functions]
  [value]
    type = ConstantFunction
    value = 1
  []
  [zero]
    type = ConstantFunction
    value = 0
  []
[]

[BCs]
  [Periodic]
    [x]
      variable = disp_x
      auto_direction = 'x y z'
    []
    [y]
      variable = disp_y
      auto_direction = 'x y z'
    []
    [z]
      variable = disp_z
      auto_direction = 'x y z'
    []
  []
  
  # Grab a node near the center to fix rigid body motion
  [fix_center_x]
    type = DirichletBC
    variable = disp_x
    boundary = 'center'
    value = 0
  []
  [fix_center_y]
    type = DirichletBC
    variable = disp_y
    boundary = 'center'
    value = 0
  []
  [fix_center_z]
    type = DirichletBC
    variable = disp_z
    boundary = 'center'
    value = 0
  []
  # Now prevent rigid rotation
  [apply_up_x]
    type = DirichletBC
    variable = disp_x
    boundary = 'up'
    value = 0
  []
  [apply_up_z]
    type = DirichletBC
    variable = disp_z
    boundary = 'up'
    value = 0
  []
  [apply_forward_x]
    type = DirichletBC
    variable = disp_x
    boundary = 'forward'
    value = 0
  []
[]

[Materials]
  [elastic_tensor_1]
    type = ComputeIsotropicElasticityTensor
    youngs_modulus = 100000.0
    poissons_ratio = 0.3
    block = '1'
  []
  [elastic_tensor_2]
    type = ComputeIsotropicElasticityTensor
    youngs_modulus = 120000.0
    poissons_ratio = 0.21
    block = '2'
  []
  [compute_stress]
    type = ComputeLagrangianLinearElasticStress
    large_kinematics = false
  []
[]

[Postprocessors]
  [stress_xx]
    type = ElementAverageValue
    variable = "cauchy_stress_xx"
  []
  [stress_yy]
    type = ElementAverageValue
    variable = "cauchy_stress_yy"
  []
  [stress_zz]
    type = ElementAverageValue
    variable = "cauchy_stress_zz"
  []
  [stress_yz]
    type = ElementAverageValue
    variable = "cauchy_stress_yz"
  []
  [stress_xz]
    type = ElementAverageValue
    variable = "cauchy_stress_xz"
  []
  [stress_xy]
    type = ElementAverageValue
    variable = "cauchy_stress_xy"
  []

  [strain_xx]
    type = ElementAverageValue
    variable = "mechanical_strain_xx"
  []
  [strain_yy]
    type = ElementAverageValue
    variable = "mechanical_strain_yy"
  []
  [strain_zz]
    type = ElementAverageValue
    variable = "mechanical_strain_zz"
  []
  [strain_yz]
    type = ElementAverageValue
    variable = "mechanical_strain_yz"
  []
  [strain_xz]
    type = ElementAverageValue
    variable = "mechanical_strain_xz"
  []
  [strain_xy]
    type = ElementAverageValue
    variable = "mechanical_strain_xy"
  []
[]

[Preconditioning]
  [FSP]
    type = FSP
    topsplit = 'u_hvar'
    [u_hvar]
      splitting = 'u hvar'
      splitting_type = schur
      petsc_options = '-ksp_monitor'
      petsc_options_iname = '-pc_fieldsplit_schur_fact_type  -pc_fieldsplit_schur_precondition -ksp_max_it -ksp_gmres_restart -ksp_type -ksp_pc_side -ksp_rtol'
      petsc_options_value = 'full                            selfp                             100         101                fgmres    right        1e-4'
    []
    [u]
      vars = 'disp_x disp_y disp_z'
      petsc_options = '-ksp_monitor'
      petsc_options_iname = '-ksp_type -ksp_gmres_restart -pc_type -pc_gamg_type -pc_gamg_threshold -pc_gamg_aggressive_square_graph -pc_gamg_aggressive_coarsening -pc_gamg_coarse_eq_limit -pc_gamg_process_eq_limit -mg_levels_ksp_type -mg_levels_ksp_max_it -mg_levels_pc_type -mg_coarse_ksp_type -mg_coarse_pc_type -mg_coarse_pc_factor_mat_solver_type -ksp_atol -ksp_rtol'
      petsc_options_value = 'fgmres 50 gamg agg 0.45 true 1 1000 5000 chebyshev 1 sor preonly lu superlu_dist 1e-3 1e-4'
    []
    [hvar]
      vars = 'hvar'
      petsc_options_iname = '-pc_type'
      petsc_options_value = 'lu'
    []
  []
[]

[Executioner]
  type = Steady

  solve_type = 'newton'
  line_search = none

  automatic_scaling = true

  l_max_its = 500
  l_tol = 1e-12
  nl_max_its = 2
  nl_rel_tol = 1e-4
  nl_abs_tol = 1e-4
[]

[Outputs]
  file_base = 'output'
  [exodus]
    type = Exodus
  []
  [csv]
    type = CSV
  []
[]
