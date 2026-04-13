t_path = "/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/compgen/physics/2d/fracture/template.i"
f_path = "/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/compgen/physics/2d/fracture/fracture.i"

with open(t_path, "r") as f:
    text = f.read()

replacement = """  [fmg]
    type = FileMeshGenerator
    file = '/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/mesh.exo'
  []
  [rename]
    type = RenameBoundaryGenerator
    input = fmg
    old_boundary = '1 2 3 4'
    new_boundary = 'left right bottom top'
  []
  [bmb]
    type = BreakMeshByBlockGenerator
    input = 'rename'"""

original_bmb = """  [fmg]
    type = FileMeshGenerator
    file = '/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/mesh.exo'
  []
  [bmb]
    type = BreakMeshByBlockGenerator
    input = 'fmg'"""

if original_bmb in text:
    text = text.replace(original_bmb, replacement)
    with open(t_path, "w") as f:
        f.write(text)

with open(f_path, "r") as f:
    text = f.read()
replacement_f = """  [fmg]
    type = FileMeshGenerator
    file = '/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/mesh.exo'
  []
  [rename]
    type = RenameBoundaryGenerator
    input = fmg
    old_boundary = '1 2 3 4'
    new_boundary = 'left right bottom top'
  []"""

original_f = """  [fmg]
    type = FileMeshGenerator
    file = '/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/mesh.exo'
  []"""

# Only replace if the rename block isn't already there
if original_f in text and "[rename]" not in text:
    text = text.replace(original_f, replacement_f, 1) # replace only the first occurrence to avoid nested issues
    with open(f_path, "w") as f:
        f.write(text)
