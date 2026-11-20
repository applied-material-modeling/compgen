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

# 2D heat transfer with pseudo-periodic boundary conditions -- GPU version
# The model is a unit square with two materials and a penalty interface
#
# Kokkos residual/Jacobian assembly and PETSc linear algebra run on the device. Run with
# --compute-device=<device> (compgen adds this in gpu mode).
#
# Same problem as template.i: a periodic temperature fluctuation T driven by an imposed
# macroscopic gradient G (top-level g* values), int k (grad T + G) . grad(psi) = 0, with
# KokkosHeatConductionHomogenized in place of ADHeatConductionHomogenized.

# Macroscopic temperature gradient (load case); compgen sets these from the command line
gx = 1
gy = 0

# Phase conductivities; compgen sets these from the command line
k1 = 1
k2 = 100

[Mesh]
  [base]
    type = FileMeshGenerator
    file = 'mesh.exo'
  []
  # Fixed block names (IDs unchanged) so the broken interface sides are always
  # named a_b (block 1 side) and b_a (block 2 side)
  [names]
    type = RenameBlockGenerator
    input = base
    old_block = '1 2'
    new_block = 'a b'
  []
  [bm]
    type = BreakMeshByBlockGenerator
    input = names
  []

  [sidesets]
    type = SideSetsFromNormalsGenerator
    input = bm
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

[Variables]
  [temp]
    initial_condition = 0.0
  []
[]

[Kernels]
  [heat_conduction]
    type = KokkosHeatConductionHomogenized
    variable = temp
    thermal_conductivity = 'k'
    imposed_gradient = '${gx} ${gy} 0'
  []
[]

[Functions]
  [gx_fn]
    type = ConstantFunction
    value = ${gx}
  []
  [gy_fn]
    type = ConstantFunction
    value = ${gy}
  []
[]

[InterfaceKernels]
  [penalty]
    type = KokkosHeatPenaltyInterface
    variable = temp
    neighbor_var = temp
    boundary = 'a_b'
    penalty = 50
  []
[]

[BCs]
  [Periodic]
    [T]
      variable = temp
      auto_direction = 'x y'
    []
  []
  [fix_center]
    type = KokkosDirichletBC
    variable = temp
    boundary = 'center'
    value = 0
  []
[]

[Materials]
  # Conductivity on the device, used by the solve
  [mat_k_1]
    type = KokkosGenericConstantMaterial
    prop_names = 'k'
    prop_values = '${k1}'
    block = 1
  []
  [mat_k_2]
    type = KokkosGenericConstantMaterial
    prop_names = 'k'
    prop_values = '${k2}'
    block = 2
  []

  # Output-only host recomputation of the total gradient and flux from the converged
  # temperature (consumed only by the TIMESTEP_END aux kernels, so it does not run during the
  # solve).
  [host_k_1]
    type = ADGenericConstantMaterial
    prop_names = 'k_host'
    prop_values = '${k1}'
    block = 1
  []
  [host_k_2]
    type = ADGenericConstantMaterial
    prop_names = 'k_host'
    prop_values = '${k2}'
    block = 2
  []
  [calculate_output]
    type = FluxOutputMaterial
    temp = temp
    thermal_conductivity = 'k_host'
    targets = 'gx_fn gy_fn'
  []
[]

[AuxVariables]
  [gradient_x]
    order = CONSTANT
    family = MONOMIAL
  []
  [gradient_y]
    order = CONSTANT
    family = MONOMIAL
  []
  [q_x]
    order = CONSTANT
    family = MONOMIAL
  []
  [q_y]
    order = CONSTANT
    family = MONOMIAL
  []
[]

[AuxKernels]
  [gradient_x]
    type = ADMaterialRealVectorValueAux
    property = total_temperature_gradient
    variable = gradient_x
    component = 0
    execute_on = TIMESTEP_END
  []
  [gradient_y]
    type = ADMaterialRealVectorValueAux
    property = total_temperature_gradient
    variable = gradient_y
    component = 1
    execute_on = TIMESTEP_END
  []
  [q_x]
    type = ADMaterialRealVectorValueAux
    property = flux
    variable = q_x
    component = 0
    execute_on = TIMESTEP_END
  []
  [q_y]
    type = ADMaterialRealVectorValueAux
    property = flux
    variable = q_y
    component = 1
    execute_on = TIMESTEP_END
  []
[]

[Postprocessors]
  [gradient_x]
    type = ElementAverageValue
    variable = "gradient_x"
  []
  [gradient_y]
    type = ElementAverageValue
    variable = "gradient_y"
  []
  [q_x]
    type = ElementAverageValue
    variable = "q_x"
  []
  [q_y]
    type = ElementAverageValue
    variable = "q_y"
  []
[]

[Executioner]
  type = Steady

  solve_type = 'newton'
  line_search = none

  # Device-resident PETSc: Kokkos vectors, aijkokkos matrix, BoomerAMG-preconditioned FGMRES.
  # The matrix type is aijkokkos rather than hypre because Kokkos assembly into a hypre matrix
  # faults on the GPU when periodic BCs add constrained DOFs; PCHYPRE converts the aijkokkos
  # matrix on the device. LU has no device implementation, so the linear tolerance is tight
  # instead (the CPU template solves with LU).
  petsc_options_iname = '-vec_type -nl0_mat_type -pc_type -pc_hypre_type -ksp_type -pc_hypre_boomeramg_tol -pc_hypre_boomeramg_max_iter -pc_hypre_boomeramg_interp_type -pc_hypre_boomeramg_agg_nl -pc_hypre_boomeramg_strong_threshold -ksp_gmres_modifiedgramschmidt -ksp_gmres_restart'
  petsc_options_value = 'kokkos aijkokkos hypre boomeramg fgmres 0 1 ext+i 1 0.7 1 100'

  l_max_its = 1000
  l_tol = 1e-12
  nl_max_its = 10
  nl_rel_tol = 1e-8
  nl_abs_tol = 1e-10

  residual_and_jacobian_together = true
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
