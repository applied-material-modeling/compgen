import exodusii
import numpy as np
points = np.array([[0,0], [1,0], [1,1], [0,1]])
mat_a = [[1,2,3,4]]
try:
    with exodusii.File("test.exo", mode="w") as exo:
        exo.put_init("2D Mesh", 2, len(points), 1, 1, 1, 0)
        exo.put_coord(points[:, 0], points[:, 1])
        exo.put_element_block(1, "QUAD", 1, 4)
        exo.put_element_block_name(1, "mat_a")
        exo.put_element_conn(1, np.array(mat_a))
        exo.put_node_set_param(1, 2)
        exo.put_node_set(1, [1, 4])
        try:
            exo.put_node_set_name(1, "left")
            print("put_node_set_name SUCCESS")
        except Exception as e:
            print("put_node_set_name FAILED", e)
except Exception as e:
    print("Failed creating!", e)
