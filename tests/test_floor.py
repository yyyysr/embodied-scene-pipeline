import copy
from types import SimpleNamespace

import numpy as np
import pytest

from embodied_scene.assembly import default_assembly
from embodied_scene.floor import estimate_floor


def room():
    rng = np.random.default_rng(12)
    floor = np.column_stack((rng.uniform(-2, 2, (8000, 2)), rng.normal(-0.85, .004, 8000)))
    table = np.column_stack((rng.uniform(-.5, .5, (12000, 2)), rng.normal(0, .003, 12000)))
    walls = rng.uniform([-2, -2, -.85], [2, 2, 2], (6000, 3))
    noise = rng.uniform([-2, -2, -20], [2, 2, -10], (20, 3))
    p = np.concatenate([floor, table, walls, noise])
    return SimpleNamespace(positions=p, opacities=np.ones(len(p)))


def test_floor_ignores_low_outliers_and_dense_table_and_is_repeatable():
    data = room()
    assembly = default_assembly()
    before = copy.deepcopy(assembly)
    result = estimate_floor(data, assembly)
    assert result['floor_z_m'] == pytest.approx(-.85, abs=.01)
    assert assembly == before
    assembly['background']['placement']['position_m'][2] += result['delta_z_m']
    assert estimate_floor(data, assembly)['delta_z_m'] == pytest.approx(0, abs=.001)


def test_floor_accounts_for_source_axes_units_placement_and_scale():
    data = room()
    # Reverse Rx(-90) to encode source Y-down.
    data.positions = data.positions[:, [0, 2, 1]] * [1, -1, 1]
    assembly = default_assembly()
    s = np.sqrt(.5)
    assembly['background']['source_to_world'] = {
        'orientation_xyzw': [-s, 0, 0, s], 'meters_per_source_unit': .5,
    }
    assembly['background']['placement'] = {
        'position_m': [2, 3, .2], 'orientation_xyzw': [0, 0, s, s], 'uniform_scale': 4,
    }
    assert estimate_floor(data, assembly)['floor_z_m'] == pytest.approx(-1.5, abs=.02)


def test_vertical_wall_is_not_a_floor():
    rng = np.random.default_rng(2)
    p = rng.uniform([-2, 0, -1], [2, 0, 2], (5000, 3))
    with pytest.raises(ValueError):
        estimate_floor(SimpleNamespace(positions=p, opacities=np.ones(len(p))), default_assembly())
