"""Conservative horizontal-floor estimate for a manually oriented SPZ background."""

import numpy as np

from embodied_scene.assembly import validate_assembly


def _rotate(points, xyzw):
    xyz = np.asarray(xyzw[:3])
    cross = 2 * np.cross(xyz, points)
    return points + xyzw[3] * cross + np.cross(xyz, cross)


def estimate_floor(data, assembly):
    """Return a world-Z shift, never mutate assembly or infer source axes.

    Search low horizontal density bands with broad two-dimensional support.
    This is a geometric suggestion, not semantic recognition of a floor.
    """
    validate_assembly(assembly)
    bg = assembly['background']
    source, placement = bg['source_to_world'], bg['placement']
    points = np.asarray(data.positions, dtype=float)
    opacity = np.asarray(data.opacities)
    valid = np.isfinite(points).all(axis=1) & np.isfinite(opacity) & (opacity >= 0)
    points = points[valid]
    if len(points) < 200:
        raise ValueError('有效高斯点不足，无法估算地面。')
    # Deterministic bounded sample; opacity is stored as a logit (0 = alpha 0.5).
    if len(points) > 200000:
        points = points[np.random.default_rng(0).choice(len(points), 200000, replace=False)]
    points = _rotate(points, source['orientation_xyzw']) * source['meters_per_source_unit']
    points = _rotate(points, placement['orientation_xyzw']) * placement['uniform_scale']
    points += placement['position_m']
    lower, upper = np.percentile(points, [1, 99], axis=0)
    span = upper - lower
    if (span[:2] <= 0).any() or span[2] <= 0:
        raise ValueError('背景范围不足，无法估算地面。')
    tolerance = max(span[2] * 0.015, 0.005)
    counts, edges = np.histogram(points[:, 2], bins=100, range=(lower[2], upper[2]))
    # Only inspect the bottom 35% of the robust height range.
    candidates = sorted(range(35), key=lambda i: counts[i], reverse=True)[:8]
    floors = []
    for i in candidates:
        height = (edges[i] + edges[i + 1]) / 2
        band = points[np.abs(points[:, 2] - height) <= tolerance]
        if len(band) < max(100, len(points) * 0.015):
            continue
        xy_span = np.diff(np.percentile(band[:, :2], [5, 95], axis=0), axis=0)[0]
        if (xy_span < span[:2] * 0.25).any():
            continue
        cells = np.floor((band[:, :2] - lower[:2]) / span[:2] * 16).astype(int)
        cells = cells[((cells >= 0) & (cells < 16)).all(axis=1)]
        coverage = len(np.unique(cells, axis=0)) / 256
        if coverage < 0.15:
            continue
        centered = band - np.median(band, axis=0)
        singular = np.linalg.svd(centered[:, :2], compute_uv=False)
        if singular[1] < singular[0] * 0.15:
            continue
        slopes = np.linalg.lstsq(
            np.column_stack((centered[:, :2], np.ones(len(band)))), centered[:, 2], rcond=None
        )[0][:2]
        if np.linalg.norm(slopes) > 0.08:
            continue
        floors.append((float(np.median(band[:, 2])), len(band), coverage))
    if not floors:
        raise ValueError('未找到可信的低位水平面；请确认源轴向，或手动调整位置 Z。')
    height, count, coverage = min(floors)
    return {
        'floor_z_m': height, 'delta_z_m': -height,
        'support_points': count, 'coverage': round(coverage, 3),
        'method': 'low_horizontal_density_band',
        'warning': '几何估计，可能是低位平台；请检查画面并保存。少量噪点仍可能低于网格。',
    }
