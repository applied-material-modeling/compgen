import re

def fix_file(filepath, replacements):
    with open(filepath, 'r') as f:
        content = f.read()
    
    for target, replacement in replacements:
        content = content.replace(target, replacement)
        
    with open(filepath, 'w') as f:
        f.write(content)

# Fix template.i
template_replacements = [
    (
"""[Mesh]
  [fmg]
    type = FileMeshGenerator
    file = 'gold/composite.msh'
  []
[]""",
"""[Mesh]
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
[]"""
    ),
    (
"""  [bulk_properties_A]
    type = ADGenericConstantMaterial
    prop_names = 'K G l Gc psic'
    prop_values = '${K_A} ${G_A} ${l} ${Gc_A} ${psic_A}'
    block = 'A'
  []
  [bulk_properties_B]
    type = ADGenericConstantMaterial
    prop_names = 'K G l Gc psic'
    prop_values = '${K_B} ${G_B} ${l} ${Gc_B} ${psic_B}'
    block = 'B'
  []""",
"""  [bulk_properties_A]
    type = ADGenericConstantMaterial
    prop_names = 'K G l Gc psic'
    prop_values = '${K_A} ${G_A} ${l} ${Gc_A} ${psic_A}'
    block = '1'
  []
  [bulk_properties_B]
    type = ADGenericConstantMaterial
    prop_names = 'K G l Gc psic'
    prop_values = '${K_B} ${G_B} ${l} ${Gc_B} ${psic_B}'
    block = '2'
  []"""
    )
]

# Fix fracture.i
fracture_replacements = [
    (
"""[Mesh]
  [fmg]
    type = FileMeshGenerator
    file = 'gold/composite.msh'
  []
[]""",
"""[Mesh]
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
[]"""
    ),
    (
"""  [bulk_properties_A]
    type = ADGenericConstantMaterial
    prop_names = 'l Gc psic'
    prop_values = '${l} ${Gc_A} ${psic_A}'
    block = 'A'
  []
  [bulk_properties_B]
    type = ADGenericConstantMaterial
    prop_names = 'l Gc psic'
    prop_values = '${l} ${Gc_B} ${psic_B}'
    block = 'B'
  []""",
"""  [bulk_properties_A]
    type = ADGenericConstantMaterial
    prop_names = 'l Gc psic'
    prop_values = '${l} ${Gc_A} ${psic_A}'
    block = '1'
  []
  [bulk_properties_B]
    type = ADGenericConstantMaterial
    prop_names = 'l Gc psic'
    prop_values = '${l} ${Gc_B} ${psic_B}'
    block = '2'
  []"""
    )
]

# Reset files from original
import shutil
shutil.copy('/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/pff/mechanics.i', '/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/compgen/physics/2d/fracture/template.i')
shutil.copy('/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/pff/fracture.i', '/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/compgen/physics/2d/fracture/fracture.i')

# Apply replacements
fix_file('/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/compgen/physics/2d/fracture/template.i', template_replacements)
fix_file('/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/compgen/physics/2d/fracture/fracture.i', fracture_replacements)

print("Files fixed successfully.")
