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

import importlib
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

# The (mutually exclusive) ways to specify isotropic elastic constants. MOOSE templates
# always take the engineering constants, so the other pairs are converted before use.
ENGINEERING = ("youngs_modulus", "poissons_ratio")
LAME = ("lame_lambda", "lame_mu")
BULK_SHEAR = ("bulk_modulus", "shear_modulus")
ELASTIC_PAIRS = (ENGINEERING, LAME, BULK_SHEAR)


def check_elastic_parameters(names):
    """Check that a set of property names specifies elastic constants consistently.

    A material may give exactly one of the pairs ``youngs_modulus``/``poissons_ratio``,
    ``lame_lambda``/``lame_mu`` or ``bulk_modulus``/``shear_modulus``, never a mix. The
    Lame and bulk/shear pairs must be given complete. Materials with none of these (e.g.
    thermal-only) are accepted.

    Args:
        names (iterable): Property names of one material.
    """
    names = set(names)
    used = [pair for pair in ELASTIC_PAIRS if names.intersection(pair)]
    if len(used) > 1:
        given = sorted(names.intersection(sum(used, ())))
        options = " or ".join("/".join(pair) for pair in ELASTIC_PAIRS)
        raise ValueError(
            f"Elastic constants must be given as only one of {options} "
            f"(got {', '.join(given)})."
        )
    for pair in (LAME, BULK_SHEAR):
        present = names.intersection(pair)
        if present and len(present) != len(pair):
            missing = set(pair) - present
            raise ValueError(
                f"Elastic constants {'/'.join(pair)} must be given as a pair; missing "
                f"{', '.join(sorted(missing))}."
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


def bulk_shear_to_engineering(K, G):
    """Convert bulk and shear moduli to Young's modulus and Poisson's ratio.

    Args:
        K (float): Bulk modulus.
        G (float): Shear modulus.

    Returns:
        tuple: ``(youngs_modulus, poissons_ratio)``.
    """
    if K <= 0.0 or G <= 0.0:
        raise ValueError(
            "Bulk and shear moduli must be positive, got "
            f"bulk_modulus={K}, shear_modulus={G}."
        )
    E = 9.0 * K * G / (3.0 * K + G)
    nu = (3.0 * K - 2.0 * G) / (2.0 * (3.0 * K + G))
    return E, nu


_CONVERSIONS = ((LAME, lame_to_engineering), (BULK_SHEAR, bulk_shear_to_engineering))


def resolve_elastic_constants(props):
    """Return material properties with Young's modulus and Poisson's ratio available.

    If ``props`` gives Lame parameters or bulk/shear moduli, return a copy with
    ``youngs_modulus`` and ``poissons_ratio`` added (the given entries are kept).
    Otherwise return ``props`` as is.

    Args:
        props (dict): Property values of one material.
    """
    check_elastic_parameters(props)
    for pair, convert in _CONVERSIONS:
        if all(k in props for k in pair):
            E, nu = convert(*(props[k] for k in pair))
            return {**props, "youngs_modulus": E, "poissons_ratio": nu}
    return props


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

    Isotropic elastic constants may be given as ``youngs_modulus`` and
    ``poissons_ratio``, as ``lame_lambda`` and ``lame_mu``, or as ``bulk_modulus`` and
    ``shear_modulus`` (only one pair).

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

    Isotropic elastic constants may be given as ``youngs_modulus`` and
    ``poissons_ratio``, as ``lame_lambda`` and ``lame_mu``, or as ``bulk_modulus`` and
    ``shear_modulus`` (only one pair; each value sampled independently).

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


def sample_contrast_pair(low, high, alpha=0.5, max_contrast=None):
    """Sample a pair of property values ``(p_A, p_B)`` with log-distributed contrast.

    Both values lie in ``[low, high]``. Working in log space, ``c = log(p_A / p_B)`` has
    ``|c|`` distributed with density proportional to ``(L - |c|)**alpha`` on ``[0, L]``,
    ``L = log(high / low)``, and a random sign. Given ``c``, ``log(p_B)`` is uniform over
    the range that keeps both values inside the interval.

    ``alpha = 0`` gives a log-uniform contrast (but concentrates the individual values
    toward the middle of the interval); ``alpha = 1`` makes ``(log p_A, log p_B)``
    uniform over the square (each value log-uniform, but large contrasts rare).

    ``max_contrast`` truncates ``|c|`` to ``[0, log(max_contrast)]`` (so with ``alpha = 0``
    the contrast magnitude is log-uniform on ``[1, max_contrast]``). If the interval is
    too narrow for that contrast, the window narrows to the largest one that fits,
    ``high / low``.

    Args:
        low (float): Lower bound of both values, > 0.
        high (float): Upper bound of both values, >= low.
        alpha (float): Shape exponent, > -1.
        max_contrast (float): Largest contrast magnitude, >= 1. None means ``high / low``.

    Returns:
        tuple: ``(p_A, p_B)``; the contrast is ``p_A / p_B``.
    """
    lo, hi = math.log(low), math.log(high)
    L = hi - lo
    # Inverse CDF of |c| (density ~ (L - |c|)**alpha), truncated to [0, M].
    M = L if max_contrast is None else min(math.log(max_contrast), L)
    F_M = 1.0 - ((L - M) / L) ** (alpha + 1.0) if L > 0.0 else 1.0
    s = L * (1.0 - (1.0 - random.random() * F_M) ** (1.0 / (alpha + 1.0)))
    c = s * random.choice((-1.0, 1.0))
    u2 = random.uniform(lo + max(0.0, -c), hi - max(0.0, c))
    u1 = u2 + c
    if L == 0.0:
        return low, low
    # Clamp to absorb exp(log(x)) round-off at the interval ends.
    return min(max(math.exp(u1), low), high), min(max(math.exp(u2), low), high)


ContrastSpec = namedtuple("ContrastSpec", ["low", "high", "alpha", "max_contrast"])


def _parse_contrast_spec(prop, spec):
    """Normalize one contrast property specification into a ContrastSpec.

    A specification is either a plain ``[min, max]`` sequence (default ``alpha``) or a
    dictionary with a required ``interval`` key and optional ``alpha`` and
    ``max_contrast`` keys.
    """
    alpha = 0.5
    max_contrast = None
    if isinstance(spec, dict):
        unknown = set(spec) - {"interval", "alpha", "max_contrast"}
        if unknown:
            raise ValueError(
                f"Unknown key(s) {', '.join(repr(k) for k in sorted(unknown))} for "
                f"contrast property '{prop}'. Accepted keys are: 'alpha', 'interval', "
                f"'max_contrast'."
            )
        if "interval" not in spec:
            raise ValueError(
                f"Specification for contrast property '{prop}' is missing the required "
                f"'interval' key."
            )
        interval = spec["interval"]
        alpha = spec.get("alpha", alpha)
        max_contrast = spec.get("max_contrast")
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
    if max_contrast is not None and (
        isinstance(max_contrast, bool)
        or not isinstance(max_contrast, (int, float))
        or max_contrast < 1.0
    ):
        raise ValueError(
            f"'max_contrast' for contrast property '{prop}' must be a number >= 1, "
            f"got {max_contrast!r}."
        )
    return ContrastSpec(
        low, high, float(alpha), None if max_contrast is None else float(max_contrast)
    )


class ContrastMaterialGenerator(MaterialGenerator):
    """
    Jointly generate the properties of phases A and B, sampling property contrasts.

    Each ``contrast`` property is sampled for both phases at once with
    :func:`sample_contrast_pair`, so the contrast ``A / B`` covers many orders of magnitude
    while both values stay inside the given (physical) interval. A contrast property is a
    plain ``[min, max]`` sequence or a dictionary with a required ``interval``, an
    optional ``alpha`` (default 0.5) and an optional ``max_contrast`` (default
    ``max / min``; narrowed to that when the interval cannot reach it)::

        "contrast": {
            "youngs_modulus": {"interval": [1.0e3, 1.0e6], "alpha": 0.5},
            "lame_mu": {"interval": [1.0e-3, 5.0e5], "alpha": 0.0, "max_contrast": 1.0e3},
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
            a[prop], b[prop] = sample_contrast_pair(
                spec.low, spec.high, spec.alpha, spec.max_contrast
            )
        return a, b


class FilteredMaterialGenerator(MaterialGenerator):
    """
    Wrap another material generator and reject samples outside given bounds.

    Each draw of the wrapped generator (a single property dict, or an ``(A, B)`` pair as
    from :class:`ContrastMaterialGenerator`) is accepted only if every phase passes all
    the bounds; otherwise the wrapped generator is drawn again. The accepted samples
    therefore follow the wrapped distribution conditioned on the bounds.

    Bounds apply to the resolved elastic constants, so ``poissons_ratio`` (and
    ``youngs_modulus``) can be bounded even when the wrapped generator samples bulk and
    shear moduli or Lame parameters. Any other property a phase carries can be bounded
    too. For example, to keep phases away from the nearly incompressible limit::

        "materials": {
            "type": "materials.FilteredMaterialGenerator",
            "params": {
                "generator": {"type": "materials.ContrastMaterialGenerator",
                              "params": {"contrast": {...}}},
                "bounds": {"poissons_ratio": [null, 0.45]}
            }
        }

    Keyword Args:
        generator (dict): ``type`` (``module.Class`` within compgen) and ``params`` of
            the wrapped generator.
        bounds (dict): Property name -> ``[min, max]``; either end may be ``None`` (JSON
            ``null``) for no bound. Both ends are inclusive.
        max_attempts (int): Draws allowed for one accepted sample before giving up with
            a ``RuntimeError`` (guards against bounds that can (almost) never be met).
    """

    def __init__(self, generator=None, bounds=None, max_attempts=10000):
        if not isinstance(generator, dict) or "type" not in generator:
            raise ValueError(
                "FilteredMaterialGenerator needs a 'generator' dictionary with a 'type'."
            )
        module_name, class_name = generator["type"].split(".")
        cls = getattr(importlib.import_module("compgen." + module_name), class_name)
        self.generator = cls(**generator.get("params", {}))

        self.bounds = {}
        for prop, bound in (bounds or {}).items():
            if not isinstance(bound, (list, tuple)) or len(bound) != 2:
                raise ValueError(
                    f"Bound for '{prop}' must be a [min, max] pair, got {bound!r}."
                )
            low = -math.inf if bound[0] is None else float(bound[0])
            high = math.inf if bound[1] is None else float(bound[1])
            if low > high:
                raise ValueError(f"Bound for '{prop}' has min > max: {bound!r}.")
            self.bounds[prop] = (low, high)
        if not self.bounds:
            raise ValueError("FilteredMaterialGenerator needs at least one bound.")

        if int(max_attempts) < 1:
            raise ValueError(f"max_attempts must be >= 1, got {max_attempts!r}.")
        self.max_attempts = int(max_attempts)
        self.attempts = 0  # total draws of the wrapped generator
        self.accepted = 0  # total accepted samples

    def accepts(self, props):
        """Whether one phase's property dict satisfies every bound."""
        resolved = resolve_elastic_constants(props)
        for prop, (low, high) in self.bounds.items():
            if prop not in resolved:
                raise KeyError(
                    f"Bounded property '{prop}' is not produced by the wrapped generator "
                    f"(it gives {sorted(resolved)})."
                )
            if not low <= resolved[prop] <= high:
                return False
        return True

    def next(self):
        """Draw from the wrapped generator until a sample passes all bounds."""
        for _ in range(self.max_attempts):
            sample = next(self.generator)
            self.attempts += 1
            phases = sample if isinstance(sample, tuple) else (sample,)
            if all(self.accepts(p) for p in phases):
                self.accepted += 1
                return sample
        raise RuntimeError(
            f"FilteredMaterialGenerator: no sample within bounds {self.bounds} after "
            f"{self.max_attempts} draws."
        )
