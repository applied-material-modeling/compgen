"""Various helpers for reading Exodus II files."""

import numpy as np


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
