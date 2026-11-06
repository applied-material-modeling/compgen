# Copyright 2026, UChicago Argonne, LLC
# All Rights Reserved
# Software Name: compgen
# By: Argonne National Laboratory
# OPEN SOURCE LICENSE (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""Tensor metadata and routines for assembling structured tensor outputs."""

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
        tensor_type (str): Type of the tensor. One of "scalar", "vector",
            "rank_two_tensor", or "symmetric_rank_two_tensor".
        dim (int): Dimension of the tensor.  One of 2, 3.
        components (list of np.ndarray): List of components of the tensor.
    """
    shape = tensor_info[tensor_type][dim]

    if len(components) != np.prod(shape):
        raise ValueError(
            f"Number of components {len(components)} does not match expected "
            f"number {np.prod(shape)} for tensor type {tensor_type} and "
            f"dimension {dim}."
        )

    if tensor_type == "scalar":
        return {"type": "scalar", "shape": tuple(), "data": components[0]}

    orig_shape = components[0].shape

    return {
        "type": tensor_type,
        "shape": shape,
        "data": np.stack(components, axis=-1).reshape(orig_shape + shape),
    }
