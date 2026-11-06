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

# 2D heat transfer with pseudo-periodic boundary conditions 
# The model is a unit square with two materials

[GlobalParams]
  targets = 'value zero zero'
[]

[Mesh]
  [base]
    type = FileMeshGenerator
    file = 'mesh.exo'
  []
  [bm]
    type = BreakMeshByBlockGenerator
    input = base
    interface_name = 'ab'
  []
  [sidesets]
    type = SideSetsFromNormalsGenerator
    input = bm
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

[Variables]
  [./temp]
    initial_condition = 0.0
  [../]
[]

[Kernels]
  [./heat_conduction]
    type = ADHeatConductionHomogenized
    variable = temp
    thermal_conductivity = 'k'
  [../]
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

[InterfaceKernels]
  [./penalty]
    type = PenaltyInterfaceDiffusion
    variable = temp
    neighbor_var = temp
    boundary = 'ab'
    penalty = 50
  [../]
[]

[BCs]
  [Periodic]
    [T]
      variable = temp
      auto_direction = 'x y z'
    []
  []
  [fix_center]
    type = DirichletBC
    variable = temp
    boundary = 'center'
    value = 0
  []
[]


[Materials]
  [mat_k_1]
    type = ADGenericConstantMaterial
    prop_names = 'k'
    prop_values = '1'
    block = 1
  []
  [mat_k_2]
    type = ADGenericConstantMaterial
    prop_names = 'k'
    prop_values = '100'
    block = 2
  []
  [calculate_output]
    type = FluxOutputMaterial
    temp = temp
    thermal_conductivity = 'k'
  []
[]

[AuxVariables]
   [./gradient_x]
     order = CONSTANT
     family = MONOMIAL
   [../]
   [./gradient_y]
     order = CONSTANT
     family = MONOMIAL
   [../]
   [./gradient_z]
     order = CONSTANT
     family = MONOMIAL
   [../]
   [./q_x]
     order = CONSTANT
     family = MONOMIAL
   [../]
   [./q_y]
     order = CONSTANT
     family = MONOMIAL
   [../]
   [./q_z]
     order = CONSTANT
     family = MONOMIAL
   [../]
[]

[AuxKernels]
   [./gradient_x]
     type = ADMaterialRealVectorValueAux
     property = total_temperature_gradient
     variable = gradient_x
     component = 0
   [../]
   [./gradient_y]
     type = ADMaterialRealVectorValueAux
     property = total_temperature_gradient
     variable = gradient_y
     component = 1
   [../]
   [./gradient_z]
     type = ADMaterialRealVectorValueAux
     property = total_temperature_gradient
     variable = gradient_z
     component = 2
   [../]
   [./q_x]
     type = ADMaterialRealVectorValueAux
     property = flux
     variable = q_x
     component = 0
   [../]
   [./q_y]
     type = ADMaterialRealVectorValueAux
     property = flux
     variable = q_y
     component = 1
   [../]
   [./q_z]
     type = ADMaterialRealVectorValueAux
     property = flux
     variable = q_z
     component = 2
   [../]
[]

[Preconditioning]
  [smp]
    type = SMP
    full = true
  []
[]

[Executioner]
  type = Steady

  solve_type = 'newton'
  line_search = none

  petsc_options_iname = '-pc_type'
  petsc_options_value = 'lu'

  l_max_its = 2
  l_tol = 1e-10
  nl_max_its = 2
  nl_rel_tol = 1e-8
  nl_abs_tol = 1e-10

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
  [gradient_z]
    type = ElementAverageValue
    variable = "gradient_z"
  []
  [q_x]
    type = ElementAverageValue
    variable = "q_x"
  []
  [q_y]
    type = ElementAverageValue
    variable = "q_y"
  []
  [q_z]
    type = ElementAverageValue
    variable = "q_z"
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
