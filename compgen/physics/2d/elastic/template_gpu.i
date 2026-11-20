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
# The problem is the same as template.i: the homogenization system with the same
# constraints and targets, small kinematics and the volumetric locking correction,
# through the QuasiStatic Physics with use_kokkos = true.
# 2D elastic solid under periodic boundary conditions
# The model is a unit square with two materials
#
# Rigid translation is removed by pinning the `center` node. A periodic
# fluctuation field cannot contain a rigid rotation, and the macroscopic
# gradient is fully prescribed (xx, xy, yy by `strain`, yx held at zero by
# `none`; constraint_types is read column-major), so no further constraint is
# needed. An extra pinned node would over-constrain the fluctuation field.

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
      displacements = 'disp_x disp_y'
      [all]
        strain = SMALL
        add_variables = true
        new_system = true
        formulation = TOTAL
        use_kokkos = true
        displacements = 'disp_x disp_y'
        volumetric_locking_correction = true
        constraint_types =  'strain none none strain strain none none none none'
        targets = 'value zero zero'

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
[]

[Materials]
  [elastic_tensor_1]
    type = KokkosComputeIsotropicLinearElasticStress
    youngs_modulus = 100000.0
    poissons_ratio = 0.3
    block = '1'
  []
  [elastic_tensor_2]
    type = KokkosComputeIsotropicLinearElasticStress
    youngs_modulus = 120000.0
    poissons_ratio = 0.21
    block = '2'
  []
  [compute_stress]
    type = KokkosComputeLagrangianStressCustomSmall
    custom_small_stress = stress
    custom_small_jacobian = Jacobian_mult
    stabilize_strain = true
  []

  # Outputs (the host Physics' generate_output)
  [compute_strain_output]
    type = KokkosComputeLagrangianIncrementalStrain
    large_kinematics = false
    strain = mechanical_strain
  []
  [cauchy_stress_xx]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = stress
    property_name = cauchy_stress_xx
    index_i = 0
    index_j = 0
  []
  [cauchy_stress_xy]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = stress
    property_name = cauchy_stress_xy
    index_i = 0
    index_j = 1
  []
  [cauchy_stress_xz]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = stress
    property_name = cauchy_stress_xz
    index_i = 0
    index_j = 2
  []
  [cauchy_stress_yy]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = stress
    property_name = cauchy_stress_yy
    index_i = 1
    index_j = 1
  []
  [cauchy_stress_yz]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = stress
    property_name = cauchy_stress_yz
    index_i = 1
    index_j = 2
  []
  [cauchy_stress_zz]
    type = KokkosRankTwoCartesianComponent
    rank_two_tensor = stress
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
  [strain_xy]
    type = KokkosElementAverageValue
    variable = "mechanical_strain_xy"
  []
[]

[Preconditioning]
  # The macro-gradient scalar variable couples to every displacement DOF. Split it off with a
  # Schur complement (only a few unknowns) so the displacement block can use algebraic
  # multigrid on the device. PETSc's GAMG is used for that block: BoomerAMG on the extracted
  # displacement block was unreliable on the GPU. The displacement block applies one GAMG
  # cycle (the outer FGMRES, with modified Gram-Schmidt and a long restart, does the rest).
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
      vars = 'disp_x disp_y'
      petsc_options_iname = '-ksp_type -pc_type -pc_gamg_type -mg_levels_ksp_type -mg_levels_pc_type'
      petsc_options_value = 'preonly gamg agg chebyshev jacobi'
    []
    [hvar]
      vars = 'hvar'
      petsc_options_iname = '-ksp_type -pc_type'
      petsc_options_value = 'gmres jacobi'
    []
  []
[]

[Executioner]
  type = Steady

  solve_type = 'newton'
  line_search = none

  # Device-resident PETSc vectors and matrices
  petsc_options_iname = '-vec_type -nl0_mat_type'
  petsc_options_value = 'kokkos aijkokkos'

  residual_and_jacobian_together = true

  l_max_its = 500
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

