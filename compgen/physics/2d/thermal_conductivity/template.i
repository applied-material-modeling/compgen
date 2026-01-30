# 2D heat transfer with pseudo-periodic boundary conditions 
# The model is a unit square with two materials

[GlobalParams]
  targets = 'value zero'
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

[BCs]
  [Periodic]
    [T]
      variable = temp
      auto_direction = 'x y'
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
   [./q_x]
     order = CONSTANT
     family = MONOMIAL
   [../]
   [./q_y]
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
  [q_x]
    type = ElementAverageValue
    variable = "q_x"
  []
  [q_y]
    type = ElementAverageValue
    variable = "q_y"
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
