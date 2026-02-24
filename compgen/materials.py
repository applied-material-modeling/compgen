import random


class MaterialGenerator:
    """
    Base class for material generators.
    """

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        raise NotImplementedError("Subclasses must implement the next() method.")


class FixedMaterialGenerator(MaterialGenerator):
    """
    Just return a fixed dictionary of material properties.

    Args:
        props (dict): A dictionary of material properties.
    """

    def __init__(self, **props):
        self.props = props

    def next(self):
        return self.props


class RandomMaterialGenerator(MaterialGenerator):
    """
    Generate random material properties.

    Args:
        prop_ranges (dict): A dictionary where keys are property names and values are tuples of (min, max) ranges.
    """

    def __init__(self, **prop_ranges):
        self.prop_ranges = prop_ranges

    def next(self):
        return {
            prop: random.uniform(*range_) for prop, range_ in self.prop_ranges.items()
        }
