"""HELIOS++ 运行环境检测与诊断服务。

检测项：
  1. HELIOS++ 可执行文件：存在性、可执行权限、版本探测
  2. 资源目录完整性：源仓库根目录、data 子目录、pyhelios 平台/扫描器定义
  3. 静态工作目录：模型 / 航迹 / 配置 / 结果
"""
import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

from app import config as cfg

def _severity(items: list[dict]) -> str:
    """根据子项状态汇总整体严重程度：error > warning > ok。"""
    statuses = [i.get("status", "ok") for i in items]
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"

# ------------------------------------------------------------------ #
#  1. HELIOS++ 可执行文件检测
# ------------------------------------------------------------------ #

def _resolve_executable(path: str) -> Optional[str]:
    """解析可执行文件路径。

    若 path 含路径分隔符则视为文件路径直接检查；
    否则视为命令名，在 PATH 中查找（shutil.which）。
    """
    if os.sep in path or "/" in path:
        # 显式文件路径
        p = Path(path)
        return str(p) if p.exists() else None
    # 命令名 —— 在 PATH 中查找
    resolved = shutil.which(path)
    return resolved

def _is_executable(path: str) -> bool:
    """判断文件是否可执行（Unix 权限位 / Windows 存在即可）。"""
    if os.name == "nt":
        return Path(path).exists()
    return bool(Path(path).exists() and os.access(path, os.X_OK))

async def _probe_version(path: str) -> Optional[str]:
    """尝试运行 helios++ 获取版本信息（3 秒超时）。

    HELIOS++ 无标准 --version 参数，此处以 --help 的首行输出为
    尽力探测；失败返回 None，不影响整体诊断。
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            path, "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=3)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return None
        first_line = stdout.decode("utf-8", errors="replace").split("\n", 1)[0].strip()
        if first_line:
            return first_line
    except (FileNotFoundError, OSError):
        pass
    return None

async def diagnose_helios_executable() -> dict:
    """检测 HELIOS++ 可执行文件。"""
    path = cfg.HELIOS_PATH
    resolved = _resolve_executable(path)

    if resolved is None:
        return {
            "path": path,
            "resolved_path": None,
            "found": False,
            "executable": False,
            "version": None,
            "status": "error",
            "message": f"未找到 HELIOS++ 可执行文件「{path}」，请检查 HELIOS_PATH 环境变量或安装 HELIOS++。",
        }

    is_exec = _is_executable(resolved)
    version = await _probe_version(resolved)

    if not is_exec:
        return {
            "path": path,
            "resolved_path": resolved,
            "found": True,
            "executable": False,
            "version": None,
            "status": "error",
            "message": f"文件已找到「{resolved}」但无执行权限，请添加执行权限（chmod +x）。",
        }

    return {
        "path": path,
        "resolved_path": resolved,
        "found": True,
        "executable": True,
        "version": version,
        "status": "ok",
        "message": version or "已就绪",
    }

# ------------------------------------------------------------------ #
#  2. 资源目录完整性检测
# ------------------------------------------------------------------ #

# HELIOS++ 源仓库关键子目录（场景部件 / 演示场景）
_REPO_KEY_DIRS = [
    ("data", "演示数据根目录", True),
    ("data/scenes", "场景定义", False),
    ("data/sceneparts", "场景部件", False),
]

# pyhelios 数据目录关键文件（平台 / 扫描器定义）
_PYHELIOS_KEY_FILES = [
    ("data/platforms.xml", "平台定义", True),
    ("data/scanners_als.xml", "机载扫描器定义", False),
    ("data/scanners_tls.xml", "Terrestrial 扫描器定义", False),
]

def _check_repo() -> dict:
    """检测 HELIOS++ 源仓库根目录及关键子目录。"""
    repo = Path(cfg._HELIOS_REPO)
    label = "HELIOS_REPO"

    if not repo.exists():
        return {
            "name": label,
            "path": str(repo),
            "exists": False,
            "status": "error",
            "message": f"HELIOS++ 源仓库目录不存在「{repo}」，请设置 HELIOS_REPO 环境变量。",
            "subdirs": [],
        }

    subdirs = []
    for rel, desc, critical in _REPO_KEY_DIRS:
        p = repo / rel
        exists = p.exists()
        subdirs.append({
            "path": rel,
            "description": desc,
            "exists": exists,
            "critical": critical,
            "status": "error" if (critical and not exists) else ("ok" if exists else "warning"),
        })

    overall = _severity(subdirs)
    return {
        "name": label,
        "path": str(repo),
        "exists": True,
        "status": overall,
        "message": "目录结构完整" if overall == "ok" else "部分关键子目录缺失",
        "subdirs": subdirs,
    }

def _check_pyhelios_data() -> dict:
    """检测 pyhelios 数据目录（平台/扫描器 XML 定义）。"""
    pyhelios_data = Path(cfg._HELIOS_REPO) / "python" / "pyhelios" / "data"

    if not pyhelios_data.exists():
        return {
            "name": "pyhelios_data",
            "path": str(pyhelios_data),
            "exists": False,
            "status": "error",
            "message": "pyhelios 数据目录不存在，平台/扫描器定义无法解析。",
            "files": [],
        }

    files = []
    for rel, desc, critical in _PYHELIOS_KEY_FILES:
        p = pyhelios_data / rel
        exists = p.exists()
        files.append({
            "path": rel,
            "description": desc,
            "exists": exists,
            "critical": critical,
            "status": "error" if (critical and not exists) else ("ok" if exists else "warning"),
        })

    # 额外检测是否存在任意扫描器 XML（通配 scanners_*.xml）
    scanner_xmls = list(pyhelios_data.glob("scanners_*.xml"))
    files.append({
        "path": f"scanners_*.xml（匹配 {len(scanner_xmls)} 个）",
        "description": "扫描器定义文件（通配）",
        "exists": len(scanner_xmls) > 0,
        "critical": False,
        "status": "ok" if scanner_xmls else "warning",
    })

    overall = _severity(files)
    return {
        "name": "pyhelios_data",
        "path": str(pyhelios_data),
        "exists": True,
        "status": overall,
        "message": "平台/扫描器定义完整" if overall == "ok" else "部分关键文件缺失",
        "files": files,
    }

def _check_assets() -> list:
    """检测每个 --assets 搜索路径。"""
    results = []
    for i, asset_path in enumerate(cfg.HELIOS_ASSETS):
        p = Path(asset_path)
        exists = p.exists()
        results.append({
            "index": i,
            "path": asset_path,
            "exists": exists,
            "status": "ok" if exists else "warning",
            "message": "路径有效" if exists else "路径不存在（可能影响资源解析）",
        })
    return results

def diagnose_resource_dirs() -> list:
    """资源目录完整性检测汇总。"""
    return [
        _check_repo(),
        _check_pyhelios_data(),
    ]

# ------------------------------------------------------------------ #
#  3. 静态工作目录检测
# ------------------------------------------------------------------ #

def diagnose_static_dirs() -> list:
    """检测后端静态工作目录是否就绪。"""
    dirs = [
        ("models", "模型目录", cfg.MODELS_DIR),
        ("trajectories", "航迹目录", cfg.TRAJECTORIES_DIR),
        ("configs", "配置目录", cfg.CONFIGS_DIR),
        ("results", "结果目录", cfg.RESULTS_DIR),
    ]
    results = []
    for key, label, path in dirs:
        exists = Path(path).exists()
        results.append({
            "name": key,
            "label": label,
            "path": str(path),
            "exists": exists,
            "status": "ok" if exists else "error",
            "message": "就绪" if exists else "目录不存在",
        })
    return results

# ------------------------------------------------------------------ #
#  4. 汇总诊断
# ------------------------------------------------------------------ #

async def diagnose_all() -> dict:
    """执行全量环境诊断，返回结构化报告。"""
    executable = await diagnose_helios_executable()
    resources = diagnose_resource_dirs()
    assets = _check_assets()
    static_dirs = diagnose_static_dirs()

    all_items = [executable] + resources + assets + static_dirs
    overall = _severity(all_items)

    summary = {
        "ok": "环境就绪",
        "warning": "环境存在非关键问题，部分功能可能受限",
        "error": "环境检测失败，仿真功能不可用",
    }

    return {
        "overall": overall,
        "summary": summary.get(overall, ""),
        "helios_executable": executable,
        "resource_dirs": resources,
        "assets": assets,
        "static_dirs": static_dirs,
    }