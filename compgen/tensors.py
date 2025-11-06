import numpy as np

tensor_info = {
    "scalar": {2: (1,), 3: (1,)},
    "vector": {2: (2,), 3: (3,)},
    "rank_two_tensor": {2: (2, 2), 3: (3, 3)},
    "symmetric_rank_two_tensor": {2: (3,), 3: (6,)},
}


def assemble_tensor(tensor_type, dim, components):
    """
    Assemble a tensor from its components.

    Args:
        tensor_type (str): Type of the tensor.  One of "scalar", "vector", "rank_two_tensor", "symmetric_rank_two_tensor".
        dim (int): Dimension of the tensor.  One of 2, 3.
        components (list of np.ndarray): List of components of the tensor.
    """
    shape = tensor_info[tensor_type][dim]

    if len(components) != np.prod(shape):
        raise ValueError(
            f"Number of components {len(components)} does not match expected number {np.prod(shape)} for tensor type {tensor_type} and dimension {dim}."
        )

    if tensor_type == "scalar":
        return ("scalar", tuple(), components[0])

    orig_shape = components[0].shape

    return {
        "type": tensor_type,
        "shape": shape,
        "data": np.stack(components, axis=-1).reshape(orig_shape + shape),
    }
