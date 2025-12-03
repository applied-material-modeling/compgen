import numpy as np
from numpy.fft import rfftn, irfftn
from scipy.ndimage import gaussian_filter


class SpectralGenerator:
    """Generate structures based on another image by calculating its spectrum

    Args:
        reference_image (np.ndarray): 2D binary array representing the reference structure.
        nx (int): Number of grid points in the x-direction.
        ny (int): Number of grid points in the y-direction.

    Keyword Args:
        seed (int): Seed for the random number generator. Defaults to None.
    """

    def __init__(self, reference_image, nx, ny, seed=None, iters=100):
        self.reference_image = reference_image
        self.nx = nx
        self.ny = ny
        self.rng = np.random.default_rng(seed)
        self.iters = iters
        self.target_spectrum = self.compute_spectrum(reference_image)
        self.vf = np.mean(reference_image)

    def compute_spectrum(self, image):
        """Compute the spectrum of the given image.

        Args:
            image (np.ndarray): 2D binary array.

        Returns:
            np.ndarray: image spectrum
        """
        # Generate the spectrum
        f = image.astype(float) - np.mean(image)
        spec = np.abs(rfftn(f))

        # Resample to the right size
        old_nx, old_nyh = spec.shape
        new_nyh = self.ny // 2 + 1

        resampled_spec = np.zeros((self.nx, new_nyh))

        nx_min = min(old_nx, self.nx)
        nyh_min = min(old_nyh, new_nyh)

        resampled_spec[:nx_min, :nyh_min] = spec[:nx_min, :nyh_min]

        if self.nx < old_nx or new_nyh < old_nyh:
            sx = max(old_nx / self.nx, 1.0)
            sy = max(old_nyh / new_nyh, 1.0)
            sigma = (sx / 8.0, sy / 8.0)
            resampled_spec = gaussian_filter(resampled_spec, sigma=sigma)

        return resampled_spec

    def sample(self, spectrum):
        """
        Sample the spectrum and binary constraint
        """
        field = self.rng.normal(size=(self.nx, self.ny))

        for _ in range(self.iters):
            F = rfftn(field)
            phase = F / np.maximum(np.abs(F), 1e-12)
            F_new = phase * spectrum

            field = irfftn(F_new, s=(self.nx, self.ny))
            # Enforce binary constraint
            field = (field > self.vf).astype(float)

        return field.astype(bool)

    def next(self):
        """Generate a new structure matching the target 2-point correlation.

        Returns:
            np.ndarray: A 2D array of shape (nx, ny) with random bool values.
        """
        return self.sample(self.target_spectrum)

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()


class RandomGenerator:
    """Generate random structures of a given shape.

    Args:
        nx (int): Number of grid points in the x-direction.
        ny (int): Number of grid points in the y-direction.

    Keyword Args:
        seed (int): Seed for the random number generator. Defaults to None.

    """

    def __init__(self, nx, ny, seed=None):
        self.nx = nx
        self.ny = ny
        self.rng = np.random.default_rng(seed)

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
        vf = self.rng.uniform(0, 1.0)
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
