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

"""Tests for structure generation utilities and stochastic generator outputs."""

import numpy as np
import pytest

from compgen.gen import (
    RandomGenerator,
    SpinodalGenerator,
    TwoPointGenerator,
    Reconstruction2D,
    ParticleGenerator,
    VoronoiGenerator,
    FromNumpyGenerator,
)


@pytest.mark.parametrize(
    "shape,vf",
    [
        ([128], 0.25),
        ([64, 64], 0.3),
        ([32, 32, 32], 0.1),
    ],
)
def test_random_generator_shape_and_vf(shape, vf):
    """Test that the RandomGenerator produces images of the correct shape and
    approximate volume fraction."""
    gen = RandomGenerator(shape, vf, random_seed=123)
    img = gen.sample()

    assert img.shape == tuple(shape)

    total = int(np.prod(shape))
    expected = int(total * vf)
    assert int(img.sum()) == expected


@pytest.mark.parametrize(
    "shape,vf,l,bandwidth",
    [
        ([128], 0.35, 16.0, 0.4),
        ([64, 64], 0.4, 12.0, 0.35),
        ([32, 32, 32], 0.3, 10.0, 0.3),
    ],
)
def test_spinodal_generator_shape_and_vf(shape, vf, l, bandwidth):
    """Test that the SpinodalGenerator produces images of the correct shape and
    approximate volume fraction."""
    gen = SpinodalGenerator(shape, vf, l, bandwidth, random_seed=321)
    img = gen.sample()

    assert img.shape == tuple(shape)

    frac = img.mean()
    assert np.isclose(frac, vf, atol=0.05)


def test_two_point_generator_shape_and_vf():
    """Test that the TwoPointGenerator produces images of the correct shape and
    approximate volume fraction."""
    rng = np.random.default_rng(7)
    reference_image = rng.random((48, 48)) > 0.65
    gen = TwoPointGenerator([48, 48], reference_image, random_seed=11)

    img = gen.sample()
    assert img.shape == reference_image.shape

    ref_vf = reference_image.mean()
    assert np.isclose(img.mean(), ref_vf, atol=0.1)


@pytest.mark.parametrize(
    "path,descriptors",
    [
        (
            "demos/complete/reconstruction/demo_microstructures/ms_0.npy",
            {"Variation": 10.0, "Correlations": 1.0},
        ),
        (
            "demos/complete/reconstruction/demo_microstructures",
            {"VolumeFractions": 1.0, "TwoPointCorrelations": 1.0},
        ),
    ],
)
def test_reconstruction_generator_shape_and_vf(path, descriptors):
    """Test that the Reconstruction2D generator produces images of the
    correct shape and approximate volume fraction."""
    final_shape = (48, 48)
    limit_to = 4
    gen = Reconstruction2D(
        N=final_shape,
        target_path=path,
        descriptors=descriptors,
        limit_to=limit_to,
        random_seed=42,
    )
    img = gen.sample()

    assert img.shape == final_shape
    assert np.isclose(img.mean(), gen.target_vf, atol=0.25)


@pytest.mark.parametrize(
    "N,vf,kind,shape_params,buffer",
    [
        ([64, 64], 0.3, "disks", {"size_m": 0.1}, 1.0),
        (
            [64, 64],
            0.3,
            "ellipses",
            {"size_m": 0.1, "ratio_m": 2.0, "theta_m": 45.0},
            0.5,
        ),
        ([64, 64], 0.3, "ellipses", {"size_m": 0.05, "ratio_m": 10.0}, None),
        ([64, 64], 0.6, "laminae2", {"size_m": 0.1, "size_s": 0.05}, 0.4),
        ([32, 32, 32], 0.2, "spheres", {"size_m": 0.4}, 0.7),
        ([32, 32, 32], 0.1, "spheroids", {"size_m": 0.3, "ratio_m": 2.0}, 0.7),
        ([32, 32, 32], 0.4, "fibers", {"size_m": 0.2}, 0.6),
        ([32, 32, 32], 0.5, "laminae3", {"size_m": 0.1, "size_s": 0.05}, 1.0),
    ],
)
def test_particle_generator_shape_and_vf(N, vf, kind, shape_params, buffer):
    """Test that the ParticleGenerator produces images of the correct shape and
    approximate volume fraction."""
    gen = ParticleGenerator(
        N=N,
        vf=vf,
        kind=kind,
        shape_params=shape_params,
        buffer=buffer,
        random_seed=42,
    )
    img = gen.sample()
    assert img.shape == tuple(N)
    frac = img.mean()
    assert np.isclose(frac, vf, atol=0.1) or np.isclose(frac, 1.0 - vf, atol=0.1)


def test_particle_generator_accepts_none_shape_params():
    """A `None` shape parameter means "omitted" (e.g. random orientation), as the
    docstring says, instead of failing validation."""
    gen = ParticleGenerator(
        [32, 32],
        0.2,
        "ellipses",
        {"size_m": 0.2, "ratio_m": 2.0, "theta_m": None},
        random_seed=0,
    )
    img = gen.sample()
    assert img.shape == (32, 32)
    assert img.any() and not img.all()


@pytest.mark.parametrize("bad", [-0.1, [0.1], [0.1, -0.2], "0.2"])
def test_particle_generator_rejects_invalid_shape_params(bad):
    """Negative values, wrong-length lists and non-numbers are still rejected."""
    with pytest.raises(ValueError):
        ParticleGenerator([32, 32], 0.2, "disks", {"size_m": bad})


@pytest.mark.parametrize(
    "N,grain_size,thickness,lloyd_iter,mode",
    [
        ([64, 64], 0.25, 0.03, 0, "faces"),
        ([64, 64], [0.15, 0.25], 0.05, 0, "faces"),
        ([64, 64], 0.2, 0.04, 5, "faces"),
        ([32, 32, 32], 0.35, 0.05, 0, "faces"),
        ([32, 32, 32], 0.4, 0.06, 3, "faces"),
        ([32, 32, 32], 0.35, 0.15, 0, "edges"),
        ([32, 32, 32], [0.3, 0.4], [0.1, 0.2], 3, "edges"),
    ],
)
def test_voronoi_generator_shape_and_dtype(N, grain_size, thickness, lloyd_iter, mode):
    """Test that the VoronoiGenerator produces bool images of the correct shape,
    containing both phases."""
    gen = VoronoiGenerator(
        N=N,
        grain_size=grain_size,
        thickness=thickness,
        lloyd_iter=lloyd_iter,
        mode=mode,
        random_seed=42,
    )
    img = gen.sample()
    assert img.shape == tuple(N)
    assert img.dtype == bool
    # Both grains and boundaries should be present for these parameters.
    assert img.any() and not img.all()


def test_voronoi_generator_positional_args():
    """`mode` is the last parameter, so pre-existing positional calls keep their
    meaning (lloyd_iter, invert, random_seed)."""
    gen = VoronoiGenerator([32, 32], 0.3, 0.1, 0, False, 42)
    assert gen.invert is False and gen.mode == "faces"
    assert np.array_equal(
        gen.sample(),
        VoronoiGenerator([32, 32], 0.3, 0.1, invert=False, random_seed=42).sample(),
    )


def test_voronoi_generator_rejects_bad_mode():
    """Unknown modes, and the 3D-only edges mode in 2D, are rejected."""
    with pytest.raises(ValueError):
        VoronoiGenerator([32, 32, 32], 0.3, 0.1, mode="vertices")
    with pytest.raises(ValueError):
        VoronoiGenerator([32, 32], 0.3, 0.1, mode="edges")


# The geometry tests below check VoronoiGenerator internals directly.
# pylint: disable=protected-access


def _polygon_area(poly):
    center = poly.mean(axis=0)
    nxt = np.roll(poly, -1, axis=0)
    return 0.5 * np.linalg.norm(np.cross(poly - center, nxt - center), axis=1).sum()


def test_voronoi_3d_faces_volume_fraction():
    """Wall volume matches sum(face area) * width, up to overlaps at edges."""
    seeds = np.random.default_rng(1).random((27, 3))
    faces = VoronoiGenerator._periodic_voronoi_3d(seeds, "faces")
    width = 0.03
    mask = VoronoiGenerator._rasterize_faces([96, 96, 96], faces, width)
    predicted = sum(_polygon_area(poly) for poly, _ in faces) * width
    assert mask.mean() == pytest.approx(predicted, rel=0.15)
    assert mask.mean() < predicted  # overlaps only remove volume


def test_voronoi_3d_edges_volume_fraction():
    """Strut volume matches sum(edge length) * pi * r^2, up to vertex overlaps."""
    seeds = np.random.default_rng(1).random((27, 3))
    segments = VoronoiGenerator._periodic_voronoi_3d(seeds, "edges")
    width = 0.03
    mask = VoronoiGenerator._rasterize_edges([96, 96, 96], segments, width)
    length = np.linalg.norm(segments[:, 1] - segments[:, 0], axis=1).sum()
    predicted = length * np.pi * (0.5 * width) ** 2
    assert mask.mean() == pytest.approx(predicted, rel=0.25)


def test_voronoi_3d_faces_on_bisectors():
    """Wall voxels lie near the bisector of the two nearest seeds, and every
    voxel essentially on a bisector is covered (no gaps between prisms)."""
    seeds = np.random.default_rng(2).random((27, 3))
    N = [64, 64, 64]
    width = 0.04
    mask = VoronoiGenerator._rasterize_faces(
        N, VoronoiGenerator._periodic_voronoi_3d(seeds, "faces"), width
    )
    axes = [(np.arange(n) + 0.5) / n for n in N]
    d1, d2 = VoronoiGenerator._two_nearest(seeds, np.meshgrid(*axes, indexing="ij"))
    assert (d2 - d1)[mask].max() <= width
    assert mask[(d2 - d1) < 1e-3].all()


def _sorted_periodic_distances(seeds, N):
    """Brute-force sorted distances from every voxel center to all seed images."""
    axes = [(np.arange(n) + 0.5) / n for n in N]
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    offsets = np.array(
        [(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)],
        dtype=float,
    )
    images = (offsets[:, None, :] + seeds[None, :, :]).reshape(-1, 3)
    dist = np.linalg.norm(grid[:, None, :] - images[None, :, :], axis=-1)
    dist.sort(axis=1)
    return dist.reshape(*N, -1)


@pytest.mark.parametrize("n_seeds", [2, 3, 4, 5])
@pytest.mark.parametrize("rng_seed", [3, 9, 12, 13])
def test_voronoi_3d_sparse_seeds(n_seeds, rng_seed):
    """With very few seeds, walls and struts still follow the true periodic
    tessellation: no false walls from outer-image cells, and none missing.

    A voxel within w/2 of a face satisfies d2 - d1 <= w, and one within w/2 of
    an edge satisfies d3 - d1 <= w, where d_k is the k-th nearest seed image.
    """
    seeds = np.random.default_rng(rng_seed).random((n_seeds, 3))
    N = [32, 32, 32]
    width = 0.06
    dist = _sorted_periodic_distances(seeds, N)

    faces = VoronoiGenerator._rasterize_faces(
        N, VoronoiGenerator._periodic_voronoi_3d(seeds, "faces"), width
    )
    gap2 = dist[..., 1] - dist[..., 0]
    assert gap2[faces].max() <= width + 1e-9
    assert faces[gap2 < 1e-3].all()

    edges = VoronoiGenerator._rasterize_edges(
        N, VoronoiGenerator._periodic_voronoi_3d(seeds, "edges"), width
    )
    gap3 = dist[..., 2] - dist[..., 0]
    assert gap3[edges].max() <= width + 1e-9
    assert edges[gap3 < 1e-3].all()


@pytest.mark.parametrize("mode", ["faces", "edges"])
def test_voronoi_3d_periodic(mode):
    """Translating the seeds by whole voxels rolls the image exactly, so the
    structure is seamlessly periodic across the cell faces."""
    N = [40, 40, 40]
    shift = np.array([5, -7, 11])
    seeds = np.random.default_rng(3).random((27, 3))
    raster = (
        VoronoiGenerator._rasterize_faces
        if mode == "faces"
        else VoronoiGenerator._rasterize_edges
    )

    def image(s):
        return raster(N, VoronoiGenerator._periodic_voronoi_3d(s, mode), 0.05)

    base = image(seeds)
    moved = image((seeds + shift / np.array(N)) % 1.0)
    assert base.any()
    assert np.array_equal(np.roll(base, tuple(shift), axis=(0, 1, 2)), moved)


# pylint: enable=protected-access


def test_voronoi_3d_edges_thinner_than_faces():
    """For the same width the strut network occupies less volume than walls."""
    kwargs = {"grain_size": 0.3, "thickness": 0.15, "invert": False, "random_seed": 7}
    faces = VoronoiGenerator([32, 32, 32], mode="faces", **kwargs).sample()
    edges = VoronoiGenerator([32, 32, 32], mode="edges", **kwargs).sample()
    assert (~edges).sum() < (~faces).sum()
    # Struts are a subset of the walls (both centered on the same geometry,
    # capsule radius == half wall width).
    assert not np.any(~edges & faces)


@pytest.mark.parametrize("dtype", [bool, np.uint8, np.int64, np.float32])
def test_from_numpy_generator_normalizes_dtype(tmp_path, dtype):
    """Whatever the file's dtype, the generator yields bool with content intact."""
    ref = np.random.default_rng(3).random((4, 16, 16)) > 0.5
    path = tmp_path / "structures.npy"
    np.save(path, ref.astype(dtype))

    gen = FromNumpyGenerator(str(path))
    for expected in ref:
        img = gen.sample()
        assert img.dtype == bool
        assert np.array_equal(img, expected)


def test_from_numpy_generator_binarizes_grayscale(tmp_path):
    """A grayscale file is thresholded at 0.5 rather than passed through."""
    data = np.random.default_rng(4).random((2, 16, 16))
    path = tmp_path / "grayscale.npy"
    np.save(path, data)

    img = FromNumpyGenerator(str(path)).sample()
    assert img.dtype == bool
    assert np.array_equal(img, data[0] > 0.5)


def test_all_generators_return_bool():
    """Every generator honours the bool contract in the base-class docstring."""
    rng = np.random.default_rng(5)
    generators = [
        RandomGenerator([32, 32], 0.4, random_seed=0),
        SpinodalGenerator([32, 32], 0.4, 8.0, 0.2, random_seed=0),
        TwoPointGenerator([32, 32], rng.random((32, 32)) > 0.6, random_seed=0),
        VoronoiGenerator([32, 32], 0.25, 0.2, random_seed=0),
        ParticleGenerator([32, 32], 0.3, "disks", {"size_m": 0.2}, random_seed=0),
        RandomGenerator([16, 16, 16], 0.4, random_seed=0),
        VoronoiGenerator([16, 16, 16], 0.4, 0.2, random_seed=0),
        VoronoiGenerator([16, 16, 16], 0.4, 0.2, mode="edges", random_seed=0),
        ParticleGenerator([16, 16, 16], 0.3, "spheres", {"size_m": 0.3}, random_seed=0),
    ]
    for gen in generators:
        assert gen.sample().dtype == bool, type(gen).__name__
