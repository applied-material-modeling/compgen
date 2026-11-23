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

# GPU version of template.i (Kokkos assembly and materials, device PETSc). Run with
# --compute-device=<device>; compgen adds this in gpu mode.
#
# The problem is the same as template.i: large kinematics with the F-bar volumetric
# locking correction, the same homogenization constraints and targets, and Simo-Hughes J2
# plasticity with linear hardening (KokkosComputeSimoHughesJ2PlasticityStress).
# 3D plastic solid under periodic boundary conditions
# loaded in a direction indicated by theta and phi
# The model is a unit cube with two materials
#
# Macroscopic constraints (constraint_types is read column-major:
# xx yx zx xy yy zy xz yz zz). F_xy = F_xz = F_yz = 0 (strain) with
# P_yx = P_zx = P_zy = 0 (stress) makes F lower triangular and P upper
# triangular, so the Cauchy stress J^-1 P F^T is diagonal in the load axes,
# and rigid rotations are fixed. This is the same convention as the 2D plastic
# template (F_xy = 0), so 2D and 3D results share one convention.

theta = 0.0 # [0, pi]
phi = 0.0 # [0, 2*pi]

sy1 = 100.0
k1 = 1000.0
sy2 = 120.0
k2 = 1200.0

stress_max = 1200.0 # Should not control
eq_strain_max = 0.02 # Should cause termination

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

[Problem]
  # Give GAMG the 6 rigid body modes of the displacements as the near nullspace of the
  # displacement split, along with block size 3
  rigid_body_near_null_space_displacements = 'disp_x disp_y disp_z'
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
    type = KokkosDirichletBC
    variable = disp_x
    boundary = 'center'
    value = 0
  []
  [fix_center_y]
    type = KokkosDirichletBC
    variable = disp_y
    boundary = 'center'
    value = 0
  []
  [fix_center_z]
    type = KokkosDirichletBC
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

[Variables]
  [disp_x]
  []
  [disp_y]
  []
  [disp_z]
  []
  [hvar]
    family = SCALAR
    order = NINTH
  []
[]

[Kernels]
  [TM_all0]
    type = KokkosHomogenizedTotalLagrangianStressDivergence
    variable = disp_x
    component = 0
    displacements = 'disp_x disp_y disp_z'
    large_kinematics = true
    stabilize_strain = true
    macro_var = hvar
    constraint_types = 'stress stress stress strain stress stress strain strain stress'
    targets = 'value_xx zero zero zero value_yy zero zero zero value_zz'
  []
  [TM_all1]
    type = KokkosHomogenizedTotalLagrangianStressDivergence
    variable = disp_y
    component = 1
    displacements = 'disp_x disp_y disp_z'
    large_kinematics = true
    stabilize_strain = true
    macro_var = hvar
    constraint_types = 'stress stress stress strain stress stress strain strain stress'
    targets = 'value_xx zero zero zero value_yy zero zero zero value_zz'
  []
  [TM_all2]
    type = KokkosHomogenizedTotalLagrangianStressDivergence
    variable = disp_z
    component = 2
    displacements = 'disp_x disp_y disp_z'
    large_kinematics = true
    stabilize_strain = true
    macro_var = hvar
    constraint_types = 'stress stress stress strain stress stress strain strain stress'
    targets = 'value_xx zero zero zero value_yy zero zero zero value_zz'
  []
[]

[Materials]
  [all_strain]
    type = KokkosComputeDeformationGradient
    displacements = 'disp_x disp_y disp_z'
    large_kinematics = true
    stabilize_strain = true
    homogenization_gradient_names = homogenization_gradient
  []
  [fbar_average]
    type = KokkosComputeFbarAverage
    displacements = 'disp_x disp_y disp_z'
  []
  [all_compute_homogenization_gradient]
    type = KokkosComputeHomogenizedLagrangianStrain
    macro_gradient = hvar
    constraint_types = 'stress stress stress strain stress stress strain strain stress'
    targets = 'value_xx zero zero zero value_yy zero zero zero value_zz'
    homogenization_gradient_name = homogenization_gradient
  []
  [compute_stress_1]
    type = KokkosComputeSimoHughesJ2PlasticityStress
    youngs_modulus = 100000.0
    poissons_ratio = 0.3
    yield_stress = ${sy1}
    hardening_modulus = ${k1}
    stabilize_strain = true
    displacements = 'disp_x disp_y disp_z'
    block = 1
  []
  [compute_stress_2]
    type = KokkosComputeSimoHughesJ2PlasticityStress
    youngs_modulus = 100000.0
    poissons_ratio = 0.3
    yield_stress = ${sy2}
    hardening_modulus = ${k2}
    stabilize_strain = true
    displacements = 'disp_x disp_y disp_z'
    block = 2
  []

  # Outputs
  [compute_strain_output]
    type = KokkosComputeLagrangianIncrementalStrain
    large_kinematics = true
    strain = mechanical_strain
    effective_strain = equivalent_strain
  []
  [cauchy_stress_xx]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = cauchy_stress
    property_name = cauchy_stress_xx
    index_i = 0
    index_j = 0
  []
  [cauchy_stress_xy]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = cauchy_stress
    property_name = cauchy_stress_xy
    index_i = 0
    index_j = 1
  []
  [cauchy_stress_xz]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = cauchy_stress
    property_name = cauchy_stress_xz
    index_i = 0
    index_j = 2
  []
  [cauchy_stress_yy]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = cauchy_stress
    property_name = cauchy_stress_yy
    index_i = 1
    index_j = 1
  []
  [cauchy_stress_yz]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = cauchy_stress
    property_name = cauchy_stress_yz
    index_i = 1
    index_j = 2
  []
  [cauchy_stress_zz]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = cauchy_stress
    property_name = cauchy_stress_zz
    index_i = 2
    index_j = 2
  []
  [mechanical_strain_xx]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = mechanical_strain
    property_name = mechanical_strain_xx
    index_i = 0
    index_j = 0
  []
  [mechanical_strain_xy]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = mechanical_strain
    property_name = mechanical_strain_xy
    index_i = 0
    index_j = 1
  []
  [mechanical_strain_xz]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = mechanical_strain
    property_name = mechanical_strain_xz
    index_i = 0
    index_j = 2
  []
  [mechanical_strain_yy]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = mechanical_strain
    property_name = mechanical_strain_yy
    index_i = 1
    index_j = 1
  []
  [mechanical_strain_yz]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = mechanical_strain
    property_name = mechanical_strain_yz
    index_i = 1
    index_j = 2
  []
  [mechanical_strain_zz]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = mechanical_strain
    property_name = mechanical_strain_zz
    index_i = 2
    index_j = 2
  []
  [equivalent_stress]
    type = KokkosParsedMaterial
    property_name = equivalent_stress
    material_property_names = 'cauchy_stress_xx cauchy_stress_xy cauchy_stress_xz cauchy_stress_yy cauchy_stress_yz cauchy_stress_zz'
    expression = 'sqrt(0.5*((cauchy_stress_xx-cauchy_stress_yy)^2+(cauchy_stress_yy-cauchy_stress_zz)^2+(cauchy_stress_zz-cauchy_stress_xx)^2)+3*(cauchy_stress_xy^2+cauchy_stress_xz^2+cauchy_stress_yz^2))'
  []
[]

[AuxVariables]
  [cauchy_stress_xx]
    order = CONSTANT
    family = MONOMIAL
  []
  [cauchy_stress_xy]
    order = CONSTANT
    family = MONOMIAL
  []
  [cauchy_stress_xz]
    order = CONSTANT
    family = MONOMIAL
  []
  [cauchy_stress_yy]
    order = CONSTANT
    family = MONOMIAL
  []
  [cauchy_stress_yz]
    order = CONSTANT
    family = MONOMIAL
  []
  [cauchy_stress_zz]
    order = CONSTANT
    family = MONOMIAL
  []
  [mechanical_strain_xx]
    order = CONSTANT
    family = MONOMIAL
  []
  [mechanical_strain_xy]
    order = CONSTANT
    family = MONOMIAL
  []
  [mechanical_strain_xz]
    order = CONSTANT
    family = MONOMIAL
  []
  [mechanical_strain_yy]
    order = CONSTANT
    family = MONOMIAL
  []
  [mechanical_strain_yz]
    order = CONSTANT
    family = MONOMIAL
  []
  [mechanical_strain_zz]
    order = CONSTANT
    family = MONOMIAL
  []
  [equivalent_strain]
    order = CONSTANT
    family = MONOMIAL
  []
  [equivalent_stress]
    order = CONSTANT
    family = MONOMIAL
  []
[]

[AuxKernels]
  [cauchy_stress_xx]
    type = KokkosMaterialRealAux
    variable = cauchy_stress_xx
    property = cauchy_stress_xx
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [cauchy_stress_xy]
    type = KokkosMaterialRealAux
    variable = cauchy_stress_xy
    property = cauchy_stress_xy
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [cauchy_stress_xz]
    type = KokkosMaterialRealAux
    variable = cauchy_stress_xz
    property = cauchy_stress_xz
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [cauchy_stress_yy]
    type = KokkosMaterialRealAux
    variable = cauchy_stress_yy
    property = cauchy_stress_yy
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [cauchy_stress_yz]
    type = KokkosMaterialRealAux
    variable = cauchy_stress_yz
    property = cauchy_stress_yz
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [cauchy_stress_zz]
    type = KokkosMaterialRealAux
    variable = cauchy_stress_zz
    property = cauchy_stress_zz
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [mechanical_strain_xx]
    type = KokkosMaterialRealAux
    variable = mechanical_strain_xx
    property = mechanical_strain_xx
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [mechanical_strain_xy]
    type = KokkosMaterialRealAux
    variable = mechanical_strain_xy
    property = mechanical_strain_xy
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [mechanical_strain_xz]
    type = KokkosMaterialRealAux
    variable = mechanical_strain_xz
    property = mechanical_strain_xz
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [mechanical_strain_yy]
    type = KokkosMaterialRealAux
    variable = mechanical_strain_yy
    property = mechanical_strain_yy
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [mechanical_strain_yz]
    type = KokkosMaterialRealAux
    variable = mechanical_strain_yz
    property = mechanical_strain_yz
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [mechanical_strain_zz]
    type = KokkosMaterialRealAux
    variable = mechanical_strain_zz
    property = mechanical_strain_zz
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [equivalent_strain]
    type = KokkosMaterialRealAux
    variable = equivalent_strain
    property = equivalent_strain
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [equivalent_stress]
    type = KokkosMaterialRealAux
    variable = equivalent_stress
    property = equivalent_stress
    execute_on = 'INITIAL TIMESTEP_END'
  []
[]

[Postprocessors]
  [stress_xx]
    type = KokkosElementAverageValue
    variable = "cauchy_stress_xx"
  []
  [stress_yy]
    type = KokkosElementAverageValue
    variable = "cauchy_stress_yy"
  []
  [stress_zz]
    type = KokkosElementAverageValue
    variable = "cauchy_stress_zz"
  []
  [stress_yz]
    type = KokkosElementAverageValue
    variable = "cauchy_stress_yz"
  []
  [stress_xz]
    type = KokkosElementAverageValue
    variable = "cauchy_stress_xz"
  []
  [stress_xy]
    type = KokkosElementAverageValue
    variable = "cauchy_stress_xy"
  []

  [strain_xx]
    type = KokkosElementAverageValue
    variable = "mechanical_strain_xx"
  []
  [strain_yy]
    type = KokkosElementAverageValue
    variable = "mechanical_strain_yy"
  []
  [strain_zz]
    type = KokkosElementAverageValue
    variable = "mechanical_strain_zz"
  []
  [strain_yz]
    type = KokkosElementAverageValue
    variable = "mechanical_strain_yz"
  []
  [strain_xz]
    type = KokkosElementAverageValue
    variable = "mechanical_strain_xz"
  []
  [strain_xy]
    type = KokkosElementAverageValue
    variable = "mechanical_strain_xy"
  []

  [equivalent_strain]
    type = KokkosElementAverageValue
    variable = equivalent_strain
  []
  [equivalent_stress]
    type = KokkosElementAverageValue
    variable = equivalent_stress
  []
[]

[Preconditioning]
  # The macro-gradient scalar variable couples to every displacement DOF. Split it off with a
  # Schur complement (only a few unknowns). The displacement block is solved accurately (FGMRES
  # to rtol 1e-4) so that the Schur complement action is nearly exact and the outer FGMRES needs
  # only a few iterations; one GAMG cycle per outer iteration took ~100x more outer iterations
  # and was slower overall. PETSc's GAMG preconditions the inner solve (BoomerAMG on the extracted
  # displacement block was unreliable on the GPU and diverged under CG). GAMG gets the rigid
  # body modes and the block size from [Problem]/rigid_body_near_null_space_displacements.
  # Aggressive coarsening is off because it coarsens far too fast for elasticity with a large
  # stiffness contrast. The inner Krylov method is FGMRES rather than the CG of the small
  # strain templates because the large kinematics F-bar tangent is not symmetric. The rigid body
  # modes are evaluated in the reference configuration.
  [FSP]
    type = FSP
    topsplit = 'u_hvar'
    [u_hvar]
      splitting = 'u hvar'
      splitting_type = schur
      petsc_options_iname = '-pc_fieldsplit_schur_fact_type -pc_fieldsplit_schur_precondition -ksp_type -ksp_gmres_modifiedgramschmidt -ksp_gmres_restart -ksp_rtol -ksp_max_it'
      petsc_options_value = 'full selfp fgmres 1 100 1e-10 500'
    []
    [u]
      vars = 'disp_x disp_y disp_z'
      petsc_options_iname = '-ksp_type -ksp_rtol -pc_type -pc_gamg_type -pc_gamg_aggressive_coarsening -mg_levels_ksp_type -mg_levels_pc_type -mg_levels_ksp_max_it'
      petsc_options_value = 'fgmres 1e-4 gamg agg 0 chebyshev jacobi 3'
    []
    [hvar]
      vars = 'hvar'
      petsc_options_iname = '-ksp_type -pc_type'
      petsc_options_value = 'gmres jacobi'
    []
  []
[]

[Executioner]
  type = Transient

  solve_type = 'newton'
  line_search = none

  # Device-resident PETSc vectors and matrices
  petsc_options_iname = '-vec_type -nl0_mat_type'
  petsc_options_value = 'kokkos aijkokkos'

  residual_and_jacobian_together = true

  end_time = 5.0
  dtmin = 1e-4
  dt = 0.01
  l_max_its = 500
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

