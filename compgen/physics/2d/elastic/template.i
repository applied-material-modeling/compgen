# 2D elastic solid under periodic boundary conditions
# The model is a unit square with two materials
#
# Variant of template.i with the redundant `up` node constraint removed.
# Rigid translation is removed by pinning the `center` node; rigid rotation
# of the periodic fluctuation field is excluded by periodicity, and the macro
# rotation is pinned by the off-diagonal `strain` constraint on the yx gradient
# component (constraint_types below). The `apply_up_x` Dirichlet BC is therefore
# expected to be redundant.

[GlobalParams]
  displacements = 'disp_x disp_y'
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
                0 1 0'
    new_boundary = 'left right bottom top'
  []

  [center]
    type = ExtraNodesetGenerator
    input = sidesets
    coord = '0.5 0.5'
    use_closest_node = true
    new_boundary = 'center'
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
        constraint_types =  'strain none none strain strain none none none none'
        targets = 'value zero zero'
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
      auto_direction = 'x y'
    []
    [y]
      variable = disp_y
      auto_direction = 'x y'
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

[Preconditioning]
  [smp]
    type = SMP
    full = true
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
  [strain_xy]
    type = ElementAverageValue
    variable = "mechanical_strain_xy"
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
