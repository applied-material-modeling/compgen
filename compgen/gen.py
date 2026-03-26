"""Methods for generating random composite structures."""

from pathlib import Path
import importlib

import numpy as np
from skimage.transform import resize
import gstools as gs
from scipy.optimize import curve_fit


def make_orthogonal(img):
    """Mirror and tile the input array to give it orthogonal periodicity.

    This works for arrays of arbitrary dimensionality by concatenating the
    array with its flipped version along each axis (processing axes from
    last to first).
    """
    arr = np.asarray(img)
    for axis in reversed(range(arr.ndim)):
        arr = np.concatenate([arr, np.flip(arr, axis=axis)], axis=axis)
    return arr


def make_periodic(img: np.ndarray, margin: int = 2) -> np.ndarray:
    """
    Make periodic for Sculpt/MOOSE workflow.

    Overwrite the first and last `margin` layers of each axis with the layer at
    index `margin`, for 2D or 3D arrays.

    A value `margin` = 2 seems to work consistently with Sculpt/MOOSE.
    """
    arr = np.asarray(img)
    arr = arr.squeeze()

    if arr.ndim not in (2, 3):
        raise RuntimeError(f"Expected 2D or 3D array, got {arr.ndim}D")

    if not isinstance(margin, int) or margin < 1:
        raise ValueError(f"margin must be a positive integer, got {margin}")

    if any(2 * margin >= s for s in arr.shape):
        raise ValueError(f"margin={margin} is too large for shape {arr.shape}")

    # Loop over each axis
    for ax in range(arr.ndim):
        # Slice selecting the master layer at index = margin
        master = [slice(None)] * arr.ndim
        master[ax] = slice(margin, margin + 1)

        # Slice for lower and upper boundary block
        lo = [slice(None)] * arr.ndim
        lo[ax] = slice(0, margin)
        hi = [slice(None)] * arr.ndim
        hi[ax] = slice(-margin, None)

        # Overwrite both boundary blocks using the master layer
        arr[tuple(lo)] = arr[tuple(master)]
        arr[tuple(hi)] = arr[tuple(master)]

    return arr


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
        # Generator printout for clarity
        print(f"{self.__class__.__name__} called")
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
        self.reference_image = self.standardize_image(reference_image)
        self.acov, self.mean, self.var = self.image_statistics(self.reference_image)
        self.r, self.c = self.radial_average_variogram(self.acov)

        self.model = self.fit_model(self.r, self.c, radial_mask=radial_mask)
        self.generator = gs.SRF(self.model)

    def standardize_image(self, image):
        """Standardize the reference image to the desired size.

        Args:
            image (np.ndarray): 2D binary array.

        Returns:
            np.ndarray: Standardized 2D binary array.
        """
        img_resized = resize(
            image.astype(float),
            (self.nx, self.ny),
            order=1,
            mode="reflect",
            anti_aliasing=True,
        )
        img_binary = img_resized > 0.5
        return img_binary.astype(bool)

    def image_statistics(self, image):
        """Calculate the empirical coveriance, mean, and variance of the image.

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
        h = (h - np.mean(h)) / np.std(h)

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

    def __init__(self, filename, random_seed=None):
        super().__init__(random_seed=random_seed)
        self.data = np.load(filename)
        self.index = 0
        self.total = self.data.shape[0]

    def sample(self):
        """Generate the next structure from the loaded data.

        Returns:
            np.ndarray: An array of shape corresponding to the loaded structures.
        """
        if self.index >= self.total:
            self.index = 0  # Reset to the beginning if we reach the end
        generated = self.data[self.index]
        self.index += 1
        return generated


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
                raise ValueError(
                    f"Target '{f}' must be 2D after squeeze, got shape {arr.shape}"
                )
            arr_bin = self._binarize_image(arr, int)
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
            self.descriptor_types = ["Correlations"]
            self.descriptor_weights = [1.0]
        else:
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
        self._make_descriptor = lambda: self._build_descriptor_dict()

    @staticmethod
    def _binarize_image(image, dtype=bool):
        bin_img = np.asarray(image, dtype=float) > 0.5
        return bin_img.astype(dtype)

    def _array_to_microstructure(self, arr):
        ms = self.mcrpy.Microstructure(
            arr,
            use_multiphase=False,
        )
        return ms

    def _build_descriptor_dict(self):
        """Build a single descriptor dictionary consumable by MCRpy."""
        descs = [
            self.mcrpy.characterize(ms, self.char_settings) for ms in self.targets_ms
        ]

        # If there is only one target, no averaging is needed.
        if len(descs) == 1:
            return descs[0]

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

        # Control first guess for reproducibility
        first_guess = self.rng.random(self.target_shape) < self.target_vf

        generated = self.reconstruct(first_guess)

        # Resize generated image to desired shape
        if generated.shape != (self.nx, self.ny):
            generated = resize(
                np.asarray(generated, dtype=float),
                (self.nx, self.ny),
                order=1,
                mode="reflect",
                anti_aliasing=True,
                preserve_range=True,
            )

        generated = self._binarize_image(generated, bool)
        return generated
