"""端到端检查：通过运行中的 FeHALS 后端完整跑一次仿真，验证 /api/results 返回 stats。

用法：conda run -n FeHALS python tests/e2e_stats_check.py [XYZ|LAS]
"""
import json
import math
import sys
import time
import urllib.request

BASE = "http://localhost:8000/api"
# 绕过系统代理,避免 localhost 请求被代理拦截
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, payload=None, raw=False):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with _opener.open(req, timeout=30) as r:
            body = r.read()
            return r.status, (body if raw else json.loads(body))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def run_e2e(output_format):
    print(f"\n===== 端到端测试(输出格式 {output_format})=====")

    # 1. 生成航迹:沿 X 轴往返,航高 20m
    # 11 个航点:trj 用索引作时间(每点 1s),航点越多飞得越慢,默认 2x2m 地面才扫得到
    import json as _json
    wps = [[-5 + 1.0 * i, 0] for i in range(11)]
    st, traj = call("POST", "/trajectory/generate", {
        "waypoints": wps, "altitude": 10,
    })
    assert st == 200, traj
    print(f"航迹: {traj['file_id']} ({traj['point_count']} 点)")

    # 2. 生成配置:低航高大扫描角,保证能打到 2x2m 默认地面
    st, cfg = call("POST", "/config/generate", {
        "platform_type": "UAV", "speed": 0.5, "altitude": 10,
        "scan_freq": 50, "scan_angle": 30, "pulse_freq": 100,
        "output_format": output_format,
    })
    assert st == 200, cfg
    print(f"配置: {cfg['config_id']}")

    # 3. 启动仿真(无模型 → 默认 groundplane 场景)
    st, run = call("POST", "/simulation/run", {
        "trajectory_id": traj["file_id"], "config_id": cfg["config_id"],
    })
    assert st == 200, run
    task_id = run["task_id"]
    print(f"任务: {task_id}")

    # 4. 轮询结果接口(未完成时返回 409)
    deadline = time.time() + 180
    while True:
        st, res = call("GET", f"/results/{task_id}")
        if st == 200:
            break
        assert st == 409 and time.time() < deadline, (st, res)
        time.sleep(2)
    print(f"结果文件: {res['file_path']}")

    # 5. 校验 stats
    s = res["stats"]
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        mark = "✓" if cond else "✗"
        if not cond:
            ok = False
        print(f"  {mark} {name} {detail}")

    check("count > 0", s["count"] > 0, f"(count={s['count']})")
    check("count 与 point_count 一致", s["count"] == res["point_count"])
    zs = [p[2] for p in res["points"][:20000]]
    if s["count"] == len(res["points"]):  # 未降采样时:均值可与渲染点直接对账
        mean = sum(zs) / len(zs)
        check("mean_z 与点集对账", math.isclose(s["mean_z"], mean, abs_tol=1e-3),
              f"(stats={s['mean_z']:.3f} vs 实算={mean:.3f})")
    zmin, zmax = res["bounds"][2], res["bounds"][5]
    check("min/max_z 与 bounds 一致",
          math.isclose(s["min_z"], zmin, abs_tol=1e-3) and math.isclose(s["max_z"], zmax, abs_tol=1e-3),
          f"({s['min_z']:.2f}~{s['max_z']:.2f})")
    check("P5 ≤ 中位数 ≤ P95", s["p05_z"] <= s["median_z"] <= s["p95_z"],
          f"(P5={s['p05_z']:.2f}, P50={s['median_z']:.2f}, P95={s['p95_z']:.2f})")
    h = s["z_histogram"]
    check("直方图 40 箱", len(h["bins"]) == 40, f"(bins={len(h['bins'])})")
    check("直方图计数总和 = 点数", sum(h["bins"]) == s["count"],
          f"(sum={sum(h['bins'])})")
    check("bin_size = 极差/40",
          math.isclose(h["bin_size"], (h["max"] - h["min"]) / 40, abs_tol=1e-9))
    if "intensity" in s:
        i = s["intensity"]
        check("强度统计齐全", i["min"] <= i["mean"] <= i["max"],
              f"(mean={i['mean']:.1f}, {i['min']:.1f}~{i['max']:.1f})")
    else:
        print("  - 无强度统计(该格式未返回 intensity)")

    print("结论:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    fmt = sys.argv[1] if len(sys.argv) > 1 else "XYZ"
    sys.exit(run_e2e(fmt))
