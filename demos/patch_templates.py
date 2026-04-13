t_path = "compgen/physics/2d/fracture/template.i"
f_path = "compgen/physics/2d/fracture/fracture.i"

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
text = text.replace("""  [fmg]\n    type = FileMeshGenerator\n    file = '/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/mesh.exo'\n  []\n  [bmb]\n    type = BreakMeshByBlockGenerator\n    input = 'fmg'""", replacement)
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
text = text.replace("""  [fmg]\n    type = FileMeshGenerator\n    file = '/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/mesh.exo'\n  []""", replacement_f)
with open(f_path, "w") as f:
    f.write(text)
