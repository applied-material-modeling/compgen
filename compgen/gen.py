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

# pylint: disable=too-many-lines
"""Methods for generating random composite structures."""

from __future__ import annotations

from pathlib import Path
import importlib
from typing import TYPE_CHECKING
import numpy as np
import gstools as gs
from scipy.optimize import curve_fit
from compgen.utils import standardize_image

if TYPE_CHECKING:
    import torch


class DampedOscillationCovariance(gs.CovModel):
    """Damped Oscillation covariance model.

    Args:
        dim (int): Dimension of the model.
        var (float): Variance of the model.
        len_scale (float): Correlation length scale.
        freq (float): Frequency of oscillations.
        damp (float): Damping factor.
    """

    def __init__(self, dim=2, var=1, len_scale=1, amp=0.1, freq=0.1, damp=0.1):
        super().__init__(dim=dim, var=var, len_scale=len_scale)
        self.amp = amp
        self.freq = freq
        self.damp = damp

    def _variogram(self, h, var, len_scale, amp, freq, damp):
        """Actually evaluate the variogram with given parameters.
        Args:
            h (np.ndarray): Lag distances.
            var (float): Variance.
            len_scale (float): Correlation length scale.
            amp (float): Amplitude of oscillations.
            freq (float): Frequency of oscillations.
            damp (float): Damping factor.

        """
        a = var * (1.0 - np.exp(-h / len_scale))
        b = amp * np.exp(-damp * h) * np.sin(2 * np.pi * freq * h)
        return a + b

    def variogram(self, h):
        """Evaluate the variogram at given lag distances.
        Args:
            h (np.ndarray): Lag distances.
        """
        return self._variogram(
            h, self.var, self.len_scale, self.amp, self.freq, self.damp
        )

    def fit(self, r, c):
        """Fit the model to given variogram data.

        Args:
            r (np.ndarray): Radii.
            c (np.ndarray): Variogram values.
        """
        popt, _ = curve_fit(
            self._variogram,
            r,
            c,
            p0=[self.var, self.len_scale, self.amp, self.freq, self.damp],
            bounds=(0, np.inf),
        )
        self.var, self.len_scale, self.amp, self.freq, self.damp = popt
        return self


class EmpiricalCovariance(gs.CovModel):
    """Empirical covariance model from given data.

    Args:
        dim (int): Dimension of the model.
        r (np.ndarray): Radii.
        c (np.ndarray): Variogram values.
    """

    def __init__(self, dim=2, r=None, c=None):
        super().__init__(dim=dim)
        self.r = r
        self.c = c

    def variogram(self, h):
        """Evaluate the variogram at given lag distances by interpolating the empirical data.
        Args:
            h (np.ndarray): Lag distances.
        """
        cov = np.interp(h, self.r, self.c, left=self.c[0], right=self.c[-1])
        return cov


class StructureGenerator:
    """
    Base class for structure generators.

    Keyword Args:
        random_seed (int): Seed for the random number generator. Defaults to None.
    """

    def __init__(self, random_seed=None):
        self.rng = np.random.default_rng(random_seed)

    def _sample_value(self, v):
        """
        Either return a value if it's a scalar or sample from a uniform distribution if it's a list.

        Args:
            v (float or list): Value or range to sample
        """
        if isinstance(v, list) and len(v) == 2:
            return self.rng.uniform(v[0], v[1])
        return v

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        """Generate the next structure."""
        return self.sample()

    def sample(self):
        """Generate the next structure.

        Returns:
            np.ndarray: An array of shape `self.N` with random bool values.
        """
        raise NotImplementedError("Subclasses must implement this method.")


class GenerativeStructureGenerator(StructureGenerator):
    """
    Makes new structures from scratch

    Args:
        N (list): Size of the generated structures in each dimension
    """

    def __init__(self, N, random_seed=None):
        super().__init__(random_seed=random_seed)
        if len(N) < 1:
            raise ValueError("N must be a list with at least one dimension.")
        self.N = N
        self.rng = np.random.default_rng(random_seed)

    @property
    def dim(self):
        """Dimension of the generated structures."""
        return len(self.N)

    @property
    def nx(self):
        """Number of grid points in the x-direction."""
        return self.N[0]

    @property
    def ny(self):
        """Number of grid points in the y-direction."""
        if self.dim < 2:
            return 0
        return self.N[1]

    @property
    def nz(self):
        """Number of grid points in the z-direction."""
        if self.dim < 3:
            return 0
        return self.N[2]

    def sample(self):
        """Generate the next structure.

        Returns:
            np.ndarray: An array of shape `self.N` with random bool values.
        """
        raise NotImplementedError("Subclasses must implement this method.")


class TwoPointGenerator(GenerativeStructureGenerator):
    """Generate structures based on two point correlations.

    Args:
        N (list): Size of the generated structures in each dimension.
        reference_image (np.ndarray): 2D binary array representing the reference structure.

    Keyword Args:
        random_seed (int): Seed for the random number generator. Defaults to None.
        l_guess (float): Initial guess for the correlation length scale. Defaults to 5.0.
        radial_mask (float): Maximum radius to consider for fitting. Defaults to None.
    """

    def __init__(
        self, N, reference_image, random_seed=None, l_guess=5.0, radial_mask=None
    ):
        super().__init__(N, random_seed=random_seed)

        if self.dim != 2:
            raise ValueError(
                "TwoPointGenerator only supports 2D structures for the moment."
            )

        self.l_guess = l_guess
        self.reference_image = standardize_image(reference_image, shape=N, dtype=bool)
        self.acov, self.mean, self.var = self.image_statistics(self.reference_image)
        self.r, self.c = self.radial_average_variogram(self.acov)

        self.model = self.fit_model(self.r, self.c, radial_mask=radial_mask)
        self.generator = gs.SRF(self.model)

    def image_statistics(self, image):
        """Calculate the empirical covariance, mean, and variance of the image.

        Args:
            image (np.ndarray): 2D binary array.
        """
        img = image.astype(float)
        mean = np.mean(img)
        F = np.fft.fft2(img - mean)
        acov = np.fft.fftshift(
            np.real(np.fft.ifft2(F * np.conj(F))) / (img.shape[0] * img.shape[1])
        )
        var = acov[img.shape[0] // 2, img.shape[1] // 2]
        return acov, mean, var

    def radial_average_variogram(self, acov):
        """Compute the radial average of the autocovariance and convert to variogram.

        Args:
            acov (np.ndarray): 2D autocovariance array.

        Returns:
            tuple: Radii and corresponding averaged values.
        """
        x, y = np.indices(acov.shape)
        center = np.array(acov.shape) // 2
        r = np.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)
        r = r.astype(int)

        tbin = np.bincount(r.ravel(), acov.ravel())
        nr = np.bincount(r.ravel())
        radialprofile = tbin / nr
        variogram = radialprofile[0] - radialprofile
        return np.arange(r.max() + 1), variogram

    def fit_model(self, r, c, radial_mask=None):
        """Fit a Gaussian model to the radial average.

        Args:
            r (np.ndarray): Radii.
            c (np.ndarray): Variogram values.

        Keyword Args:
            radial_mask (float): Maximum radius to consider for fitting. Defaults to None.

        Returns:
            gstools.CovModel: Fitted covariance model.
        """
        # Mask off beyond some range
        if radial_mask is not None:
            mask = r <= radial_mask
            r = r[mask]
            c = c[mask]

        model = DampedOscillationCovariance(dim=2)
        model.fit(r, c)

        return model

    def sample(self):
        """Generate a new structure matching the target 2-point correlation.

        Returns:
            np.ndarray: A 2D array of shape (nx, ny) with random bool values.
        """
        x = np.arange(self.nx)
        y = np.arange(self.ny)
        field = self.generator.structured([x, y], seed=self.rng.integers(0, 1e9))

        z = (field - np.mean(field)) / np.std(field)
        thresh = np.quantile(z, 1 - self.mean)

        generated = (z > thresh).astype(bool)

        return generated


class SpinodalGenerator(GenerativeStructureGenerator):
    """Generate structures based on spinodal decomposition.

    Args:
        N (list): Size of the generated structures in each dimension.
        vf (float or list): Volume fraction of phase A or range for random samples.
        l (float or list): Characteristic length scale or range for random samples.
        bandwidth (float or list): Bandwidth of the spinodal structure or range for random samples.

    Keyword Args:
        random_seed (int): Seed for the random number generator. Defaults to None.
    """

    def __init__(self, N, vf, l, bandwidth, random_seed=None):
        super().__init__(N, random_seed=random_seed)
        self.vf_input = vf
        self.l_input = l
        self.bandwidth_input = bandwidth

    def sample(self):
        """Sample parameters for the next structure.

        Returns:
            np.ndarray: An array of shape `self.N` with random bool values.
        """
        # Sample the parameters
        vf = self._sample_value(self.vf_input)
        l = self._sample_value(self.l_input)
        bandwidth = self._sample_value(self.bandwidth_input)

        # Build k-vectors for each dimension and compute spectral magnitude
        ks = [2.0 * np.pi * np.fft.fftfreq(n) for n in self.N]
        K_components = np.meshgrid(*ks, indexing="ij")
        K_mag = np.zeros_like(K_components[0])
        for K in K_components:
            K_mag = K_mag + K**2
        K_mag = np.sqrt(K_mag)

        k0 = 2.0 * np.pi / l
        sigma_k = bandwidth * k0

        assert sigma_k > 0.0
        amplitude_spectrum = np.exp(-0.5 * ((K_mag - k0) / sigma_k) ** 2)
        amplitude_spectrum[K_mag == 0] = 0.0

        g = self.rng.normal(size=tuple(self.N))
        g_hat = np.fft.fftn(g)

        amp_filter = np.sqrt(amplitude_spectrum)
        h_hat = g_hat * amp_filter

        h = np.fft.ifftn(h_hat).real
        # h = (h - np.mean(h)) / np.std(h)
        std = np.std(h)
        h = (h - np.mean(h)) / max(std, 1e-12)

        T = np.quantile(h, 1 - vf)
        img = h > T

        return img


class RandomGenerator(GenerativeStructureGenerator):
    """Generate random structures of a given shape.

    Args:
        N (list): Size of the generated structures in each dimension.
        vf (float or list): Volume fraction of phase A or range for random samples.

    Keyword Args:
        random_seed (int): Seed for the random number generator. Defaults to None.
    """

    def __init__(self, N, vf, random_seed=None):
        super().__init__(N, random_seed=random_seed)
        self.vf_input = vf

    def sample(self):
        """Generate the next random structure via hierarchical sampling.

        Returns:
            np.ndarray: An array of shape `self.N` with random bool values.
        """
        # First select the volume fraction of phase A
        vf = self._sample_value(self.vf_input)
        total = int(np.prod(self.N))
        nf = int(total * vf)
        # Handle trivial cases explicitly
        if nf <= 0:
            return np.zeros(tuple(self.N), dtype=bool)
        if nf >= total:
            return np.ones(tuple(self.N), dtype=bool)

        # Then sample a hierarchical random structure across arbitrary dimensions
        inds = self.rng.choice(total, size=nf, replace=False)
        img = np.zeros((total,), dtype=bool)
        img[inds] = True
        return img.reshape(tuple(self.N))


class FromNumpyGenerator(StructureGenerator):
    """
    Just read a npy file. The assumption is the first axis is the number of
    structures and then the rest are the dimensions.

    Args:
        filename (str): Path to the .npy file containing the structures.
    """

    # A fixed list rather than a stream: the runner draws each structure once
    # and does not backfill failures (see runner.run).
    predefined = True

    def __init__(self, filename, random_seed=None):
        super().__init__(random_seed=random_seed)
        self.data = np.load(filename)
        self.index = 0
        self.total = self.data.shape[0]

    def sample(self):
        """Generate the next structure from the loaded data.

        The file's dtype is not trusted: like every other generator this returns
        bool, thresholding non-binary values at 0.5.

        Returns:
            np.ndarray: A bool array of shape corresponding to the loaded structures.
        """
        if self.index >= self.total:
            self.index = 0  # Reset to the beginning if we reach the end
        generated = self.data[self.index]
        self.index += 1
        return standardize_image(generated, dtype=bool)


# pylint: disable=too-many-instance-attributes
class Reconstruction2D(GenerativeStructureGenerator):
    """Reconstruction-based generator using the MCRpy library.

    Args:
        N (list): Desired output size [nx, ny].
        target_path (str or Path): Path to a target `.npy` file, or a folder
            containing multiple `.npy` files.

    Keyword Args:
        random_seed (int): Seed for the random number generator.
        descriptors (dict[str, float]): Mapping from descriptor name to weight.
            Example: {"VolumeFractions": 5.0, "Correlations": 1.0}
            Default is {"Correlations": 1.0} (recommended)
        limit_to (int): Limit for descriptor convolutions.
    """

    def __init__(
        self,
        N,
        target_path,
        random_seed=None,
        descriptors=None,
        limit_to=16,
    ):
        super().__init__(N, random_seed=random_seed)

        if self.dim != 2:
            raise ValueError(
                "Reconstruction2D only supports 2D structures for the moment."
            )

        # mcrpy required only if this generator is used
        try:
            self.mcrpy = importlib.import_module("mcrpy")
        except ImportError as e:
            raise RuntimeError(
                "Reconstruction2D requires the MCRpy library. "
                "To install in the active python environment:"
                "    pip install mcrpy"
            ) from e

        # mcrpy expects np.product
        if not hasattr(np, "product"):
            np.product = np.prod

        self.target_path = Path(target_path)
        if not self.target_path.exists():
            raise FileNotFoundError(f"Target file/folder not found: {self.target_path}")

        if self.target_path.is_file():
            self.target_files = [self.target_path]
        elif self.target_path.is_dir():
            self.target_files = sorted(self.target_path.glob("*.npy"))
            if len(self.target_files) == 0:
                raise FileNotFoundError(
                    f"No .npy files found in target folder: {self.target_path}"
                )
        else:
            raise ValueError(
                f"target_path must be a file or directory, got: {self.target_path}"
            )

        self.targets = []
        common_shape = None
        for f in self.target_files:
            arr = np.asarray(np.load(f))
            arr = np.squeeze(arr)
            if arr.ndim != 2:
                raise ValueError(f"Target '{f}' must be 2D, got shape {arr.shape}")
            arr_bin = standardize_image(arr, dtype=int)
            if common_shape is None:
                common_shape = arr_bin.shape
            else:
                if arr_bin.shape != common_shape:
                    raise ValueError("All target arrays must have the same shape. ")
            self.targets.append(arr_bin)

        if len(self.targets) == 0:
            raise RuntimeError("No valid targets were loaded.")

        self.n_targets = len(self.targets)
        self.target_shape = common_shape
        self.target_vf = float(np.mean([np.mean(t) for t in self.targets]))
        self.targets_ms = [self._array_to_microstructure(t) for t in self.targets]

        # mcrpy settings
        if descriptors is None:
            descriptors = {"Correlations": 1.0}
        allowed_descriptors = {
            "VolumeFractions",
            "Variation",
            "TwoPointCorrelations",
            "Correlations",
            "FFTCorrelations",
            "LinealPathApproximation",
        }
        invalid_keys = set(descriptors.keys()) - allowed_descriptors
        if invalid_keys:
            raise ValueError(
                f"Invalid descriptor keys: {invalid_keys}. "
                f"Allowed keys are: {allowed_descriptors}"
            )
        self.descriptor_types = list(descriptors.keys())
        self.descriptor_weights = list(descriptors.values())
        self.limit_to = limit_to
        self.char_settings = self.mcrpy.CharacterizationSettings(
            descriptor_types=self.descriptor_types,
            limit_to=self.limit_to,
        )
        self.recon_settings = self.mcrpy.ReconstructionSettings(
            descriptor_types=self.descriptor_types,
            descriptor_weights=self.descriptor_weights,
            limit_to=self.limit_to,
            use_multigrid_reconstruction=True,
            max_iter=200,
        )

    def _array_to_microstructure(self, arr):
        ms = self.mcrpy.Microstructure(
            arr,
            use_multiphase=False,
        )
        return ms

    def _make_descriptor(self):
        """Build a single descriptor dictionary consumable by MCRpy."""
        descs = [
            self.mcrpy.characterize(ms, self.char_settings) for ms in self.targets_ms
        ]

        # If there is only one target, no averaging is needed.
        if len(descs) == 1:
            return descs[0]

        # Build new descriptor by averaging the descriptors across all targets while
        # keeping the settings from the first one (they are the same across all targets).
        descriptor_dict = {}
        for k in descs[0]:
            if k == "settings":
                descriptor_dict[k] = descs[0][k]
            else:
                descriptor_dict[k] = sum(d[k] for d in descs) / len(descs)

        return descriptor_dict

    def reconstruct(self, initial_array):
        """Run MCRpy reconstruction starting from `initial_array`."""

        descriptor_dict = self._make_descriptor()
        initial_ms = self._array_to_microstructure(initial_array)

        _, reconstructed_ms = self.mcrpy.reconstruct(
            descriptor_dict=descriptor_dict,
            desired_shape=self.target_shape,
            settings=self.recon_settings,
            initial_microstructure=initial_ms,
        )

        generated = reconstructed_ms.decode_phases(raw=True)
        generated = np.asarray(generated)
        generated = np.squeeze(generated)
        return generated

    def sample(self):
        """Generate a new structure via MCRpy reconstruction.

        Returns:
            np.ndarray: A 2D bool array of shape ``(nx, ny)``.
        """
        # Control first guess for reproducibility
        first_guess = self.rng.random(self.target_shape) < self.target_vf

        generated = self.reconstruct(first_guess)
        generated = standardize_image(generated, shape=(self.nx, self.ny), dtype=bool)
        return generated


# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=import-outside-toplevel
class ParticleGenerator(GenerativeStructureGenerator):
    """Generate microstructures by randomly placing and optionally rearranging particles.

    All entries of `N` must be equal. Supported `kind` values:
        2D (use with `N` of length 2): "laminae2", "disks", "ellipses"
        3D (use with `N` of length 3): "laminae3", "fibers", "spheres", "spheroids"

    `args` parameter conventions:
        each value is a `float` (fixed) or a `[min, max]` list (sampled uniformly each
            :meth:`sample` call):
        `*_m` / `*_s` suffixes denote mean and spread (half-width) of the uniform distribution
            for that parameter; if `_m` is given but `_s` is omitted, then `_s` automatically
            set to 0.0. The `_s` (spread) key is optional; if absent, the parameter is fixed
            at `_m`.

        `size_*`: mean / half-width of the particle's characteristic axis length in normalised
            units [0, 1] (`size_m` wrt unit cell, `size_s` wrt `size_m` for compatibility
            with sample method logic). For spheroids this is the equatorial diameter; the value
            is halved internally to get the semi-axis.
        `ratio_*`: mean / half-width of the aspect ratio (major/minor).
            Values > 1 give prolate shapes; < 1 oblate.
        `theta_*`: mean / half-width of the 2-D in-plane orientation angle
            in degrees. Omit (or set to `None`) for a uniformly random orientation.
        `az_*`, `el_*`: mean / half-width of the azimuth and
            elevation angles in degrees for 3-D orientation. Omit for isotropic sampling.

    Args:
        N (list[int]): Grid resolution in each dimension; all entries must be equal.
        vf (float or list[float, float]): Target volume fraction, or `[min, max]`
            range sampled on each call.
        kind (str): Particle shape identifier — see the table above.
        args (dict[str, float | list]): Shape parameters — see conventions above.

    Keyword Args:
        buffer (float | None): Minimum surface-to-surface clearance in normalised units.
            `None` (default) skips rearrangement entirely.
        dt (float): Adam learning rate for overlap minimisation. Ignored when
            `buffer` is `None`. Default `0.001`.
        max_iter (int): Maximum optimisation iterations per placement attempt. Ignored
            when `buffer` is `None`. Default `1000`.
        tol (float): Overlap-energy threshold for convergence. Ignored when `buffer`
            is `None`. Default `1e-9`.
        random_seed (int | None): Seed for both the NumPy and PyTorch RNGs.
    """

    def __init__(
        self,
        N,
        vf,
        kind: str,
        shape_params: dict[str, float],
        buffer: float | None = None,
        dt: float = 0.001,
        max_iter: int = 1000,
        tol: float = 1e-9,
        random_seed=None,
    ):
        super().__init__(N, random_seed=random_seed)
        self.random_seed = random_seed

        try:
            import torch  # pylint: disable=import-error
        except ImportError as e:
            raise RuntimeError(
                "ParticleGenerator requires PyTorch. "
                "Install it with: pip install torch"
            ) from e

        self.torch_rng = torch.Generator(device="cpu")
        if random_seed is not None:
            self.torch_rng.manual_seed(random_seed)

        self.vf_input = vf
        self.res = self.N[0]
        self.buffer = buffer
        if buffer is not None:
            self.dt = dt
            self.max_iter = max_iter
            self.tol = tol
        self.kind = kind
        self.shape_params = shape_params
        self.shape_params, self.idim, self.pdim, self.opt_i = self._particle_setup()

        if self.idim != self.dim:
            raise ValueError(
                f"Expected particle kind of dimension {self.dim}, got {self.idim}."
            )

        if any(x != N[0] for x in N):
            raise ValueError(
                "Particle generator only supports same size in all directions, "
                f"received {tuple(N)}."
            )

    def _particle_setup(self):
        K2 = {"size_m", "size_s"}
        K3 = K2 | {"ratio_m", "ratio_s"}
        K4 = K3 | {"theta_m", "theta_s"}
        K5 = K3 | {"az_m", "az_s", "el_m", "el_s"}
        specs = {
            "laminae2": (2, 1, 1, K2),
            "disks": (2, 2, 2, K2),
            "ellipses": (2, 2, 3, K4),
            "spheres": (3, 3, 3, K2),
            "spheroids": (3, 3, 4, K5),
            "laminae3": (3, 1, 1, K2),
            "fibers": (3, 2, 2, K3),
        }

        if self.kind not in specs:
            admitted_kinds = {
                str(d): {k for k, v in specs.items() if v[0] == d} for d in (2, 3)
            }
            raise ValueError(
                f"kind input `{self.kind}` not recognized. Admitted kinds are: \n"
                f"{' '*12}2D: {admitted_kinds['2']}\n"
                f"{' '*12}3D: {admitted_kinds['3']}"
            )

        for val in self.shape_params.values():
            if isinstance(val, (int, float)) and val >= 0:
                continue
            if (
                isinstance(val, list)
                and len(val) == 2
                and all(isinstance(x, (int, float)) and x >= 0 for x in val)
            ):
                continue
            raise ValueError(
                "`shape_params` values must be positive floats or lists of 2 floats"
            )

        dim, pdim, opt_i, keys = specs[self.kind]
        # `keys` is a set, whose iteration order is randomised per process by
        # PYTHONHASHSEED. `sample` consumes one RNG draw per key in this dict's
        # order, so an unsorted order makes the draw-to-parameter assignment
        # differ between process launches and breaks seed reproducibility.
        # Sort the keys to keep the sampling order deterministic.
        shape_params = {k: self.shape_params.get(k, None) for k in sorted(keys)}

        return shape_params, dim, pdim, opt_i

    def sample(self):
        """Sample volume fraction and particle geometry, place (and optionally
        rearrange) particles, then rasterize onto the grid.

        Returns:
            np.ndarray: 2D/3D bool array of shape `self.N`.
        """
        import torch  # pylint: disable=import-error

        rearrange = self.buffer is not None

        # Per-dimension caps: rearranging more particles becomes prohibitively slow.
        n_allowed = (100, 50, 20)

        vf = self._sample_value(self.vf_input)

        shape_params = {}
        for key, value in self.shape_params.items():
            if value is not None:
                shape_params[key] = self._sample_value(value)
            else:
                shape_params[key] = None

        particles = ParticleGenerator._initialize_particles(
            pdim=self.pdim,
            phi=vf,
            shape_params=shape_params,
            # Cap placement to stop a runaway/degenerate sample from hanging.
            max_particles=(self.res // 2) ** self.pdim,
            torch_rng=self.torch_rng,
        )

        if rearrange and particles.shape[0] > 1:
            if particles.shape[0] > n_allowed[self.pdim - 1]:
                raise RuntimeError("Too many particles needed for this sample.")

            buffer = self._sample_value(self.buffer)

            particles, converged = ParticleGenerator._rearrange_particles(
                particles=particles,
                opt_i=self.opt_i,
                buffer=buffer,
                dt=self.dt,
                max_iter=self.max_iter,
                tol=self.tol,
            )

            if not converged:
                raise RuntimeError(
                    f"Rearrangement failed to reach tolerance within {self.max_iter} iterations."
                )

        img = ParticleGenerator._rasterize_particles(
            dim=self.idim, pdim=self.pdim, particles=particles, res=self.res
        )

        # Randomly swap phases so neither is always the "particle" phase.
        if torch.rand((), generator=self.torch_rng) < 0.5:
            return ~img

        return img

    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    @staticmethod
    def _initialize_particles(
        pdim: int,
        phi: float,
        shape_params: dict,
        max_particles: int | None = None,
        dtype: torch.dtype | None = None,
        device: str | torch.device = "cpu",
        torch_rng: torch.Generator | None = None,
    ):
        import torch  # pylint: disable=import-error

        if dtype is None:
            dtype = torch.float64
        device = torch.device(device)

        if phi <= 0:
            raise RuntimeError("Zero or negative volume fraction.")

        pi = torch.tensor(torch.pi, dtype=dtype, device=device)
        deg_to_rad = pi / 180.0

        def get_angle(key_m, key_s):
            m = shape_params.get(key_m)
            if m is None:
                return None, None
            s = shape_params.get(key_s) or 0.0
            return m * deg_to_rad, s * deg_to_rad

        if shape_params["size_m"] is not None:
            size_m = shape_params["size_m"] / 2.0
        else:
            raise ValueError("args must include size_m")

        size_s = (shape_params.get("size_s") or 0.0) * size_m
        ratio_m = shape_params.get("ratio_m") or 1.0
        ratio_s = shape_params.get("ratio_s") or 0.0
        theta_m, theta_s = get_angle("theta_m", "theta_s")
        az_m, az_s = get_angle("az_m", "az_s")
        el_m, el_s = get_angle("el_m", "el_s")

        def _uniform(mean, spread):
            if spread is None or spread == 0.0:
                return torch.as_tensor(mean, dtype=dtype, device=device)
            if mean < spread:
                raise ValueError("mean must be >= spread.")
            return (
                mean
                - spread
                + 2.0
                * spread
                * torch.rand((), dtype=dtype, device=device, generator=torch_rng)
            )

        total = torch.tensor(0.0, dtype=dtype, device=device)
        target = torch.tensor(phi, dtype=dtype, device=device)
        rows = []

        while total < target:

            # Anti-hang guard: a too-small sampled particle size would otherwise
            # need an unbounded number of particles to reach the target volume
            # fraction (and if a particle's volume falls below the FP resolution
            # of `total`, the loop would never terminate). `rows` grows every
            # iteration even when `total` stalls, so this catches both cases.
            if max_particles is not None and len(rows) >= max_particles:
                raise RuntimeError(
                    f"Placement exceeded {max_particles} particles; the sampled "
                    "particle size is too small for the target volume fraction."
                )

            if pdim == 1:
                a = _uniform(size_m, size_s)
                x = torch.rand((), dtype=dtype, device=device, generator=torch_rng)
                row = torch.stack([x, a])
                value = 2.0 * a

            elif pdim == 2:
                a = _uniform(size_m, size_s)
                r = _uniform(ratio_m, ratio_s)
                b = a * r
                theta = (
                    2.0
                    * pi
                    * torch.rand((), dtype=dtype, device=device, generator=torch_rng)
                    if theta_m is None
                    else _uniform(theta_m, theta_s)
                )
                x = torch.rand((), dtype=dtype, device=device, generator=torch_rng)
                y = torch.rand((), dtype=dtype, device=device, generator=torch_rng)
                row = torch.stack([x, y, theta, a, b])
                value = pi * a * b

            else:
                b = _uniform(size_m, size_s)
                r = _uniform(ratio_m, ratio_s)
                a = b * r
                az = (
                    2.0
                    * pi
                    * torch.rand((), dtype=dtype, device=device, generator=torch_rng)
                    if az_m is None
                    else _uniform(az_m, az_s)
                )
                el = (
                    -pi / 2.0
                    + pi
                    * torch.rand((), dtype=dtype, device=device, generator=torch_rng)
                    if el_m is None
                    else _uniform(el_m, el_s)
                )
                x = torch.rand((), dtype=dtype, device=device, generator=torch_rng)
                y = torch.rand((), dtype=dtype, device=device, generator=torch_rng)
                z = torch.rand((), dtype=dtype, device=device, generator=torch_rng)
                row = torch.stack([x, y, z, az, el, a, b])
                value = (4.0 / 3.0) * pi * a * b * b

            if value == 0.0:
                raise ValueError("Degenerate particles.")

            new_total = total + value
            if rows and torch.abs(new_total - target) > torch.abs(total - target):
                break
            total = new_total
            rows.append(row)

        particles = torch.stack(rows, dim=0)

        return particles

    # pylint: disable=too-many-statements
    @staticmethod
    def _overlap_energy(particles, buffer, eps=1e-12):
        import torch  # pylint: disable=import-error

        p = particles
        n = p.shape[0]
        if n <= 1:
            raise RuntimeError("Overlap calculation requires multiple particles")
        ncol = p.shape[1]

        if ncol == 2:  # 1D: [x, a]
            x = p[:, 0]
            a = p[:, 1]

            dx = x[:, None] - x[None, :]
            dx = dx - torch.round(dx)

            m = a[:, None] ** 2 + a[None, :] ** 2 + eps
            mu2 = dx * dx / m
            mu = torch.sqrt(torch.clamp(mu2, min=0.0) + eps)

        elif ncol == 5:  # 2D: [x, y, theta, a, b]
            x = p[:, 0]
            y = p[:, 1]
            theta = p[:, 2]
            a = p[:, 3]
            b = p[:, 4]

            c = torch.cos(theta)
            s = torch.sin(theta)
            a2 = a * a
            b2 = b * b

            q11 = a2 * c * c + b2 * s * s
            q12 = (a2 - b2) * c * s
            q22 = a2 * s * s + b2 * c * c

            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]

            dx = dx - torch.round(dx)
            dy = dy - torch.round(dy)

            m11 = q11[:, None] + q11[None, :]
            m12 = q12[:, None] + q12[None, :]
            m22 = q22[:, None] + q22[None, :]

            det = m11 * m22 - m12 * m12 + eps
            mu2 = (m22 * dx * dx - 2.0 * m12 * dx * dy + m11 * dy * dy) / det
            mu = torch.sqrt(torch.clamp(mu2, min=0.0) + eps)

        elif ncol == 7:  # 3D: [x, y, z, az, el, a, b]
            x = p[:, 0]
            y = p[:, 1]
            z = p[:, 2]
            az = p[:, 3]
            el = p[:, 4]
            a = p[:, 5]
            b = p[:, 6]

            ca = torch.cos(az)
            sa = torch.sin(az)
            ce = torch.cos(el)
            se = torch.sin(el)

            nx = ce * ca
            ny = ce * sa
            nz = se

            a2 = a * a
            b2 = b * b
            d2 = a2 - b2

            q11 = b2 + d2 * nx * nx
            q12 = d2 * nx * ny
            q13 = d2 * nx * nz
            q22 = b2 + d2 * ny * ny
            q23 = d2 * ny * nz
            q33 = b2 + d2 * nz * nz

            dx = x[:, None] - x[None, :]
            dy = y[:, None] - y[None, :]
            dz = z[:, None] - z[None, :]

            dx = dx - torch.round(dx)
            dy = dy - torch.round(dy)
            dz = dz - torch.round(dz)

            m11 = q11[:, None] + q11[None, :]
            m12 = q12[:, None] + q12[None, :]
            m13 = q13[:, None] + q13[None, :]
            m22 = q22[:, None] + q22[None, :]
            m23 = q23[:, None] + q23[None, :]
            m33 = q33[:, None] + q33[None, :]

            c11 = m22 * m33 - m23 * m23
            c12 = m13 * m23 - m12 * m33
            c13 = m12 * m23 - m13 * m22
            c22 = m11 * m33 - m13 * m13
            c23 = m12 * m13 - m11 * m23
            c33 = m11 * m22 - m12 * m12
            det = m11 * c11 + m12 * c12 + m13 * c13 + eps
            mu2 = (
                dx * dx * c11
                + dy * dy * c22
                + dz * dz * c33
                + 2.0 * (dx * dy * c12 + dx * dz * c13 + dy * dz * c23)
            ) / det

            mu = torch.sqrt(torch.clamp(mu2, min=0.0) + eps)

        else:
            raise RuntimeError(f"Invalid particle shape {p.shape}.")

        iu, ju = torch.triu_indices(p.shape[0], p.shape[0], offset=1, device=p.device)
        overlap = torch.clamp((1.0 + buffer) - mu[iu, ju], min=0.0)
        norm = n * (n - 1) / 2

        return (overlap * overlap).sum() / norm

    @staticmethod
    def _rearrange_particles(particles, opt_i, buffer, dt, max_iter, tol=1e-9):
        import torch  # pylint: disable=import-error

        opt_i = list(range(opt_i))
        p = particles.detach().clone().requires_grad_(True)
        optimizer = torch.optim.Adam([p], lr=dt)

        opt_set = set(opt_i)
        non_opt = [i for i in range(p.shape[1]) if i not in opt_set]
        energy_value = float("inf")

        for _ in range(max_iter):

            optimizer.zero_grad()
            energy = ParticleGenerator._overlap_energy(p, buffer=buffer)
            energy.backward()

            with torch.no_grad():
                p.grad[:, non_opt] = 0.0

            optimizer.step()

            with torch.no_grad():
                # Wrap positions back into [0, 1) (periodic domain).
                if 0 in opt_set:
                    p[:, 0] %= 1.0
                if 1 in opt_set:
                    p[:, 1] %= 1.0
                if p.shape[1] == 7 and 2 in opt_set:
                    p[:, 2] %= 1.0

                # Wrap angles to their principal range.
                if p.shape[1] == 5 and 2 in opt_set:
                    p[:, 2] %= 2.0 * torch.pi
                elif p.shape[1] == 7:
                    if 3 in opt_set:
                        p[:, 3] %= 2.0 * torch.pi
                    if 4 in opt_set:  # elevation: keep in [-π/2, π/2]
                        p[:, 4] += torch.pi / 2.0
                        p[:, 4] %= torch.pi
                        p[:, 4] -= torch.pi / 2.0

            energy_value = energy.item()

            if energy_value < tol:
                break

        converged = energy_value < tol
        return p.detach(), converged

    @staticmethod
    @staticmethod
    def _rasterize_particles(dim, pdim, particles, res, dtype=bool):
        particles = np.asarray(particles, dtype=float)

        shape = (res,) * dim
        axes = [(np.arange(res, dtype=float) + 0.5) / res for _ in range(dim)]
        grids = np.meshgrid(*axes, indexing="ij")
        eps = 1e-12

        if pdim == 1:
            a_max = float(particles[:, 1].max())
        elif pdim == 2:
            a_max = float(particles[:, 3:5].max())
        else:
            a_max = float(particles[:, 5:7].max())
        stencil = int(np.ceil(a_max))
        off = range(-stencil, stencil + 1)

        inside = np.zeros(shape, dtype=bool)

        if pdim == 1:
            x = particles[:, 0]
            a = particles[:, 1]
            for ox in off:
                dx = grids[0][..., None] - (x + ox)
                inside |= np.any((dx / (a + eps)) ** 2 <= 1.0, axis=-1)

        elif pdim == 2:
            x = particles[:, 0]
            y = particles[:, 1]
            theta = particles[:, 2]
            a = particles[:, 3]
            b = particles[:, 4]
            c = np.cos(theta)
            s = np.sin(theta)
            for ox in off:
                for oy in off:
                    dx = grids[0][..., None] - (x + ox)
                    dy = grids[1][..., None] - (y + oy)
                    q1 = c * dx + s * dy
                    q2 = -s * dx + c * dy
                    ell = (q1 / (a + eps)) ** 2 + (q2 / (b + eps)) ** 2
                    inside |= np.any(ell <= 1.0, axis=-1)

        else:  # pdim == 3
            x = particles[:, 0]
            y = particles[:, 1]
            z = particles[:, 2]
            az = particles[:, 3]
            el = particles[:, 4]
            a = particles[:, 5]
            b = particles[:, 6]
            ca, sa = np.cos(az), np.sin(az)
            ce, se = np.cos(el), np.sin(el)
            u = np.stack([ce * ca, ce * sa, se], axis=-1)
            ref = np.where(
                (np.abs(u[:, 0]) < 0.9)[:, None],
                np.array([[1.0, 0.0, 0.0]]),
                np.array([[0.0, 1.0, 0.0]]),
            )
            v = np.cross(u, ref)
            v /= np.linalg.norm(v, axis=-1, keepdims=True) + eps
            w = np.cross(u, v)
            w /= np.linalg.norm(w, axis=-1, keepdims=True) + eps
            for ox in off:
                for oy in off:
                    for oz in off:
                        dx = grids[0][..., None] - (x + ox)
                        dy = grids[1][..., None] - (y + oy)
                        dz = grids[2][..., None] - (z + oz)
                        q1 = dx * u[:, 0] + dy * u[:, 1] + dz * u[:, 2]
                        q2 = dx * v[:, 0] + dy * v[:, 1] + dz * v[:, 2]
                        q3 = dx * w[:, 0] + dy * w[:, 1] + dz * w[:, 2]
                        ell = (
                            (q1 / (a + eps)) ** 2
                            + (q2 / (b + eps)) ** 2
                            + (q3 / (b + eps)) ** 2
                        )
                        inside |= np.any(ell <= 1.0, axis=-1)

        mask = np.zeros(shape, dtype=dtype)
        mask[inside] = True
        return mask


class VoronoiGenerator(GenerativeStructureGenerator):
    """Generate periodic Voronoi tessellations with thick grain boundaries.

    Random seed points partition the unit cell into Voronoi grains.
    The tessellation is exactly periodic: distances use the minimum-image
    convention on the unit torus, so grains and boundaries wrap seamlessly across
    every face.

    Args:
        N (list[int]): Grid resolution in each dimension (length 2 or 3).
        grain_size (float or list): Characteristic grain diameter in normalised
            units ``[0, 1]`` (relative to the unit cell), or a ``[min, max]``
            range sampled per call. Smaller values give more, finer grains; the
            seed count is derived as ``round((1 / grain_size) ** dim)``.
        thickness (float or list): Grain-boundary thickness as a fraction of the
            grain size, or a ``[min, max]`` range. Near a flat Voronoi facet the
            full boundary width is approximately ``thickness * grain_size`` in
            normalised units.

    Keyword Args:
        lloyd_iter (int): Number of Lloyd relaxation iterations applied to the
            seeds before tessellation. ``0`` (default) leaves seeds fully random
            (irregular Poisson-Voronoi grains with a broad size distribution); a
            few iterations (e.g. 3-10) yield progressively more equiaxed,
            uniformly sized grains.
        invert (bool): If ``True`` (default) randomly swap the two phases so the
            boundary network is not always the same phase. Set ``False`` for a
            deterministic convention (grains ``True``, boundaries ``False``).
        random_seed (int): Seed for the random number generator. Defaults to None.
    """

    def __init__(
        self,
        N,
        grain_size,
        thickness,
        lloyd_iter=0,
        invert: bool = True,
        random_seed=None,
    ):
        super().__init__(N, random_seed=random_seed)
        if self.dim not in (2, 3):
            raise ValueError(
                f"VoronoiGenerator supports 2D or 3D only, got dim={self.dim}."
            )
        self.grain_size_input = grain_size
        self.thickness_input = thickness
        self.lloyd_iter_input = lloyd_iter
        self.invert = invert

    def sample(self):
        """Sample grain size and boundary thickness, build the periodic
        tessellation, and classify grains vs. boundaries.

        Returns:
            np.ndarray: 2D/3D bool array of shape `self.N`.
        """
        grain_size = self._sample_value(self.grain_size_input)
        thickness = self._sample_value(self.thickness_input)
        lloyd_iter = round(self._sample_value(self.lloyd_iter_input))

        n_grains = max(2, int(round((1.0 / grain_size) ** self.dim)))

        # Seeds and cell-center coordinates, both in normalised units [0, 1).
        seeds = self.rng.random((n_grains, self.dim))
        axes = [(np.arange(n) + 0.5) / n for n in self.N]
        grids = np.meshgrid(*axes, indexing="ij")

        if lloyd_iter > 0:
            seeds = self._relax_seeds(seeds, grids, lloyd_iter)

        d1, d2 = self._two_nearest(seeds, grids)

        # Boundary where a point is near the bisector of its two nearest seeds.
        boundary = (d2 - d1) <= thickness * grain_size

        # Grain interiors True, boundaries False (before optional inversion).
        img = ~boundary

        # Random phase inverter, matching the ParticleGenerator convention.
        if self.invert and self.rng.random() < 0.5:
            return ~img

        return img

    @staticmethod
    def _two_nearest(seeds, grids):
        """Distances to the nearest and second-nearest seed for every grid point.

        Uses the minimum-image convention per axis so distances are periodic on
        the unit torus. Tracks only the two smallest distances, keeping memory at
        O(grid points) regardless of the number of seeds.

        Args:
            seeds (np.ndarray): ``(n_grains, dim)`` seed coordinates in [0, 1).
            grids (list[np.ndarray]): Per-axis coordinate grids from meshgrid.

        Returns:
            tuple[np.ndarray, np.ndarray]: ``(d1, d2)`` nearest / second-nearest
            distance arrays, each of shape ``grids[0].shape``.
        """
        shape = grids[0].shape
        d1 = np.full(shape, np.inf)
        d2 = np.full(shape, np.inf)
        for s in seeds:
            dist2 = np.zeros(shape)
            for k, g in enumerate(grids):
                delta = g - s[k]
                delta -= np.round(delta)  # minimum image -> periodic
                dist2 += delta * delta
            dist = np.sqrt(dist2)
            closer = dist < d1
            d2 = np.where(closer, d1, d2)
            d1 = np.where(closer, dist, d1)
            between = (~closer) & (dist < d2)
            d2 = np.where(between, dist, d2)
        return d1, d2

    @staticmethod
    def _relax_seeds(seeds, grids, iters):
        """Lloyd relaxation on the periodic domain for more equiaxed grains.

        Each iteration assigns every grid point to its nearest seed, then moves
        each seed to the circular-mean (periodic) centroid of its cell. Empty
        cells are left in place.

        Args:
            seeds (np.ndarray): ``(n_grains, dim)`` seed coordinates in [0, 1).
            grids (list[np.ndarray]): Per-axis coordinate grids from meshgrid.
            iters (int): Number of relaxation iterations.

        Returns:
            np.ndarray: Relaxed seed coordinates, same shape as `seeds`.
        """
        n_grains = seeds.shape[0]
        flat_coords = [g.ravel() for g in grids]
        npts = flat_coords[0].size
        two_pi = 2.0 * np.pi
        for _ in range(iters):
            owner = np.zeros(npts, dtype=np.intp)
            best = np.full(npts, np.inf)
            for i, s in enumerate(seeds):
                dist2 = np.zeros(npts)
                for k, c in enumerate(flat_coords):
                    delta = c - s[k]
                    delta -= np.round(delta)
                    dist2 += delta * delta
                closer = dist2 < best
                owner[closer] = i
                best[closer] = dist2[closer]

            new = seeds.copy()
            for k, c in enumerate(flat_coords):
                ang = two_pi * c
                cos = np.bincount(owner, weights=np.cos(ang), minlength=n_grains)
                sin = np.bincount(owner, weights=np.sin(ang), minlength=n_grains)
                cnt = np.bincount(owner, minlength=n_grains)
                coord = (np.arctan2(sin, cos) / two_pi) % 1.0
                has = cnt > 0
                new[has, k] = coord[has]
            seeds = new
        return seeds
