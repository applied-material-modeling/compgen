import json
import os
from compgen import moose

with open("compgen/physics/2d/fracture/settings.json", "r") as f:
    physics_settings = json.load(f)

print("Attempting to process output...")
# mesh is mesh.exo, output_exo is results/tmpevw001gw/output_0.e, output_csv is results/tmpevw001gw/output_0.csv
try:
    res = moose.process_output(
        "2d/fracture",
        "compgen/demos/mesh.exo",
        {"A": {}, "B": {}, "AB": {}},
        "compgen/demos/results/tmpevw001gw/output_0.e",
        "compgen/demos/results/tmpevw001gw/output_0.csv"
    )
    print("Success!")
except Exception as e:
    print(f"Failed with error: {e}")
    import traceback
    traceback.print_exc()
