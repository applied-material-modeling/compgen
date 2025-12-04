import numpy as np
from skimage.transform import resize
import gstools as gs
from scipy.optimize import curve_fit


def make_orthogonal(img):
    """Mirror and tile the input image to give it orthogonal periodicity."""
    img_h = np.hstack([img, np.flip(img, axis=1)])
    img_v = np.vstack([img_h, np.flip(img_h, axis=0)])
    return img_v


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
        cov = np.interp(h, self.r, self.c, left=self.c[0], right=self.c[-1])
        return cov


class TwoPointGenerator:
    """Generate structures based on two point correlations.

    Args:
        reference_image (np.ndarray): 2D binary array representing the reference structure.
        nx (int): Number of grid points in the x-direction.
        ny (int): Number of grid points in the y-direction.
    """

    def __init__(
        self, reference_image, nx, ny, random_seed=None, l_guess=5.0, radial_mask=None
    ):
        self.nx = nx
        self.ny = ny
        self.rng = np.random.default_rng(random_seed)
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

    def next(self):
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

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()


class SpinodalGenerator:
    """Generate structures based on spinodal decomposition.

    Args:
        nx (int): Number of grid points in the x-direction.
        ny (int): Number of grid points in the y-direction.
        vf (float): Volume fraction of phase A.
        l (float): Characteristic length scale.
        bandwidth (float): Bandwidth of the spinodal structure.

    Keyword Args:
        seed (int): Seed for the random number generator. Defaults to None.
    """

    def __init__(self, nx, ny, vf, l, bandwidth, seed=None):
        self.nx = nx
        self.ny = ny
        self.vf = vf
        self.l = l
        self.bandwidth = bandwidth
        self.rng = np.random.default_rng(seed)

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        """Generate the next structure via spinodal decomposition.

        Returns:
            np.ndarray: A 2D array of shape (nx, ny) with random bool values.
        """
        kx = 2.0 * np.pi * np.fft.fftfreq(self.nx)
        ky = 2.0 * np.pi * np.fft.fftfreq(self.ny)
        KX, KY = np.meshgrid(kx, ky, indexing="ij")
        K_mag = np.sqrt(KX**2 + KY**2)

        k0 = 2.0 * np.pi / self.l

        sigma_k = self.bandwidth * k0

        assert sigma_k > 0.0
        amplitude_spectrum = np.exp(-0.5 * ((K_mag - k0) / sigma_k) ** 2)
        amplitude_spectrum[K_mag == 0] = 0.0

        g = self.rng.normal(size=(self.nx, self.ny))
        g_hat = np.fft.fftn(g)

        amp_filter = np.sqrt(amplitude_spectrum)
        h_hat = g_hat * amp_filter

        h = np.fft.ifftn(h_hat).real
        h = (h - np.mean(h)) / np.std(h)

        T = np.quantile(h, 1 - self.vf)
        img = h > T

        return img


class RandomGenerator:
    """Generate random structures of a given shape.

    Args:
        nx (int): Number of grid points in the x-direction.
        ny (int): Number of grid points in the y-direction.

    Keyword Args:
        seed (int): Seed for the random number generator. Defaults to None.
        min_vf (float): Minimum volume fraction of phase A. Defaults to 0.
        max_vf (float): Maximum volume fraction of phase A. Defaults to 1.
    """

    def __init__(self, nx, ny, seed=None, min_vf=0, max_vf=1.0):
        self.nx = nx
        self.ny = ny
        self.rng = np.random.default_rng(seed)
        self.min_vf = min_vf
        self.max_vf = max_vf

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        """Generate the next random structure via hierarchical sampling.

        Returns:
            np.ndarray: A 2D array of shape (nx, ny) with random bool values.
        """
        # First select the volume fraction of phase A
        vf = self.rng.uniform(self.min_vf, self.max_vf)
        nf = int(self.nx * self.ny * vf)
        # Then sample a hierarchical random structure
        inds = self.rng.choice(list(range(self.nx * self.ny)), size=nf, replace=False)
        img = np.zeros((self.nx * self.ny,), dtype=bool)
        img[inds] = True
        return img.reshape((self.nx, self.ny))


class Rectangle:
    """Represents a 2D rectangular region.

    Args:
        xmin (float): Minimum x-coordinate.
        xmax (float): Maximum x-coordinate.
        ymin (float): Minimum y-coordinate.
        ymax (float): Maximum y-coordinate.
    """

    def __init__(self, xmin, xmax, ymin, ymax):
        self.xmin = xmin
        self.xmax = xmax
        self.ymin = ymin
        self.ymax = ymax

    def __call__(self, x, y):
        """Return true where (x, y) points are inside the rectangle.
        Args:
            x (array): x-coordinates of points.
            y (array): y-coordinates of points.
        """
        return np.logical_and(
            np.logical_and(x >= self.xmin, x <= self.xmax),
            np.logical_and(y >= self.ymin, y <= self.ymax),
        )


class Rotate:
    """Transform an object by rotating it around a given point.

    Args:
        shape (callable): The shape to be rotated.
        angle (float): Rotation angle in radians.
        origin (tuple): (x, y) coordinates of the rotation center.
    """

    def __init__(self, shape, angle, origin=np.array([0.0, 0.0])):
        self.shape = shape
        self.angle = angle
        self.origin = origin
        self.cos_angle = np.cos(angle)
        self.sin_angle = np.sin(angle)

    def __call__(self, x, y):
        """Return true where (x, y) points are inside the rotated shape.
        Args:
            x (array): x-coordinates of points.
            y (array): y-coordinates of points.
        """
        x_shifted = x - self.origin[0]
        y_shifted = y - self.origin[1]
        x_rotated = (
            x_shifted * self.cos_angle - y_shifted * self.sin_angle
        ) + self.origin[0]
        y_rotated = (
            x_shifted * self.sin_angle + y_shifted * self.cos_angle
        ) + self.origin[1]
        return self.shape(x_rotated, y_rotated)


def generate_from_objects(objects, lx, ly, nx, ny):
    """Generate a 2D mesh from a list of shape objects.

    Args:
        objects (list): List of shape objects defining material A.
        lx (float): Length of the domain in x-direction.
        ly (float): Length of the domain in y-direction.
        nx (int): Number of elements in x-direction.
        ny (int): Number of elements in y-direction.

    Returns:
        img (2D array): Binary image where 1 indicates material A.
    """
    x_vals = np.linspace(0, lx, nx)
    y_vals = np.linspace(0, ly, ny)
    X, Y = np.meshgrid(x_vals, y_vals, indexing="ij")
    img = np.zeros((ny, nx), dtype=bool)

    for obj in objects:
        img[obj(X, Y)] = 1

    return img
