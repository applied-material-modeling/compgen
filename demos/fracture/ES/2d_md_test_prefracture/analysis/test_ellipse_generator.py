import sys
from pathlib import Path

import numpy as np
import pytest

REPO_DIR = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO_DIR))

from compgen.gen import EllipseGenerator
from compgen.racoon import inject_prefracture, prefracture_endpoints


def test_material_b_inclusion_preserves_material_a_vf_semantics():
    kwargs = dict(
        N=[64, 64],
        min_size=4,
        max_size=8,
        remove_edge_ellipses=False,
        random_seed=42,
    )
    phase_a_inclusions = EllipseGenerator(
        **kwargs, vf=0.2, inclusion_material="A"
    ).sample()
    phase_b_inclusions = EllipseGenerator(
        **kwargs, vf=0.8, inclusion_material="B"
    ).sample()

    assert np.array_equal(phase_b_inclusions, ~phase_a_inclusions)
    assert np.isclose(phase_a_inclusions.mean(), 0.2, atol=0.05)
    assert np.isclose(phase_b_inclusions.mean(), 0.8, atol=0.05)


def test_ellipse_generator_rejects_unknown_inclusion_material():
    with pytest.raises(ValueError, match="inclusion_material"):
        EllipseGenerator(
            N=[16, 16],
            vf=0.2,
            min_size=2,
            max_size=4,
            inclusion_material="C",
        )


def test_prefracture_mask_enters_from_left_by_configured_fraction():
    generator = EllipseGenerator(
        N=[100, 80],
        vf=0.8,
        min_size=6,
        max_size=10,
        prefracture_length_fraction=0.35,
        prefracture_y_fraction=0.5,
        prefracture_width=8,
        random_seed=42,
    )

    mask = generator.prefracture_mask()
    assert mask[:35].any()
    assert not mask[35:].any()
    assert mask[:, 36:44].sum() > 0
    assert mask[:, :36].sum() == 0
    assert mask[:, 44:].sum() == 0


def test_ellipses_do_not_touch_prefracture_corridor():
    generator = EllipseGenerator(
        N=[96, 96],
        vf=0.8,
        min_size=5,
        max_size=10,
        remove_edge_ellipses=False,
        remove_overlapping_ellipses=True,
        prefracture_length_fraction=0.4,
        prefracture_y_fraction=0.5,
        prefracture_width=10,
        inclusion_material="B",
        random_seed=7,
    )

    structure = generator.sample()
    corridor = generator.prefracture_mask()
    # With B as the inclusion phase, True is the matrix phase reserved by the
    # corridor; no B ellipse may occupy any protected pixel.
    assert np.all(structure[corridor])


def test_prefracture_injector_writes_configured_segment(tmp_path):
    fracture_file = tmp_path / "fracture.i"
    fracture_file.write_text(
        "      x1 = '0'\n"
        "      y1 = '0'\n"
        "      x2 = '0'\n"
        "      y2 = '0'\n"
        "      z1 = '0'\n"
        "      z2 = '0'\n"
    )

    inject_prefracture(
        fracture_file,
        prefracture_endpoints(
            {"length_fraction": 0.4, "y_fraction": 0.5}, [2.0, 4.0]
        ),
    )

    text = fracture_file.read_text()
    assert "x1 = '0.0'" in text
    assert "y1 = '2.0'" in text
    assert "x2 = '0.8'" in text
    assert "y2 = '2.0'" in text


def test_prefracture_endpoints_validate_and_scale_to_domain():
    assert prefracture_endpoints(
        {"length_fraction": 0.4, "y_fraction": 0.5}, [2.0, 4.0]
    ) == {"x1": 0.0, "y1": 2.0, "x2": 0.8, "y2": 2.0}
    with pytest.raises(ValueError, match="length_fraction"):
        prefracture_endpoints({"length_fraction": 1.1, "y_fraction": 0.5}, [1, 1])