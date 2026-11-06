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

"""Utilities for helping read/write HDF5 files."""

import h5py
import numpy as np


def write_hdf5(filename, data_dict):
    """Write a dictionary of data to an HDF5 file.

    Args:
        filename (str): Path to the output HDF5 file.
        data_dict (dict): Dictionary containing data to write.
    """
    with h5py.File(filename, "w") as hdf:

        def recursive_write(group, data):
            for key, value in data.items():
                if isinstance(value, dict):
                    subgroup = group.create_group(key)
                    recursive_write(subgroup, value)
                elif isinstance(value, list):
                    subgroup = group.create_group(key)
                    for i, item in enumerate(value):
                        subgroup.attrs[str(i)] = item
                elif isinstance(value, (int, float, str)):
                    group.attrs[key] = value
                else:
                    if isinstance(value, tuple):
                        group.create_dataset(key, data=np.array(value, dtype=int))
                    else:
                        group.create_dataset(key, data=value)

        recursive_write(hdf, data_dict)
