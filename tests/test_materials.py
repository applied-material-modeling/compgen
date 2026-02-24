from compgen.materials import FixedMaterialGenerator, RandomMaterialGenerator


def test_fixed_material_generator_returns_same_values_each_time():
    gen = FixedMaterialGenerator(thermal_conductivity=12.5, youngs_modulus=210.0)

    first = gen.next()
    second = gen.next()

    assert first == {"thermal_conductivity": 12.5, "youngs_modulus": 210.0}
    assert second == {"thermal_conductivity": 12.5, "youngs_modulus": 210.0}


def test_fixed_material_generator_iterator_protocol_returns_fixed_values():
    gen = FixedMaterialGenerator(alpha=1.2, beta=3.4)

    value = next(gen)

    assert value == {"alpha": 1.2, "beta": 3.4}


def test_random_material_generator_values_stay_within_ranges():
    ranges = {
        "thermal_conductivity": (5.0, 20.0),
        "youngs_modulus": (100.0, 250.0),
        "poisson_ratio": (0.2, 0.4),
    }
    gen = RandomMaterialGenerator(**ranges)

    for _ in range(500):
        sample = gen.next()
        assert set(sample.keys()) == set(ranges.keys())
        for prop, (min_value, max_value) in ranges.items():
            assert min_value <= sample[prop] <= max_value
