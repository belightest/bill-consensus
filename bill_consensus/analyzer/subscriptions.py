"""订阅 / 周期性账单识别

判定一个商户是"订阅式固定支出"需要同时满足:
  - 支出 >= min_count 笔
  - 各笔金额相近(最大值不超过最小值的 1+amount_tolerance 倍)
  - 相邻两笔间隔相对规律(标准差 <= max_gap_stdev 天;仅 2 笔时跳过间隔校验)

识别结果用于仪表盘的"固定支出"板块,帮用户看清每月雷打不动的开销。
"""
from __future__ import annotations

import statistics

import pandas as pd

from .normalize import normalize_merchant


def detect_subscriptions(
    df: pd.DataFrame,
    min_count: int = 2,
    amount_tolerance: float = 0.25,
    max_gap_stdev: int = 7,
) -> list[dict]:
    """识别周期性固定支出,按累计金额降序返回。"""
    if df.empty or "merchant" not in df.columns:
        return []

    exp = df[df["type"] == "expense"].copy()
    if exp.empty:
        return []

    exp["_amt"] = exp["amount"].abs()
    exp["_norm"] = exp["merchant"].astype(str).map(normalize_merchant)
    exp["_date"] = pd.to_datetime(exp["date"])

    results: list[dict] = []

    for norm, g in exp.groupby("_norm"):
        if not norm or len(g) < min_count:
            continue

        amounts = g["_amt"].tolist()
        amax, amin = max(amounts), min(amounts)
        if amin <= 0 or amax > amin * (1 + amount_tolerance):
            continue

        dates = sorted(g["_date"].tolist())
        interval: int | None = None

        if len(dates) >= 3:
            gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            if statistics.pstdev(gaps) > max_gap_stdev:
                continue  # 间隔太乱,不像订阅
            interval = int(statistics.median(gaps))

        results.append(
            {
                "merchant": norm,
                "avg_amount": round(sum(amounts) / len(amounts), 2),
                "count": len(g),
                "total": round(sum(amounts), 2),
                "interval_days": interval,
                "last_date": dates[-1].strftime("%Y-%m-%d"),
            }
        )

    results.sort(key=lambda r: r["total"], reverse=True)
    return results
