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

"""Material property generators for fixed and randomized simulation inputs."""

import math
import random
from collections import namedtuple

UNIFORM = "uniform"
LOGUNIFORM = "loguniform"

# Accepted spellings of each distribution name, mapped to the canonical name.
DISTRIBUTIONS = {
    UNIFORM: UNIFORM,
    LOGUNIFORM: LOGUNIFORM,
    "log-uniform": LOGUNIFORM,
    "log_uniform": LOGUNIFORM,
}

PropertySpec = namedtuple("PropertySpec", ["low", "high", "distribution"])


def _parse_interval(prop, interval):
    """Validate and unpack an ``[min, max]`` interval.

    Args:
        prop (str): Property name, used in error messages.
        interval: The value to validate.

    Returns:
        tuple: The (min, max) pair as floats.
    """
    if isinstance(interval, (list, tuple)):
        if len(interval) != 2:
            raise ValueError(
                f"Interval for property '{prop}' must have exactly 2 entries, "
                f"got {len(interval)}."
            )
        if all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in interval
        ):
            low, high = float(interval[0]), float(interval[1])
            if low > high:
                raise ValueError(
                    f"Interval for property '{prop}' must satisfy min <= max, "
                    f"got [{low}, {high}]."
                )
            return low, high

    raise ValueError(
        f"Interval for property '{prop}' must be a list of two numbers, "
        f"got {interval!r}."
    )


def _parse_distribution(prop, distribution):
    """Resolve a distribution name to its canonical form.

    Args:
        prop (str): Property name, used in error messages.
        distribution (str): The requested distribution name.

    Returns:
        str: The canonical distribution name.
    """
    if distribution not in DISTRIBUTIONS:
        accepted = ", ".join(sorted(DISTRIBUTIONS))
        raise ValueError(
            f"Unknown distribution {distribution!r} for property '{prop}'. "
            f"Accepted values are: {accepted}."
        )
    return DISTRIBUTIONS[distribution]


def _parse_spec(prop, spec):
    """Normalize one property specification into a PropertySpec.

    A specification is either a plain ``[min, max]`` sequence, sampled uniformly, or a
    dictionary with a required ``interval`` key and an optional ``distribution`` key.

    Args:
        prop (str): Property name, used in error messages.
        spec: The specification to normalize.

    Returns:
        PropertySpec: The validated (low, high, distribution) triple.
    """
    if isinstance(spec, dict):
        unknown = set(spec) - {"interval", "distribution"}
        if unknown:
            raise ValueError(
                f"Unknown key(s) {', '.join(repr(k) for k in sorted(unknown))} for "
                f"property '{prop}'. Accepted keys are: 'distribution', 'interval'."
            )
        if "interval" not in spec:
            raise ValueError(
                f"Specification for property '{prop}' is missing the required "
                f"'interval' key."
            )
        interval = spec["interval"]
        distribution = _parse_distribution(prop, spec.get("distribution", UNIFORM))
    elif isinstance(spec, (list, tuple)):
        interval = spec
        distribution = UNIFORM
    else:
        raise ValueError(
            f"Specification for property '{prop}' must be a list of two numbers or a "
            f"dict with an 'interval' key, got {spec!r}."
        )

    low, high = _parse_interval(prop, interval)

    if distribution == LOGUNIFORM and low <= 0.0:
        raise ValueError(
            f"Interval for property '{prop}' must be strictly positive to use the "
            f"'{LOGUNIFORM}' distribution, got [{low}, {high}]."
        )

    return PropertySpec(low, high, distribution)


def _sample(spec):
    """Draw a single value from the distribution described by a PropertySpec.

    Args:
        spec (PropertySpec): The property specification to sample.

    Returns:
        float: The sampled value.
    """
    # Always consume exactly one draw, as main did for every property, so the
    # random stream (and every later property) is unchanged by a degenerate range.
    if spec.distribution == LOGUNIFORM:
        value = math.exp(random.uniform(math.log(spec.low), math.log(spec.high)))
    else:
        value = random.uniform(spec.low, spec.high)

    if spec.low == spec.high:
        # Return the bound exactly rather than an exp(log(x)) round-trip that can
        # land one ulp away.
        return spec.low
    return value


class MaterialGenerator:
    """
    Base class for material generators.
    """

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        """Generate the next set of material properties."""
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
        """Simply return the fixed properties."""
        return self.props


class RandomMaterialGenerator(MaterialGenerator):
    """
    Generate random material properties.

    Each property is sampled independently from its own interval, using its own
    distribution. A property is specified either as a plain ``[min, max]`` sequence,
    which is sampled uniformly, or as a dictionary with a required ``interval`` key and
    an optional ``distribution`` key. These four forms are all valid, and the first three
    are equivalent::

        "conductivity": [1.0, 50.0]
        "conductivity": {"interval": [1.0, 50.0]}
        "conductivity": {"interval": [1.0, 50.0], "distribution": "uniform"}
        "conductivity": {"interval": [1.0, 50.0], "distribution": "loguniform"}

    Both forms may be mixed within one generator.

    The available distributions are ``uniform`` (the default) and ``loguniform``, which
    requires a strictly positive interval.

    Args:
        prop_ranges (dict): A dictionary where keys are property names and values are
            either (min, max) intervals or specification dictionaries as described above.
    """

    def __init__(self, **prop_ranges):
        self.prop_ranges = {
            prop: _parse_spec(prop, spec) for prop, spec in prop_ranges.items()
        }

    def next(self):
        """Generate a random sample of material properties within the specified ranges."""
        return {prop: _sample(spec) for prop, spec in self.prop_ranges.items()}
