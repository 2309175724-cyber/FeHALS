"""pointcloud_parser.stats 单元测试：统计量数值正确性、直方图性质、边界情况与格式一致性。

运行：conda run -n FeHALS pytest tests/test_pointcloud_stats.py -v
"""
import json

import laspy
import numpy as np
import pytest

from app.services.pointcloud_parser import HISTOGRAM_BINS, parse, stats


# ---------------------------- 数值正确性 ----------------------------

def test_stats_match_numpy_reference():
    """各统计字段必须与 numpy 直接计算一致（防止字段映射/实现笔误）。"""
    rng = np.random.default_rng(42)
    xyz = rng.normal(size=(5000, 3)) * np.array([10, 20, 3]) + np.array([1, 2, 50])
    inten = rng.uniform(0, 100, size=5000)

    s = stats(xyz, inten)
    z = xyz[:, 2]
    assert s["count"] == 5000
    assert s["mean_z"] == pytest.approx(z.mean())
    assert s["std_z"] == pytest.approx(z.std())  # 总体标准差（ddof=0）
    assert s["min_z"] == pytest.approx(z.min())
    assert s["max_z"] == pytest.approx(z.max())
    assert s["median_z"] == pytest.approx(np.percentile(z, 50))
    assert s["p05_z"] == pytest.approx(np.percentile(z, 5))
    assert s["p95_z"] == pytest.approx(np.percentile(z, 95))
    assert s["intensity"]["mean"] == pytest.approx(inten.mean())
    assert s["intensity"]["std"] == pytest.approx(inten.std())
    assert s["intensity"]["min"] == pytest.approx(inten.min())
    assert s["intensity"]["max"] == pytest.approx(inten.max())


def test_uniform_distribution_analytic():
    """z 服从 [0,10] 均匀分布时，统计量应落在解析值附近。"""
    rng = np.random.default_rng(7)
    n = 200_000
    xyz = np.column_stack([rng.uniform(-5, 5, n), rng.uniform(-5, 5, n), rng.uniform(0, 10, n)])
    s = stats(xyz)
    assert s["mean_z"] == pytest.approx(5.0, abs=0.05)
    assert s["median_z"] == pytest.approx(5.0, abs=0.05)
    assert s["p05_z"] == pytest.approx(0.5, abs=0.1)
    assert s["p95_z"] == pytest.approx(9.5, abs=0.1)
    assert s["std_z"] == pytest.approx(10 / np.sqrt(12), abs=0.03)  # 均匀分布 σ=范围/√12


def test_stats_without_intensity_has_no_key():
    xyz = np.random.default_rng(1).uniform(size=(100, 3))
    s = stats(xyz)
    assert "intensity" not in s
    assert "mean_z" in s  # 高度统计不受影响


# ---------------------------- 直方图性质 ----------------------------

def test_histogram_basic_properties():
    rng = np.random.default_rng(3)
    z = rng.uniform(0, 40, 10_000)
    h = stats(np.column_stack([np.zeros(10_000), np.zeros(10_000), z]))["z_histogram"]
    assert len(h["bins"]) == HISTOGRAM_BINS == 40
    assert sum(h["bins"]) == 10_000  # 直方图必须覆盖全部点
    assert h["min"] == pytest.approx(float(z.min()))
    assert h["max"] == pytest.approx(float(z.max()))
    assert h["bin_size"] == pytest.approx((float(z.max()) - float(z.min())) / HISTOGRAM_BINS)


def test_histogram_bimodal():
    """两簇分离的点云：直方图应只在两端有计数，中间为 0。"""
    z = np.concatenate([np.full(500, 0.0), np.full(500, 100.0)])
    h = stats(np.column_stack([np.zeros(1000), np.zeros(1000), z]))["z_histogram"]
    counts = np.array(h["bins"])
    assert counts[0] == 500          # 最低箱：z=0 簇
    assert counts[-1] == 500         # 最高箱：z=100 簇
    assert counts[1:-1].sum() == 0   # 中间全空


def test_histogram_degenerate_single_bin():
    """所有点等高（模拟恒定航高的理想平面）时应退化为单箱而不崩溃。"""
    z = np.full(300, 42.0)
    h = stats(np.column_stack([np.zeros(300), np.zeros(300), z]))["z_histogram"]
    assert h["bins"] == [300]
    assert h["min"] == h["max"] == 42.0
    assert h["bin_size"] == 0.0


# ---------------------------- 边界情况 ----------------------------

def test_empty_cloud():
    s = stats(np.empty((0, 3)))
    assert s == {"count": 0}


def test_parse_empty_xyz_file(tmp_path):
    p = tmp_path / "empty.xyz"
    p.write_text("", encoding="utf-8")
    r = parse(str(p))
    assert r["point_count"] == 0
    assert r["stats"] == {"count": 0}
    assert r["points"] == []
    assert r["intensity"] is None
    assert r["bounds"] == [0.0] * 6


def test_xyz_missing_intensity_column(tmp_path):
    """只有 3 列（无强度）的 XYZ：intensity 为 None，且 stats 无 intensity 键。"""
    p = tmp_path / "noi.xyz"
    p.write_text("1 2 3\n4 5 6\n7 8 9\n", encoding="utf-8")
    r = parse(str(p))
    assert r["point_count"] == 3
    assert r["intensity"] is None
    assert "intensity" not in r["stats"]
    assert r["stats"]["mean_z"] == pytest.approx(6.0)


def test_xyz_mixed_columns_drops_intensity(tmp_path):
    """部分行缺强度列：整体丢弃强度（长度不匹配），但坐标与统计保留。"""
    p = tmp_path / "mixed.xyz"
    p.write_text("0 0 1 100\n0 0 2\n0 0 3 200\n", encoding="utf-8")
    r = parse(str(p))
    assert r["point_count"] == 3
    assert r["intensity"] is None
    assert "intensity" not in r["stats"]
    assert r["stats"]["mean_z"] == pytest.approx(2.0)


def test_xyz_skips_junk_lines(tmp_path):
    p = tmp_path / "junk.xyz"
    p.write_text(
        "# comment\nnot a point\n1 2 3 4\n\nabc def ghi\n5 6 7 8\n",
        encoding="utf-8",
    )
    r = parse(str(p))
    assert r["point_count"] == 2
    assert r["stats"]["mean_z"] == pytest.approx(5.0)
    assert r["intensity"] == [4.0, 8.0]


# ---------------------------- 降采样 vs 全量统计 ----------------------------

def test_stats_use_full_set_despite_downsampling(tmp_path):
    """渲染点被降采样时，stats 仍须基于全量点。"""
    rng = np.random.default_rng(11)
    n = 5000
    xyz = rng.uniform(size=(n, 3))
    p = tmp_path / "big.xyz"
    p.write_text(
        "\n".join(f"{x} {y} {z} {i}" for i, (x, y, z) in enumerate(xyz)),
        encoding="utf-8",
    )
    r = parse(str(p), max_points=1000)
    assert r["point_count"] == n                    # 全量计数
    assert len(r["points"]) == 1000                 # 渲染降采样
    assert r["stats"]["count"] == n                 # 统计基于全量
    assert r["stats"]["mean_z"] == pytest.approx(xyz[:, 2].mean())
    assert sum(r["stats"]["z_histogram"]["bins"]) == n


# ---------------------------- LAS 格式 ----------------------------

def _write_las(path, xyz, intensity):
    las = laspy.create(file_version="1.2", point_format=1)
    las.header.offsets = [0, 0, 0]
    las.header.scales = [0.001, 0.001, 0.001]
    las.x, las.y, las.z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    las.intensity = intensity
    las.write(str(path))


def test_las_stats_match_xyz(tmp_path):
    """同一批点走 LAS 与 XYZ 两条解析路径，统计结果应一致。"""
    rng = np.random.default_rng(23)
    n = 4000
    xyz = np.column_stack([
        rng.uniform(0, 100, n), rng.uniform(0, 100, n), rng.uniform(10, 60, n)
    ]).round(3)  # 3 位小数，避免 LAS 定点量化误差
    inten = rng.integers(1, 1000, n).astype(np.float64)  # LAS 强度为 uint16,须用整数

    p_xyz = tmp_path / "same.xyz"
    p_xyz.write_text(
        "\n".join(f"{x} {y} {z} {i}" for (x, y, z), i in zip(xyz, inten)),
        encoding="utf-8",
    )
    p_las = tmp_path / "same.las"
    _write_las(p_las, xyz, inten)

    r_xyz, r_las = parse(str(p_xyz)), parse(str(p_las))
    assert r_las["point_count"] == r_xyz["point_count"] == n
    assert r_las["intensity"] is not None
    for key in ("mean_z", "std_z", "min_z", "max_z", "median_z", "p05_z", "p95_z"):
        assert r_las["stats"][key] == pytest.approx(r_xyz["stats"][key], abs=1e-6)
    assert r_las["stats"]["intensity"]["mean"] == pytest.approx(
        r_xyz["stats"]["intensity"]["mean"], abs=1e-6
    )
    assert r_las["stats"]["z_histogram"]["bins"] == r_xyz["stats"]["z_histogram"]["bins"]


# ---------------------------- 可序列化 ----------------------------

def test_stats_json_serializable():
    """后端经 FastAPI 返回，所有值必须是原生 JSON 类型（不能漏包 np.float64）。"""
    xyz = np.random.default_rng(5).uniform(size=(50, 3)) * 10
    inten = np.random.default_rng(6).uniform(size=50)
    s = stats(xyz, inten)
    text = json.dumps(s)  # np.float64 会抛 TypeError
    assert isinstance(json.loads(text), dict)


# ---------------------------- 入口校验 ----------------------------

def test_parse_rejects_unknown_extension(tmp_path):
    p = tmp_path / "cloud.pcd"
    p.write_text("1 2 3\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse(str(p))


def test_parse_missing_file(tmp_path):
    import pytest as _pytest
    with _pytest.raises(FileNotFoundError):
        parse(str(tmp_path / "nope.xyz"))
