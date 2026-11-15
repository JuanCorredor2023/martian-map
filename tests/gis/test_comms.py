"""E11 radio line of sight (src/gis/comms.py) on small synthetic DEMs."""

import sys
from pathlib import Path

import numpy as np
import pytest
from osgeo import gdal

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from gis import comms  # noqa: E402

N = 200


def write_dem(tmp_path, z):
    """dem_1m.tif with origin (0, 0) top-left, 1 m cells, the team's Mars CRS."""
    path = tmp_path / "dem_1m.tif"
    ds = gdal.GetDriverByName("GTiff").Create(str(path), z.shape[1], z.shape[0], 1,
                                              gdal.GDT_Float32)
    ds.SetGeoTransform((0.0, 1.0, 0.0, 0.0, 0.0, -1.0))
    ds.SetProjection((REPO / "docs" / "contracts" / "crs.wkt").read_text(encoding="utf-8"))
    ds.GetRasterBand(1).WriteArray(z.astype(np.float32))
    ds = None
    comms.dem.cache_clear()
    comms._viewshed.cache_clear()
    return str(tmp_path)


@pytest.fixture
def wall_dem(tmp_path):
    """Flat ground with a 10 m wall across x = 100..102, from y = -150 to the bottom."""
    z = np.zeros((N, N))
    z[150:, 100:103] = 10.0
    return write_dem(tmp_path, z)


HAB = (50.5, -180.5)                    # west of the wall, in its band


def test_flat_ground_is_all_visible(tmp_path):
    base = write_dem(tmp_path, np.zeros((N, N)))
    assert comms.coverage(HAB, base) == 1.0


def test_wall_hides_the_cells_behind_it(wall_dem):
    vis = comms.line_of_sight(HAB, wall_dem)
    assert vis[180, 50] and vis[180, 90]          # same side of the wall
    assert not vis[180, 150]                      # behind the wall
    assert vis[50, 150]                           # north of the wall's end


def test_viewshed_matches_exact_profile(wall_dem):
    z, gt = comms.dem(wall_dem)
    vis = comms.line_of_sight(HAB, wall_dem)
    rng = np.random.default_rng(1)
    agree = []
    for r, c in rng.integers(0, N, (300, 2)):
        xy = (c + 0.5, -(r + 0.5))
        agree.append(comms.profile_los(z, gt, HAB, xy, comms.ANTENNA_H, comms.ASTRONAUT_H)
                     == vis[r, c])
    assert np.mean(agree) > 0.97


def test_check_route_measures_the_stretch_behind_the_wall(wall_dem):
    xs = np.arange(60.5, 160.5, 1.0)              # east along y = -180.5, 100 m
    coords = np.column_stack([xs, np.full_like(xs, -180.5)])
    out = comms.check_route(coords, HAB, wall_dem, t_s=np.arange(len(xs)) * 2.0)
    s = out["summary"]
    assert s["segments"] == 1
    seg = out["segments"][0]
    assert 100 <= seg["start_m"] + 60.5 <= 104    # the shadow starts at the wall
    assert seg["end_m"] == pytest.approx(99.0)
    assert s["duration_min"] == pytest.approx(seg["length_m"] * 2 / 60, abs=0.05)
    assert s["length_m"] <= s["route_length_m"]


def test_pair_relay_covers_the_leader_entering_the_shadow(tmp_path):
    # Wall along x = 100..102 from the north edge down to y = -150. Habitat at
    # (50.5, -180.5), south-west of the wall's end. The route goes east below the wall
    # (all visible), then north along x = 150.5: the leader enters the wall's shadow at
    # y ~ -120, while the follower, 20 m behind, still sees the habitat and the leader.
    z = np.zeros((N, N))
    z[:150, 100:103] = 10.0
    base = write_dem(tmp_path, z)
    east = [(60.5 + k, -180.5) for k in range(0, 90)]             # to x = 149.5
    north = [(150.5, -180.5 + k) for k in range(0, 141)]          # to y = -40.5
    coords = np.array(east + north)
    single = comms.check_route(coords, HAB, base)
    pair = comms.check_pair(coords, HAB, base, gap_m=20)
    assert single["summary"]["length_m"] == pytest.approx(83, abs=5)   # shadow from y ~ -123 (wall corner)
    assert pair["relay"]["length_m"] == pytest.approx(20, abs=5)
    # the link is lost 20 m later than the leader's own radio (the relay stretch)
    start_alone = single["segments"][0]["start_m"]
    assert pair["unlinked_segments"][0]["start_m"] == pytest.approx(start_alone + 20, abs=2)
    assert pair["separation_exceeded"]["length_m"] == 0


def test_pair_separation_limit(tmp_path):
    base = write_dem(tmp_path, np.zeros((N, N)))
    coords = [(10.5 + k, -100.5) for k in range(180)]
    out = comms.check_pair(coords, (10.5, -100.5), base, gap_m=150, max_sep_m=100)
    assert out["max_separation_seen_m"] == pytest.approx(150, abs=1)
    assert out["separation_exceeded"]["length_m"] > 0
    assert out["unlinked"]["length_m"] == 0       # flat: both see the habitat directly


def test_outside_the_box_raises(wall_dem):
    with pytest.raises(ValueError):
        comms.line_of_sight((-10.0, 10.0), wall_dem)
