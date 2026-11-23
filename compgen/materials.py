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

# The two (mutually exclusive) ways to specify isotropic elastic constants. MOOSE templates
# always take the engineering constants, so Lame parameters are converted before use.
ENGINEERING = ("youngs_modulus", "poissons_ratio")
LAME = ("lame_lambda", "lame_mu")


def check_elastic_parameters(names):
    """Check that a set of property names specifies elastic constants consistently.

    A material may give either ``youngs_modulus``/``poissons_ratio`` or
    ``lame_lambda``/``lame_mu``, but not a mix of the two. Lame parameters must be given as a
    pair. Materials with neither (e.g. thermal-only) are accepted.

    Args:
        names (iterable): Property names of one material.
    """
    names = set(names)
    eng = names.intersection(ENGINEERING)
    lame = names.intersection(LAME)
    if eng and lame:
        raise ValueError(
            "Elastic constants must be given either as youngs_modulus/poissons_ratio or as "
            f"lame_lambda/lame_mu, not both (got {', '.join(sorted(eng | lame))})."
        )
    if lame and len(lame) != len(LAME):
        missing = set(LAME) - lame
        raise ValueError(
            f"Lame parameters must be given as a pair; missing {', '.join(sorted(missing))}."
        )


def lame_to_engineering(lam, mu):
    """Convert Lame parameters to Young's modulus and Poisson's ratio.

    Args:
        lam (float): Lame's first parameter, lambda.
        mu (float): Lame's second parameter (shear modulus), mu.

    Returns:
        tuple: ``(youngs_modulus, poissons_ratio)``.
    """
    if mu <= 0.0 or 3.0 * lam + 2.0 * mu <= 0.0:
        raise ValueError(
            "Lame parameters must give positive shear and bulk moduli (mu > 0 and "
            f"3 lambda + 2 mu > 0), got lame_lambda={lam}, lame_mu={mu}."
        )
    E = mu * (3.0 * lam + 2.0 * mu) / (lam + mu)
    nu = lam / (2.0 * (lam + mu))
    return E, nu


def resolve_elastic_constants(props):
    """Return material properties with Young's modulus and Poisson's ratio available.

    If ``props`` gives Lame parameters, return a copy with ``youngs_modulus`` and
    ``poissons_ratio`` added (the Lame entries are kept). Otherwise return ``props`` as is.

    Args:
        props (dict): Property values of one material.
    """
    check_elastic_parameters(props)
    if not all(k in props for k in LAME):
        return props
    E, nu = lame_to_engineering(props["lame_lambda"], props["lame_mu"])
    return {**props, "youngs_modulus": E, "poissons_ratio": nu}


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

    Isotropic elastic constants may be given either as ``youngs_modulus`` and
    ``poissons_ratio`` or as ``lame_lambda`` and ``lame_mu``, but not both.

    Args:
        props (dict): A dictionary of material properties.
    """

    def __init__(self, **props):
        check_elastic_parameters(props)
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

    Isotropic elastic constants may be given either as ``youngs_modulus`` and
    ``poissons_ratio`` or as ``lame_lambda`` and ``lame_mu`` (each sampled independently),
    but not both.

    Args:
        prop_ranges (dict): A dictionary where keys are property names and values are
            either (min, max) intervals or specification dictionaries as described above.
    """

    def __init__(self, **prop_ranges):
        check_elastic_parameters(prop_ranges)
        self.prop_ranges = {
            prop: _parse_spec(prop, spec) for prop, spec in prop_ranges.items()
        }

    def next(self):
        """Generate a random sample of material properties within the specified ranges."""
        return {prop: _sample(spec) for prop, spec in self.prop_ranges.items()}


def sample_contrast_pair(low, high, alpha=0.5):
    """Sample a pair of property values ``(p_A, p_B)`` with log-distributed contrast.

    Both values lie in ``[low, high]``. Working in log space, ``c = log(p_A / p_B)`` has
    ``|c|`` distributed with density proportional to ``(L - |c|)**alpha`` on ``[0, L]``,
    ``L = log(high / low)``, and a random sign. Given ``c``, ``log(p_B)`` is uniform over
    the range that keeps both values inside the interval.

    ``alpha = 0`` gives a log-uniform contrast (but concentrates the individual values
    toward the middle of the interval); ``alpha = 1`` makes ``(log p_A, log p_B)``
    uniform over the square (each value log-uniform, but large contrasts rare).

    Args:
        low (float): Lower bound of both values, > 0.
        high (float): Upper bound of both values, >= low.
        alpha (float): Shape exponent, > -1.

    Returns:
        tuple: ``(p_A, p_B)``; the contrast is ``p_A / p_B``.
    """
    lo, hi = math.log(low), math.log(high)
    L = hi - lo
    s = L * (1.0 - random.random() ** (1.0 / (alpha + 1.0)))
    c = s * random.choice((-1.0, 1.0))
    u2 = random.uniform(lo + max(0.0, -c), hi - max(0.0, c))
    u1 = u2 + c
    if L == 0.0:
        return low, low
    # Clamp to absorb exp(log(x)) round-off at the interval ends.
    return min(max(math.exp(u1), low), high), min(max(math.exp(u2), low), high)


ContrastSpec = namedtuple("ContrastSpec", ["low", "high", "alpha"])


def _parse_contrast_spec(prop, spec):
    """Normalize one contrast property specification into a ContrastSpec.

    A specification is either a plain ``[min, max]`` sequence (default ``alpha``) or a
    dictionary with a required ``interval`` key and an optional ``alpha`` key.
    """
    alpha = 0.5
    if isinstance(spec, dict):
        unknown = set(spec) - {"interval", "alpha"}
        if unknown:
            raise ValueError(
                f"Unknown key(s) {', '.join(repr(k) for k in sorted(unknown))} for "
                f"contrast property '{prop}'. Accepted keys are: 'alpha', 'interval'."
            )
        if "interval" not in spec:
            raise ValueError(
                f"Specification for contrast property '{prop}' is missing the required "
                f"'interval' key."
            )
        interval = spec["interval"]
        alpha = spec.get("alpha", alpha)
    else:
        interval = spec
    low, high = _parse_interval(prop, interval)
    if low <= 0.0:
        raise ValueError(
            f"Interval for contrast property '{prop}' must be strictly positive, "
            f"got [{low}, {high}]."
        )
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or alpha <= -1:
        raise ValueError(
            f"'alpha' for contrast property '{prop}' must be a number > -1, got {alpha!r}."
        )
    return ContrastSpec(low, high, float(alpha))


class ContrastMaterialGenerator(MaterialGenerator):
    """
    Jointly generate the properties of phases A and B, sampling property contrasts.

    Each ``contrast`` property is sampled for both phases at once with
    :func:`sample_contrast_pair`, so the contrast ``A / B`` covers many orders of magnitude
    while both values stay inside the given (physical) interval. A contrast property is a
    plain ``[min, max]`` sequence or a dictionary with a required ``interval`` and an
    optional ``alpha`` (default 0.5)::

        "contrast": {
            "youngs_modulus": {"interval": [1.0e3, 1.0e6], "alpha": 0.5},
            "density": [1.0, 10.0]
        }

    Further properties of each phase, sampled independently, go in ``A`` and ``B``. Each
    value is either a fixed number or a :class:`RandomMaterialGenerator` specification::

        "A": {"poissons_ratio": [0.2, 0.4]},
        "B": {"poissons_ratio": 0.3}

    Unlike the other generators this one yields ``(A, B)`` pairs of property dicts, so in a
    run configuration it goes under the ``materials`` key in place of ``material_A`` and
    ``material_B``.

    Keyword Args:
        contrast (dict): Properties sampled jointly for both phases.
        A (dict): Further properties of phase A.
        B (dict): Further properties of phase B.
    """

    def __init__(self, contrast=None, A=None, B=None):
        contrast = contrast or {}
        A = A or {}
        B = B or {}
        for phase, extra in (("A", A), ("B", B)):
            overlap = set(contrast) & set(extra)
            if overlap:
                raise ValueError(
                    f"Propert(y/ies) {', '.join(sorted(overlap))} given both as a contrast "
                    f"property and for phase {phase}."
                )
            check_elastic_parameters(set(contrast) | set(extra))
        self.contrast = {
            prop: _parse_contrast_spec(prop, spec) for prop, spec in contrast.items()
        }
        self.phases = [self._phase_generator(A), self._phase_generator(B)]

    @staticmethod
    def _phase_generator(props):
        """Split one phase's properties into fixed values and a random generator."""
        fixed = {
            k: v
            for k, v in props.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
        rand = RandomMaterialGenerator(
            **{k: v for k, v in props.items() if k not in fixed}
        )
        return fixed, rand

    def next(self):
        """Generate the next ``(A, B)`` pair of material property dicts."""
        a, b = ({**fixed, **rand.next()} for fixed, rand in self.phases)
        for prop, spec in self.contrast.items():
            a[prop], b[prop] = sample_contrast_pair(spec.low, spec.high, spec.alpha)
        return a, b
