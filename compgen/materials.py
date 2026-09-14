import math
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


class DistributionMaterialGenerator(MaterialGenerator):
    """Sample material properties from per-property distributions.

    Each keyword argument maps a property name to a specification, one of:

    - ``[min, max]`` (list/tuple): sample uniformly in ``[min, max]``. This is a
      backward-compatible shorthand matching ``RandomMaterialGenerator``.
    - ``{"dist": "uniform", "range": [min, max]}``: sample uniformly.
    - ``{"dist": "loguniform", "range": [min, max]}``: sample log-uniformly, i.e.
      uniform in ``log`` space so every decade is covered evenly. ``min`` and
      ``max`` must be strictly positive. Use this for quantities that span many
      orders of magnitude across materials (fracture energies, strengths).
    - ``{"fixed": value}``: return ``value`` on every draw. Use for parameters
      that must stay constant across the sweep (e.g. the shared phase-field
      length ``l``, which must remain resolved by the mesh).

    Args:
        prop_specs: Mapping of property name to a specification as above.
    """

    def __init__(self, **prop_specs):
        self.prop_specs = prop_specs

    def next(self):
        return {prop: self._sample(spec) for prop, spec in self.prop_specs.items()}

    @staticmethod
    def _sample(spec):
        if isinstance(spec, dict):
            if "fixed" in spec:
                return spec["fixed"]
            lo, hi = spec["range"]
            if spec.get("dist", "uniform") == "loguniform":
                if lo <= 0 or hi <= 0:
                    raise ValueError(
                        "loguniform range must be strictly positive, got "
                        f"[{lo}, {hi}]"
                    )
                return math.exp(random.uniform(math.log(lo), math.log(hi)))
            return random.uniform(lo, hi)
        # list/tuple shorthand -> uniform
        return random.uniform(*spec)
