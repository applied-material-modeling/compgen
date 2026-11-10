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

theta = 0.0 # [0, pi]
phi = 0.0 # [0, 2*pi]

sy1 = 100.0
k1 = 1000.0
sy2 = 120.0
k2 = 1200.0

stress_max = 1200.0 # Should not control
eq_strain_max = 0.02 # Should cause termination

[GlobalParams]
  displacements = 'disp_x disp_y disp_z'
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
[]

[Functions]
  [value_xx]
    type = ParsedFunction
    expression = '${stress_max} * sin(${theta}) * cos(${phi}) * t'
  []
  [value_yy]
    type = ParsedFunction
    expression = '${stress_max} * sin(${theta}) * sin(${phi}) * t'
  []
  [value_zz]
    type = ParsedFunction
    expression = '${stress_max} * cos(${theta}) * t'
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
  [disp_z]
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
    constraint_types = 'stress strain strain stress stress strain stress stress stress' 
    macro_var = hvar
    off_diagonal_jacobian = true
    stabilize_strain = true
    targets = 'value_xx zero zero zero value_yy zero zero zero value_zz'
    variable = disp_x
  []
  [TM_all1]
    type = HomogenizedTotalLagrangianStressDivergence
    component = 1
    constraint_types = 'stress strain strain stress stress strain stress stress stress'  
    macro_var = hvar
    off_diagonal_jacobian = true
    stabilize_strain = true
    targets = 'value_xx zero zero zero value_yy zero zero zero value_zz'
    variable = disp_y
  []
  [TM_all2]
    type = HomogenizedTotalLagrangianStressDivergence
    component = 2
    constraint_types = 'stress strain strain stress stress strain stress stress stress' 
    macro_var = hvar
    off_diagonal_jacobian = true
    stabilize_strain = true
    targets = 'value_xx zero zero zero value_yy zero zero zero value_zz'
    variable = disp_z
  []
[]

[Materials]
  [all_strain]
    type = ComputeLagrangianStrain
    homogenization_gradient_names = homogenization_gradient
    stabilize_strain = true
  []
  [all_compute_homogenization_gradient]
    type = ComputeHomogenizedLagrangianStrain
    constraint_types = 'stress strain strain stress stress strain stress stress stress' 
    homogenization_gradient_name = homogenization_gradient
    macro_gradient = hvar
    targets = 'value_xx zero zero zero value_yy zero zero zero value_zz'
  []
[]

[Variables]
  [hvar]
    type = MooseVariableScalar
    family = SCALAR
    order = NINTH
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

  [equivalent_strain]
    type = ElementAverageValue
    variable = equivalent_strain
  []
  [equivalent_stress]
    type = ElementAverageValue
    variable = equivalent_stress
  []
[]

[Preconditioning]
  [FSP]
    type = FSP
    topsplit = 'u_hvar'
    [u_hvar]
      splitting = 'u hvar'
      splitting_type = schur
      petsc_options_iname = '-pc_fieldsplit_schur_fact_type  -pc_fieldsplit_schur_precondition -ksp_max_it -ksp_gmres_restart -ksp_type -ksp_pc_side -ksp_rtol'
      petsc_options_value = 'full                            selfp                             100         101                fgmres    right        1e-4'
    []
    [u]
      vars = 'disp_x disp_y disp_z'
      petsc_options_iname = '-ksp_type -ksp_gmres_restart -pc_type -pc_gamg_type -pc_gamg_threshold -pc_gamg_aggressive_square_graph -pc_gamg_aggressive_coarsening -pc_gamg_coarse_eq_limit -pc_gamg_process_eq_limit -mg_levels_ksp_type -mg_levels_ksp_max_it -mg_levels_pc_type -mg_coarse_ksp_type -mg_coarse_pc_type -mg_coarse_pc_factor_mat_solver_type -ksp_atol -ksp_rtol'
      petsc_options_value = 'fgmres 50 gamg agg 0.2 true 1 1000 5000 chebyshev 1 sor preonly lu superlu_dist 1e-3 1e-4'
    []
    [hvar]
      vars = 'hvar'
      petsc_options_iname = '-pc_type'
      petsc_options_value = 'lu'
    []
  []
[]

[Executioner]
  type = Transient

  solve_type = 'newton'
  line_search = none

  end_time = 5.0
  dtmin = 1e-4
  dt = 0.01

  l_max_its = 500
  l_tol = 1e-3
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
