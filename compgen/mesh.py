from compgen import temp

import numpy as np
import exodusii
import scipy.spatial as sp
import os
import os.path
import subprocess


def generate_mesh_2d(img, fname, L=(1.0, 1.0), settings={}, run_sculpt=True):
    """Run the entire process of generating a 2D mesh for an image and write it to an exodus file.

    This function will access a temp directory to store intermediate files, but copy the final
    mesh to the cwd.

    Args:
        img (2D array): Binary image where 1 indicates material A
        fname (str): Output filename for the mesh.

    Keyword Args:
        L (tuple): Lengths of the domain in each direction.
        settings (dict): Global settings dict
        run_sculpt (bool): Whether to sculpt the mesh
    """
    assert len(img.shape) == 2, "Input image must be 2D."

    lx, ly = L

    with temp.TempDirectory(settings) as (cwd, _):
        write_mesh_2d(img, "temp_mesh.e", lx=lx, ly=ly)
        if run_sculpt:
            extrude("temp_mesh.e", prefix="extruded_", lx=lx, ly=ly)
            sculpt("extruded_temp_mesh.e", prefix="sculpted_", settings=settings)
            slice("sculpted_extruded_temp_mesh.e", prefix="sliced_")
            os.rename("sliced_sculpted_extruded_temp_mesh.e", os.path.join(cwd, fname))
        else:
            os.rename("temp_mesh.e", os.path.join(cwd, fname))


def generate_mesh_3d(img, fname, L=(1.0, 1.0, 1.0), settings={}, run_sculpt=True):
    """Run the entire process of generating a 3D mesh for an image and write it to an exodus file.

    This function will access a temp directory to store intermediate files, but copy the final
    mesh to the cwd.

    Args:
        img (3D array): Binary image where 1 indicates material A
        fname (str): Output filename for the mesh.

    Keyword Args:
        L (tuple): Lengths of the domain in each direction.
        settings (dict): Global settings dict
        run_sculpt (bool): Whether to sculpt the mesh
    """
    assert len(img.shape) == 3, "Input image must be 3D."

    lx, ly, lz = L

    with temp.TempDirectory(settings) as (cwd, _):
        write_mesh_3d(img, "temp_mesh.e", lx=lx, ly=ly, lz=lz)
        if run_sculpt:
            sculpt("temp_mesh.e", prefix="sculpted_", settings=settings)
            os.rename("sculpted_temp_mesh.e", os.path.join(cwd, fname))
        else:
            os.rename("temp_mesh.e", os.path.join(cwd, fname))


def sculpt(mesh, prefix="sculpted_", settings={}):
    """Call sculpt on an extruded mesh.

    Args:
        mesh (str): Input 3D mesh filename.

    Keyword Args:
        prefix (str): Prefix for the output sculpted mesh filename.
        settings (dict): Global settings dict
    """
    outfile = os.path.splitext(f"{prefix}{mesh}")[0]
    cmd = (
        [
            settings["sculpt"]["mpi"],
            settings["sculpt"]["rank_command"],
            settings["mpi"]["ranks"],
        ]
        + [settings["sculpt"]["executable"]]
        + settings["sculpt"]["options"]
        + ["-ice", mesh, "--exodus_file", outfile]
    )
    subprocess.run(
        cmd,
        check=True,
        env=settings["sculpt"].get("environment", {}) | os.environ,
        capture_output=(not settings.get("verbose", False)),
    )

    epu_cmd = [settings["sculpt"]["epu"], "-auto", outfile + ".e" + f".{settings["mpi"]["ranks"]}.0"]
    subprocess.run(
        epu_cmd,
        check=True,
        env=settings["sculpt"].get("environment", {}) | os.environ,
        capture_output=(not settings.get("verbose", False)),
    )


def extrude(mesh, lx=1.0, ly=1.0, prefix="extruded_", lz=0.01, tol=1e-6):
    """Read a 2D mesh and extrude it into 3D.

    Args:
        mesh (str): Input 2D mesh filename.

    Keyword Args:
        prefix (str): Prefix for the output 3D mesh filename.
        lz (float): Length of the extrusion in the z-direction.

    """
    with exodusii.File(mesh, mode="r") as exo:
        coords = exo.get_coords()
        conn_a = exo.get_element_conn(1)
        conn_b = exo.get_element_conn(2)

    nnodes_orig = coords.shape[0]

    coords = np.hstack([coords, np.zeros((nnodes_orig, 1))])
    coords = np.vstack([coords, coords + np.array([0.0, 0.0, lz])])

    def update_conn(conn):
        return list(conn) + [i + nnodes_orig for i in conn]

    conn_a = np.array([update_conn(e) for e in conn_a])
    conn_b = np.array([update_conn(e) for e in conn_b])

    # Identify periodic node_sets
    node_nums = np.arange(1, coords.shape[0] + 1)
    left = coords[:, 0] < tol
    right = coords[:, 0] > lx - tol
    bottom = coords[:, 1] < tol
    top = coords[:, 1] > ly - tol

    with exodusii.File(f"{prefix}{mesh}", mode="w") as exo:
        exo.put_init(
            "3D Extruded Mesh", 3, coords.shape[0], len(conn_a) + len(conn_b), 2, 4, 0
        )
        exo.put_coord(coords[:, 0], coords[:, 1], coords[:, 2])
        exo.put_element_block(1, "HEX", len(conn_a), 8)
        exo.put_element_block_name(1, "mat_a")
        exo.put_element_conn(1, conn_a)
        exo.put_element_block(2, "HEX", len(conn_b), 8)
        exo.put_element_block_name(2, "mat_b")
        exo.put_element_conn(2, conn_b)

        exo.put_node_set_param(1, len(node_nums[left]))
        exo.put_node_set(1, node_nums[left])
        exo.put_node_set_param(2, len(node_nums[right]))
        exo.put_node_set(2, node_nums[right])
        exo.put_node_set_param(3, len(node_nums[bottom]))
        exo.put_node_set(3, node_nums[bottom])
        exo.put_node_set_param(4, len(node_nums[top]))
        exo.put_node_set(4, node_nums[top])


def slice(mesh, prefix="sliced_", eps=1e-4):
    """Take a 2D slice of a 3D hex mesh.

    This function assumes that the input mesh is a single element thick in the z-direction.

    Args:
        mesh (str): Input 3D mesh filename.

    Keyword Args:
        prefix (str): Prefix for the output 2D mesh filename.
    """
    with exodusii.File(mesh, mode="r") as exo:
        coords = exo.get_coords()
        conn_a = exo.get_element_conn(1)
        conn_b = exo.get_element_conn(2)

    node_nums = range(1, coords.shape[0] + 1)
    keep_nodes = np.abs(coords[:, 2]) < eps

    node_map = {}
    kk = 1
    for ii, keep in zip(node_nums, keep_nodes):
        if keep:
            node_map[ii] = kk
            kk += 1

    coords = coords[keep_nodes, :2]

    def update_conn(conn):
        new_conn = [node_map[c] for c in conn if c in node_map]
        points = coords[np.array(new_conn, dtype=int) - 1]
        # Really, I have to orient the points correctly to make a quad?
        center = np.mean(points, axis=0)
        angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
        sorted_indices = np.argsort(angles)
        new_conn = [new_conn[i] for i in sorted_indices]

        if len(new_conn) != 4:
            raise ValueError("Element does not have 4 nodes after slicing.")

        return new_conn

    new_conn_a = np.array([update_conn(e) for e in conn_a])
    new_conn_b = np.array([update_conn(e) for e in conn_b])

    with exodusii.File(f"{prefix}{mesh}", mode="w") as exo:
        exo.put_init(
            "2D Sliced Mesh",
            2,
            coords.shape[0],
            len(new_conn_a) + len(new_conn_b),
            2,
            0,
            0,
        )
        exo.put_coord(coords[:, 0], coords[:, 1])
        exo.put_element_block(1, "QUAD", len(new_conn_a), 4)
        exo.put_element_block_name(1, "mat_a")
        exo.put_element_conn(1, new_conn_a)
        exo.put_element_block(2, "QUAD", len(new_conn_b), 4)
        exo.put_element_block_name(2, "mat_b")
        exo.put_element_conn(2, new_conn_b)


def write_mesh_2d(img, fname, lx=1.0, ly=1.0):
    """Write a 2D mesh file from a binary image.

    Args:
        img (2D array): Binary image where 1 indicates material A
        fname (str): Output filename for the mesh.

    Keyword Args:
        lx (float): Length of the domain in x-direction.
        ly (float): Length of the domain in y-direction.
    """
    nx, ny = img.shape

    x_vals = np.linspace(0, lx, nx + 1)
    y_vals = np.linspace(0, ly, ny + 1)

    X, Y = np.meshgrid(x_vals, y_vals, indexing="ij")
    points = np.vstack([X.flatten(), Y.flatten()]).T

    mat_a = []
    mat_b = []
    for je in range(ny):
        for ie in range(nx):
            cell = [
                ie * (nx + 1) + je + 1,
                ie * (nx + 1) + je + 1 + 1,
                (ie + 1) * (nx + 1) + je + 1 + 1,
                (ie + 1) * (nx + 1) + je + 1,
            ]
            if img[ie, je]:
                mat_a.append(cell)
            else:
                mat_b.append(cell)

    with exodusii.File(fname, mode="w") as exo:
        exo.put_init("2D Mesh", 2, len(points), len(mat_a) + len(mat_b), 2, 0, 0)
        exo.put_coord(points[:, 0], points[:, 1])
        exo.put_element_block(1, "QUAD", len(mat_a), 4)
        exo.put_element_block_name(1, "mat_a")
        exo.put_element_conn(1, np.array(mat_a))
        exo.put_element_block(2, "QUAD", len(mat_b), 4)
        exo.put_element_block_name(2, "mat_b")
        exo.put_element_conn(2, np.array(mat_b))


def write_mesh_3d(img, fname, lx=1.0, ly=1.0, lz=1.0):
    """Write a 3D mesh file from a binary image.

    Args:
        img (3D array): Binary image where 1 indicates material A
        fname (str): Output filename for the mesh.

    Keyword Args:
        lx (float): Length of the domain in x-direction.
        ly (float): Length of the domain in y-direction.
        lz (float): Length of the domain in z-direction.
    """
    nx, ny, nz = img.shape

    x_vals = np.linspace(0, lx, nx + 1)
    y_vals = np.linspace(0, ly, ny + 1)
    z_vals = np.linspace(0, lz, nz + 1)

    X, Y, Z = np.meshgrid(x_vals, y_vals, z_vals, indexing="ij")
    points = np.vstack([X.flatten(), Y.flatten(), Z.flatten()]).T

    mat_a = []
    mat_b = []
    for ke in range(nz):
        for je in range(ny):
            for ie in range(nx):
                cell = [
                    ie * (nx + 1) * (ny + 1) + je * (nx + 1) + ke + 1,
                    ie * (nx + 1) * (ny + 1) + je * (nx + 1) + (ke + 1) + 1,
                    ie * (nx + 1) * (ny + 1) + (je + 1) * (nx + 1) + (ke + 1) + 1,
                    ie * (nx + 1) * (ny + 1) + (je + 1) * (nx + 1) + ke + 1,
                    (ie + 1) * (nx + 1) * (ny + 1) + je * (nx + 1) + ke + 1,
                    (ie + 1) * (nx + 1) * (ny + 1) + je * (nx + 1) + (ke + 1) + 1,
                    (ie + 1) * (nx + 1) * (ny + 1) + (je + 1) * (nx + 1) + (ke + 1) + 1,
                    (ie + 1) * (nx + 1) * (ny + 1) + (je + 1) * (nx + 1) + ke + 1,
                ]
                if img[ie, je, ke]:
                    mat_a.append(cell)
                else:
                    mat_b.append(cell)

    with exodusii.File(fname, mode="w") as exo:
        exo.put_init("3D Mesh", 3, len(points), len(mat_a) + len(mat_b), 2, 0, 0)
        exo.put_coord(points[:, 0], points[:, 1], points[:, 2])
        exo.put_element_block(1, "HEX", len(mat_a), 8)
        exo.put_element_block_name(1, "mat_a")
        exo.put_element_conn(1, np.array(mat_a))
        exo.put_element_block(2, "HEX", len(mat_b), 8)
        exo.put_element_block_name(2, "mat_b")
        exo.put_element_conn(2, np.array(mat_b))


def project_element_field_to_grid(mesh_coords, mesh_conn, element_field, L, N):
    """Project an element field from an unstructured mesh onto a structured grid.

    This uses closest element centroid projection.

    Args:
        mesh_coords (array): Coordinates of the mesh nodes.
        mesh_conn (array): Connectivity of the mesh elements, assumed to be quads.
        element_field (type, shape, data): Element field values to project.
        L (tuple): Lengths of the domain in each direction.
        N (tuple): Number of elements in each direction.
    """
    assert len(L) == len(N)

    tensor_type = element_field["type"]
    shape = element_field["shape"]
    data = element_field["data"]

    # Grid centroids
    G = np.meshgrid(
        *[np.linspace(l / n / 2, l - l / n / 2, n) for l, n in zip(L, N)], indexing="ij"
    )

    # Cell centroids
    elem_centroids = np.zeros((mesh_conn.shape[0], len(L)))
    for iel, conn in enumerate(mesh_conn):
        points = mesh_coords[conn]
        elem_centroids[iel, :] = np.mean(points, axis=0)

    tree = sp.cKDTree(elem_centroids)
    # Find the closest element for each grid point
    _, closest_elems = tree.query(np.column_stack([g.ravel() for g in G]), k=1)

    return {
        "type": tensor_type,
        "shape": shape,
        "data": data[:, closest_elems].reshape((-1,) + tuple(N) + shape),
    }


def extract_grid_from_mesh(mesh_data, img, L, length_names=["lx", "ly", "lz"]):
    """Extract grid information from mesh data.

    Args:
        mesh_data (dict): Mesh data containing unstructured grid output
        img (2D array): Binary image where 1 indicates material A
        L (tuple): Lengths of the domain in each direction.

    Keyword Args:
        length_names (list): Names for the length entries in the output grid.

    Returns:
        dict: Extracted grid information.
    """
    grid = {
        "cell_fields": {
            "material": {"type": "scalar", "shape": tuple(), "data": img},
            "stimuli": {},
            "responses": {},
        }
        | {length_names[i]: L[i] for i in range(len(L))},
    }

    for name, val in mesh_data["element_fields"]["stimuli"].items():
        grid["cell_fields"]["stimuli"][name] = project_element_field_to_grid(
            mesh_data["coords"],
            mesh_data["connectivity"],
            val,
            L,
            img.shape,
        )

    for name, val in mesh_data["element_fields"]["responses"].items():
        grid["cell_fields"]["responses"][name] = project_element_field_to_grid(
            mesh_data["coords"],
            mesh_data["connectivity"],
            val,
            L,
            img.shape,
        )

    # This is entirely to double check the material field projection
    grid["cell_fields"]["material_reprojected"] = project_element_field_to_grid(
        mesh_data["coords"],
        mesh_data["connectivity"],
        mesh_data["element_fields"]["material"],
        L,
        img.shape,
    )

    return grid
