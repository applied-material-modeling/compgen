import numpy as np
import pyvista as pv


def get_element_field(exo, field):
    """Retrieve an element field from an Exodus mesh.

    Args:
        exo (exodusii.File): Open Exodus file object.
        field (str): Name of the element field to retrieve.
    """
    var_names = list(exo.get_element_variable_names())
    if field not in var_names:
        raise ValueError(f"Field '{field}' not found in output Exodus file.")

    return np.concatenate(
        [exo.get_element_variable_values(blk, field) for blk in [1, 2]], axis=-1
    )


def get_node_field(exo, field):
    """Retrieve a node field from an Exodus mesh.

    Args:
        exo (exodusii.File): Open Exodus file object.
        field (str): Name of the node field to retrieve.
    """
    var_names = list(exo.get_node_variable_names())
    if field not in var_names:
        raise ValueError(f"Field '{field}' not found in output Exodus file.")

    return exo.get_node_variable_values(field)


def _collect_unstructured_grids(obj):
    if hasattr(obj, "n_blocks"):
        grids = []
        for i in range(obj.n_blocks):
            child = obj[i]
            if child is None:
                continue
            grids.extend(_collect_unstructured_grids(child))
        return grids

    if hasattr(obj, "n_cells") and obj.n_cells:
        return [obj]

    return []


def _coord_key(coord, dims, decimals):
    return tuple(round(float(x), decimals) for x in coord[:dims])


def get_node_field_aligned(output_exo, field, coords, decimals=8, conflict_resolution="max"):
    """Retrieve a node field from an Exodus file aligned to the reference coords order.

    Args:
        output_exo (str): Path to the Exodus output file.
        field (str): Name of the node field to retrieve.
        coords (np.ndarray): Reference coordinates ordering from the simplified mesh.
        decimals (int): Decimal places used when matching coordinates.
        conflict_resolution (str): Strategy to resolve multiple values at the same coordinate
                                    (e.g., from split interface nodes). Options: 'max', 'mean',
                                    'min', 'first'.
    """
    reader = pv.get_reader(output_exo)
    reader.enable_all_point_arrays()
    reader.disable_displacements()

    ref_keys = [_coord_key(coord, coords.shape[1], decimals) for coord in coords]
    data = np.zeros((reader.number_time_points, len(ref_keys)))

    for time_index in range(reader.number_time_points):
        reader.set_active_time_point(time_index)
        root = reader.read()
        main_blocks = _collect_unstructured_grids(root[0] if root.n_blocks else root)

        values_by_coord = {}
        for block in main_blocks:
            if field not in block.point_data:
                continue

            points = np.asarray(block.points[:, : coords.shape[1]])
            values = np.asarray(block.point_data[field])
            for point, value in zip(points, values):
                key = _coord_key(point, coords.shape[1], decimals)
                if key not in values_by_coord:
                    values_by_coord[key] = []
                values_by_coord[key].append(value)

        # Resolve multiple values per coordinate (e.g. at split interfaces)
        resolved_values = {}
        for key, val_list in values_by_coord.items():
            if len(val_list) == 1:
                resolved_values[key] = val_list[0]
            else:
                if conflict_resolution == "max":
                    resolved_values[key] = np.max(val_list)
                elif conflict_resolution == "mean":
                    resolved_values[key] = np.mean(val_list)
                elif conflict_resolution == "min":
                    resolved_values[key] = np.min(val_list)
                elif conflict_resolution == "first":
                    resolved_values[key] = val_list[0]
                else:
                    raise ValueError(f"Unknown conflict_resolution strategy: {conflict_resolution}")

        missing = [key for key in ref_keys if key not in resolved_values]
        if missing:
            raise ValueError(
                f"Could not align all coordinates for node field '{field}'. Missing {len(missing)} values."
            )

        data[time_index] = [resolved_values[key] for key in ref_keys]

    return data
