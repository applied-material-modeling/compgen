import exodusii
import os

exo_file = "compgen/demos/results/tmpevw001gw/output_0.e"
if not os.path.exists(exo_file):
    print(f"File {exo_file} not found")
else:
    with exodusii.File(exo_file, mode="r") as exo:
        print("Element variables:", list(exo.get_element_variable_names()))
        print("Global variables:", list(exo.get_global_variable_names()))
        print("Node variables:", list(exo.get_node_variable_names()))
