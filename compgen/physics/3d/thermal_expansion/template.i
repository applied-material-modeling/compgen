# 2D elastic solid under periodic boundary conditions
# The model is a unit square with two materials

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

[AuxVariables]
  [temp]
    order = FIRST
    family = LAGRANGE
  []
[]

[AuxKernels]
  [temp]
    type = ConstantAux
    variable = temp
    value = 1
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
        constraint_types =  'stress none none stress stress none stress stress stress' 
        targets = 'zero zero zero zero zero zero'
        generate_output = 'cauchy_stress_xx cauchy_stress_xy cauchy_stress_xz cauchy_stress_yy '
                          'cauchy_stress_yz cauchy_stress_zz '
                          'strain_xx strain_xy strain_xz strain_yy '
                          'strain_yz strain_zz '
        eigenstrain_names = 'thermal_strain'
        temperature = temp
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
  [thermal_strain_1]
    type = ComputeThermalExpansionEigenstrain
    stress_free_temperature = 0
    thermal_expansion_coefficient = 1e-5
    eigenstrain_name = thermal_strain
    block = '1'
    temperature = temp
  []
  [thermal_strain_2]
    type = ComputeThermalExpansionEigenstrain
    stress_free_temperature = 0
    thermal_expansion_coefficient = 2e-5
    eigenstrain_name = thermal_strain
    block = '2'
    temperature = temp
  []
[]

[Preconditioning]
  [smp]
    type = SMP
    full = true
  []
[]

[Postprocessors]
  [strain_xx]
    type = ElementAverageValue
    variable = "strain_xx"
  []
  [strain_yy]
    type = ElementAverageValue
    variable = "strain_yy"
  []
  [strain_zz]
    type = ElementAverageValue
    variable = "strain_zz"
  []
  [strain_yz]
    type = ElementAverageValue
    variable = "strain_yz"
  []
  [strain_xz]
    type = ElementAverageValue
    variable = "strain_xz"
  []
  [strain_xy]
    type = ElementAverageValue
    variable = "strain_xy"
  []
  [temperature]
    type = ElementAverageValue
    variable = "temperature"
  []
[]

[Executioner]
  type = Steady

  solve_type = 'newton'
  line_search = none

  petsc_options_iname = '-pc_type'
  petsc_options_value = 'lu'

  l_max_its = 2
  l_tol = 1e-14
  nl_max_its = 20
  nl_rel_tol = 1e-8
  nl_abs_tol = 1e-10

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
