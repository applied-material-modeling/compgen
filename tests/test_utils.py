"""Tests for dictionary merge utilities and conflict/type handling."""

import pytest

from compgen.utils import dict_merge


def test_dict_merge_nested():
    a = {"one": {"two": 3}, "three": 4}
    b = {"one": {"four": 4}}

    merged = dict_merge([a, b])

    assert merged == {"one": {"two": 3, "four": 4}, "three": 4}


def test_dict_merge_conflict_non_dict_values():
    a = {"one": {"two": 3}, "three": 4}
    b = {"one": {"two": 4}}

    with pytest.raises(ValueError):
        dict_merge([a, b])


def test_dict_merge_conflict_dict_vs_value():
    a = {"one": {"two": 3}}
    b = {"one": 4}

    with pytest.raises(ValueError):
        dict_merge([a, b])


def test_dict_merge_type_checks():
    with pytest.raises(TypeError):
        dict_merge({"a": 1})

    with pytest.raises(TypeError):
        dict_merge([{"a": 1}, 2])
