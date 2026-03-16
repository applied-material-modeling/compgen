import re

template_path = "/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/compgen/physics/2d/fracture/template.i"
with open(template_path, "r") as f:
    content = f.read()

# We need to add AuxVariables for strain and stress
aux_vars = """
  [mechanical_strain_xx]
    order = CONSTANT
    family = MONOMIAL
  []
  [mechanical_strain_yy]
    order = CONSTANT
    family = MONOMIAL
  []
  [mechanical_strain_xy]
    order = CONSTANT
    family = MONOMIAL
  []
  [cauchy_stress_xx]
    order = CONSTANT
    family = MONOMIAL
  []
  [cauchy_stress_yy]
    order = CONSTANT
    family = MONOMIAL
  []
  [cauchy_stress_xy]
    order = CONSTANT
    family = MONOMIAL
  []
"""

# And AuxKernels for them
aux_kernels = """
[AuxKernels]
  [mechanical_strain_xx_kernel]
    type = ADMaterialRealTensorValueAux
    property = mechanical_strain
    column = 0
    row = 0
    variable = mechanical_strain_xx
  []
  [mechanical_strain_yy_kernel]
    type = ADMaterialRealTensorValueAux
    property = mechanical_strain
    column = 1
    row = 1
    variable = mechanical_strain_yy
  []
  [mechanical_strain_xy_kernel]
    type = ADMaterialRealTensorValueAux
    property = mechanical_strain
    column = 0
    row = 1
    variable = mechanical_strain_xy
  []
  [cauchy_stress_xx_kernel]
    type = MaterialRealTensorValueAux
    property = cauchy_stress
    column = 0
    row = 0
    variable = cauchy_stress_xx
  []
  [cauchy_stress_yy_kernel]
    type = MaterialRealTensorValueAux
    property = cauchy_stress
    column = 1
    row = 1
    variable = cauchy_stress_yy
  []
  [cauchy_stress_xy_kernel]
    type = MaterialRealTensorValueAux
    property = cauchy_stress
    column = 0
    row = 1
    variable = cauchy_stress_xy
  []
[]
"""

postprocessors = """
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
"""

# Insert aux_vars into [AuxVariables]
content = re.sub(r'(\[AuxVariables\].*?)(^\[)', r'\1' + aux_vars + r'\2', content, flags=re.MULTILINE|re.DOTALL)

# Insert aux_kernels after [AuxVariables]
content = re.sub(r'(\[AuxVariables\].*?^\[\]\n)', r'\1\n' + aux_kernels + '\n', content, flags=re.MULTILINE|re.DOTALL)

# Insert postprocessors into [Postprocessors]
content = re.sub(r'(\[Postprocessors\].*?)(^\[)', r'\1' + postprocessors + r'\2', content, flags=re.MULTILINE|re.DOTALL)

with open(template_path, "w") as f:
    f.write(content)

print("Updated template.i")
