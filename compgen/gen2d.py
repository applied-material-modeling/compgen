import numpy as np


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
    X, Y = np.meshgrid(x_vals, y_vals)
    img = np.zeros((ny, nx), dtype=bool)

    for obj in objects:
        img[obj(X, Y)] = 1

    return img
