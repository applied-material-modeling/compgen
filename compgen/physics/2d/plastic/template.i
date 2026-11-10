# Copyright 2026, UChicago Argonne, LLC
# All Rights Reserved
# Software Name: compgen
# By: Argonne National Laboratory
# OPEN SOURCE LICENSE (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# 2D plastic solid under periodic boundary conditions
# loaded in a direction indicated by theta
# The model is a unit square with two materials

theta = 0.0

sy1 = 100.0
k1 = 1000.0
sy2 = 120.0
k2 = 1200.0

stress_max = 1200.0 # Should not control
eq_strain_max = 0.02 # Should cause termination

[GlobalParams]
  displacements = 'disp_x disp_y'
  large_kinematics = true
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

  [fix_center_x]
    type = DirichletBC
    boundary = center
    value = 0
    variable = disp_x
  []
  [fix_center_y]
    type = DirichletBC
    boundary = center
    value = 0
    variable = disp_y
  []
[]

[Functions]
  [value_xx]
    type = ParsedFunction
    expression = '${stress_max} * cos(${theta}) * t'
  []
  [value_yy]
    type = ParsedFunction
    expression = '${stress_max} * sin(${theta}) * t'
  []
  [zero]
    type = ConstantFunction
    value = 0
  []
[]

[Materials]
  [cauchy_stress_xx_all]
    type = RankTwoCartesianComponent
    index_i = 0
    index_j = 0
    outputs = none
    property_name = cauchy_stress_xx
    rank_two_tensor = cauchy_stress
  []
  [cauchy_stress_xy_all]
    type = RankTwoCartesianComponent
    index_i = 0
    index_j = 1
    outputs = none
    property_name = cauchy_stress_xy
    rank_two_tensor = cauchy_stress
  []
  [cauchy_stress_xz_all]
    type = RankTwoCartesianComponent
    index_i = 0
    index_j = 2
    outputs = none
    property_name = cauchy_stress_xz
    rank_two_tensor = cauchy_stress
  []
  [cauchy_stress_yy_all]
    type = RankTwoCartesianComponent
    index_i = 1
    index_j = 1
    outputs = none
    property_name = cauchy_stress_yy
    rank_two_tensor = cauchy_stress
  []
  [cauchy_stress_yz_all]
    type = RankTwoCartesianComponent
    block = ''
    index_i = 1
    index_j = 2
    outputs = none
    property_name = cauchy_stress_yz
    rank_two_tensor = cauchy_stress
  []
  [cauchy_stress_zz_all]
    type = RankTwoCartesianComponent
    index_i = 2
    index_j = 2
    outputs = none
    property_name = cauchy_stress_zz
    rank_two_tensor = cauchy_stress
  []
  [mechanical_strain_xx_all]
    type = RankTwoCartesianComponent
    index_i = 0
    index_j = 0
    outputs = none
    property_name = mechanical_strain_xx
    rank_two_tensor = mechanical_strain
  []
  [mechanical_strain_xy_all]
    type = RankTwoCartesianComponent
    index_i = 0
    index_j = 1
    outputs = none
    property_name = mechanical_strain_xy
    rank_two_tensor = mechanical_strain
  []
  [mechanical_strain_xz_all]
    type = RankTwoCartesianComponent
    index_i = 0
    index_j = 2
    outputs = none
    property_name = mechanical_strain_xz
    rank_two_tensor = mechanical_strain
  []
  [mechanical_strain_yy_all]
    type = RankTwoCartesianComponent
    index_i = 1
    index_j = 1
    outputs = none
    property_name = mechanical_strain_yy
    rank_two_tensor = mechanical_strain
  []
  [mechanical_strain_yz_all]
    type = RankTwoCartesianComponent
    index_i = 1
    index_j = 2
    outputs = none
    property_name = mechanical_strain_yz
    rank_two_tensor = mechanical_strain
  []
  [mechanical_strain_zz_all]
    type = RankTwoCartesianComponent
    index_i = 2
    index_j = 2
    outputs = none
    property_name = mechanical_strain_zz
    rank_two_tensor = mechanical_strain
  []
  [equivalent_strain_all]
    type = RankTwoInvariant
    property_name = equivalent_strain
    rank_two_tensor = mechanical_strain
    invariant = EffectiveStrain
  []
  [equivalent_stress_all]
    type = RankTwoInvariant
    property_name = equivalent_stress
    rank_two_tensor = cauchy_stress
    invariant = VonMisesStress
  []

  [elastic_tensor_1]
    type = ComputeIsotropicElasticityTensor
    youngs_modulus = 100000.0
    poissons_ratio = 0.3
    block = 1
  []
  [flow_stress_1]
    type = DerivativeParsedMaterial
    property_name = flow_stress
    expression = '${sy1} + ${k1} * effective_plastic_strain'
    material_property_names = 'effective_plastic_strain'
    additional_derivative_symbols = 'effective_plastic_strain'
    derivative_order = 2
    compute = false
    block = 1
  []
  [compute_stress_1]
    type = ComputeSimoHughesJ2PlasticityStress
    flow_stress_material = flow_stress_1
    block = 1
  []
  [elastic_tensor_2]
    type = ComputeIsotropicElasticityTensor
    youngs_modulus = 100000.0
    poissons_ratio = 0.3
    block = 2
  []
  [flow_stress_2]
    type = DerivativeParsedMaterial
    property_name = flow_stress
    expression = '${sy2} + ${k2} * effective_plastic_strain'
    material_property_names = 'effective_plastic_strain'
    additional_derivative_symbols = 'effective_plastic_strain'
    derivative_order = 2
    compute = false
    block = 2
  []
  [compute_stress_2]
    type = ComputeSimoHughesJ2PlasticityStress
    flow_stress_material = flow_stress_2
    block = 2
  []
[]

[Variables]
  [disp_x]
    type = MooseVariable
    family = LAGRANGE
    order = FIRST
  []
  [disp_y]
    type = MooseVariable
    family = LAGRANGE
    order = FIRST
  []
[]

[AuxKernels]
  [cauchy_stress_xx_all]
    type = MaterialRealAux
    property = cauchy_stress_xx
    variable = cauchy_stress_xx
  []
  [cauchy_stress_xy_all]
    type = MaterialRealAux
    property = cauchy_stress_xy
    variable = cauchy_stress_xy
  []
  [cauchy_stress_xz_all]
    type = MaterialRealAux
    property = cauchy_stress_xz
    variable = cauchy_stress_xz
  []
  [cauchy_stress_yy_all]
    type = MaterialRealAux
    property = cauchy_stress_yy
    variable = cauchy_stress_yy
  []
  [cauchy_stress_yz_all]
    type = MaterialRealAux
    property = cauchy_stress_yz
    variable = cauchy_stress_yz
  []
  [cauchy_stress_zz_all]
    type = MaterialRealAux
    property = cauchy_stress_zz
    variable = cauchy_stress_zz
  []
  [mechanical_strain_xx_all]
    type = MaterialRealAux
    property = mechanical_strain_xx
    variable = mechanical_strain_xx
  []
  [mechanical_strain_xy_all]
    type = MaterialRealAux
    property = mechanical_strain_xy
    variable = mechanical_strain_xy
  []
  [mechanical_strain_xz_all]
    type = MaterialRealAux
    property = mechanical_strain_xz
    variable = mechanical_strain_xz
  []
  [mechanical_strain_yy_all]
    type = MaterialRealAux
    property = mechanical_strain_yy
    variable = mechanical_strain_yy
  []
  [mechanical_strain_yz_all]
    type = MaterialRealAux
    property = mechanical_strain_yz
    variable = mechanical_strain_yz
  []
  [mechanical_strain_zz_all]
    type = MaterialRealAux
    property = mechanical_strain_zz
    variable = mechanical_strain_zz
  []
  [equivalent_strain_all]
    type = MaterialRealAux
    property = equivalent_strain
    variable = equivalent_strain
  []
  [equivalent_stress_all]
    type = MaterialRealAux
    property = equivalent_stress
    variable = equivalent_stress
  []
[]

[AuxVariables]
  [cauchy_stress_xx]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [cauchy_stress_xy]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [cauchy_stress_xz]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [cauchy_stress_yy]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [cauchy_stress_yz]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [cauchy_stress_zz]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [mechanical_strain_xx]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [mechanical_strain_xy]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [mechanical_strain_xz]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [mechanical_strain_yy]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [mechanical_strain_yz]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [mechanical_strain_zz]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [equivalent_strain]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
  [equivalent_stress]
    type = MooseVariableConstMonomial
    family = MONOMIAL
    order = CONSTANT
  []
[]

[Kernels]
  [TM_all0]
    type = HomogenizedTotalLagrangianStressDivergence
    component = 0
    constraint_types = 'stress stress none strain stress none none none none'
    macro_var = hvar
    off_diagonal_jacobian = true
    stabilize_strain = true
    targets = 'value_xx zero zero value_yy'
    variable = disp_x
  []
  [TM_all1]
    type = HomogenizedTotalLagrangianStressDivergence
    component = 1
    constraint_types = 'stress stress none strain stress none none none none'
    macro_var = hvar
    off_diagonal_jacobian = true
    stabilize_strain = true
    targets = 'value_xx zero zero value_yy'
    variable = disp_y
  []
[]

[Materials]
  [all_strain]
    type = ComputeLagrangianStrain
    displacements = 'disp_x disp_y'
    homogenization_gradient_names = homogenization_gradient
    stabilize_strain = true
  []
  [all_compute_homogenization_gradient]
    type = ComputeHomogenizedLagrangianStrain
    constraint_types = 'stress stress none strain stress none none none none'
    homogenization_gradient_name = homogenization_gradient
    macro_gradient = hvar
    targets = 'value_xx zero zero value_yy'
  []
[]

[Variables]
  [hvar]
    type = MooseVariableScalar
    family = SCALAR
    order = FOURTH
  []
[]

[Postprocessors]
  [strain_xx]
    type = ElementAverageValue
    variable = mechanical_strain_xx
  []
  [strain_xy]
    type = ElementAverageValue
    variable = mechanical_strain_xy
  []
  [strain_yy]
    type = ElementAverageValue
    variable = mechanical_strain_yy
  []
  [stress_xx]
    type = ElementAverageValue
    variable = cauchy_stress_xx
  []
  [stress_xy]
    type = ElementAverageValue
    variable = cauchy_stress_xy
  []
  [stress_yy]
    type = ElementAverageValue
    variable = cauchy_stress_yy
  []
  [equivalent_strain]
    type = ElementAverageValue
    variable = equivalent_strain
  []
  [equivalent_stress]
    type = ElementAverageValue
    variable = equivalent_stress
  []
[]

[Executioner]
  type = Transient

  solve_type = 'newton'
  line_search = none

  petsc_options_iname = '-pc_type -pc_factor_mat_solver_package -ksp_type'
  petsc_options_value = 'lu superlu_dist gmres'

  end_time = 5.0
  dtmin = 1e-4
  dt = 0.01

  l_max_its = 1
  l_tol = 1e-6
  nl_max_its = 30
  nl_rel_tol = 1e-6
  nl_abs_tol = 1e-8

[]

[UserObjects]
  [terminator]
    type = Terminator
    expression = 'equivalent_strain > ${eq_strain_max}'
    fail_mode = HARD
    execute_on = TIMESTEP_END
  []
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
