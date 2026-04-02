"""Tests for dictionary merge utilities and conflict/type handling."""

import pytest
import numpy as np
from compgen.utils import dict_merge, standardize_image


def test_dict_merge_nested():
    """Test that dict_merge correctly merges nested dictionaries without conflicts."""
    a = {"one": {"two": 3}, "three": 4}
    b = {"one": {"four": 4}}

    merged = dict_merge([a, b])

    assert merged == {"one": {"two": 3, "four": 4}, "three": 4}


def test_dict_merge_conflict_non_dict_values():
    """Test that dict_merge raises a ValueError when there is a conflict between non-dict values."""
    a = {"one": {"two": 3}, "three": 4}
    b = {"one": {"two": 4}}

    with pytest.raises(ValueError):
        dict_merge([a, b])


def test_dict_merge_conflict_dict_vs_value():
    """Test that dict_merge raises a ValueError when there is a conflict between a
    dict and a non-dict value."""
    a = {"one": {"two": 3}}
    b = {"one": 4}

    with pytest.raises(ValueError):
        dict_merge([a, b])


def test_dict_merge_type_checks():
    """Test that dict_merge raises TypeError when inputs are not lists of dicts."""
    with pytest.raises(TypeError):
        dict_merge({"a": 1})

    with pytest.raises(TypeError):
        dict_merge([{"a": 1}, 2])


@pytest.mark.parametrize(
    ("shape",),
    [
        ((10, 12),),
        ((8, 9, 10),),
    ],
)
def test_no_shape_no_dtype(shape):
    """Check image passes through unchanged when no options are given."""
    img = np.random.rand(*shape)
    out = standardize_image(img)

    assert out.shape == img.shape
    assert out.dtype == float


@pytest.mark.parametrize(
    ("input_shape", "target_shape"),
    [
        ((10, 10), (20, 15)),
        ((6, 7, 8), (12, 14, 16)),
    ],
)
def test_resize(input_shape, target_shape):
    """Check resizing produces the requested shape."""
    img = np.random.rand(*input_shape)
    out = standardize_image(img, shape=target_shape)

    assert out.shape == target_shape


@pytest.mark.parametrize(
    ("img", "dtype", "expected"),
    [
        (
            np.array([[0.2, 0.6], [0.7, 0.1]]),
            bool,
            np.array([[False, True], [True, False]]),
        ),
        (
            np.array([[0.2, 0.6]]),
            int,
            np.array([[0, 1]]),
        ),
    ],
)
def test_dtype_binarization(img, dtype, expected):
    """Check binarization for different output dtypes."""
    out = standardize_image(img, dtype=dtype)

    assert out.dtype == dtype
    assert np.array_equal(out, expected)


def test_resize_and_binarize():
    """Check combined resizing and binarization."""
    img = np.random.rand(10, 10)
    out = standardize_image(img, shape=(5, 5), dtype=np.uint8)

    assert out.shape == (5, 5)
    assert out.dtype == np.uint8
    assert set(np.unique(out)).issubset({0, 1})


@pytest.mark.parametrize(
    ("img", "target_shape"),
    [
        (np.random.rand(10, 10), (10, 10, 10)),
        (np.random.rand(5, 5, 5), (10, 10)),
    ],
)
def test_shape_dim_mismatch(img, target_shape):
    """Ensure error is raised when shape dimensionality does not match."""
    with pytest.raises(ValueError, match="shape dimensionality must match"):
        standardize_image(img, shape=target_shape)


def test_invalid_dimension():
    """Ensure error is raised for non-2D/3D input."""
    img = np.random.rand(5)

    with pytest.raises(ValueError, match="image must be 2D or 3D"):
        standardize_image(img)
