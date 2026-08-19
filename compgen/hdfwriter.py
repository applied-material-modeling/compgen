import h5py
import numpy as np

# Below this many elements, a dataset is written uncompressed. Blosc2 errors on
# very small chunks, and the space savings there are negligible anyway.
SMALL_DATASET_ELEMENTS = 1024
# Target (uncompressed) chunk size; keeps chunks small enough for Blosc2's
# internal buffer while still amortizing per-chunk overhead.
COMPRESSION_CHUNK_BYTES = 16 * 1024 * 1024


def _pick_chunk_shape(shape, itemsize, chunk_bytes):
    """Chunk along the leading axis so each chunk is roughly ``chunk_bytes``."""
    if len(shape) == 0 or shape[0] == 0:
        return None
    per_step_bytes = itemsize
    for d in shape[1:]:
        per_step_bytes *= d
    per_step_bytes = max(per_step_bytes, 1)
    steps = max(1, min(shape[0], chunk_bytes // per_step_bytes))
    return (steps,) + tuple(shape[1:])


def _write_dataset(group, key, value, compress, small_dataset_elements, chunk_bytes):
    """Write ``value`` as a dataset, optionally downcast to float32 + compressed."""
    data = np.asarray(value)
    if compress:
        if data.dtype == np.float64:
            data = data.astype(np.float32)
        if data.size >= small_dataset_elements:
            # Imported lazily so the default (uncompressed) path never needs it.
            import hdf5plugin

            chunks = _pick_chunk_shape(data.shape, data.itemsize, chunk_bytes)
            if chunks is not None:
                compression = hdf5plugin.Blosc2(
                    cname="zstd", clevel=8, filters=hdf5plugin.Blosc2.SHUFFLE
                )
                group.create_dataset(key, data=data, chunks=chunks, **compression)
                return
    group.create_dataset(key, data=data)


def write_hdf5(
    filename,
    data_dict,
    *,
    compress=False,
    preserve_prefixes=("generalized",),
    small_dataset_elements=SMALL_DATASET_ELEMENTS,
    chunk_bytes=COMPRESSION_CHUNK_BYTES,
):
    """Write a dictionary of data to an HDF5 file.

    Args:
        filename (str): Path to the output HDF5 file.
        data_dict (dict): Dictionary containing data to write.

    Keyword Args:
        compress (bool): When True, float64 datasets are downcast to float32 and
            large datasets are Blosc2/zstd compressed. Defaults to False, which
            reproduces the original byte-for-byte writing behavior.
        preserve_prefixes (tuple): Group keys whose entire subtree is written at
            full precision without compression, even when ``compress`` is True.
            Defaults to ``("generalized",)`` so homogenized quantities keep their
            float64 precision.
        small_dataset_elements (int): Datasets with fewer elements than this are
            written uncompressed.
        chunk_bytes (int): Approximate uncompressed chunk size for compression.
    """
    with h5py.File(filename, "w") as hdf:

        def recursive_write(group, data, preserve):
            for key, value in data.items():
                if isinstance(value, dict):
                    subgroup = group.create_group(key)
                    recursive_write(
                        subgroup, value, preserve or key in preserve_prefixes
                    )
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
                        _write_dataset(
                            group,
                            key,
                            value,
                            compress and not preserve,
                            small_dataset_elements,
                            chunk_bytes,
                        )

        recursive_write(hdf, data_dict, False)
