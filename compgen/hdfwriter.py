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
