import numpy as np


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
