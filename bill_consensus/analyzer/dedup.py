"""账单去重与重复交易检测

两类重复需要分开处理:
1. **同一个文件被重复放入 bills/** —— 按内容 sha256 直接跳过,零风险。
2. **同一笔钱在多平台各记一次**(微信付了,银行卡账单又有一笔) —— 只能"疑似提示",
   不能自动删: 同金额的不同笔交易在现实中很常见,误判会凭空抹掉真实支出。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from .normalize import normalize_merchant


def file_digest(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """计算文件内容的 sha256,用于识别内容完全相同的重复文件。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def dedup_files(paths: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """按内容去重账单文件。

    返回 (保留的文件列表, 被跳过的 [(文件, 与之重复的原有文件)])。
    读取失败的文件照常保留,交给解析环节去报错。
    """
    seen: dict[str, str] = {}
    kept: list[str] = []
    skipped: list[tuple[str, str]] = []

    for p in paths:
        try:
            digest = file_digest(p)
        except OSError as e:
            print(f"  [警告] 无法读取 {p}: {e}")
            kept.append(p)
            continue
        if digest in seen:
            skipped.append((p, seen[digest]))
        else:
            seen[digest] = p
            kept.append(p)

    return kept, skipped


def find_suspected_duplicates(
    df: pd.DataFrame, max_day_gap: int = 1
) -> list[list[dict]]:
    """找出跨平台疑似重复的交易。

    判定条件(全部满足):
      - 金额相同(精确到分)
      - 商户归一化后相同
      - 发生日期相差不超过 max_day_gap 天
      - 来源平台不同

    返回分组列表,每组 2 条以上。**只提示,不删除** —— 由用户在明细表中自行核对。
    """
    if df.empty or "merchant" not in df.columns or "source" not in df.columns:
        return []

    work = df.copy()
    work["_amt"] = work["amount"].abs().round(2)
    work["_norm"] = work["merchant"].astype(str).map(normalize_merchant)
    work["_date"] = pd.to_datetime(work["date"])

    groups: list[list[dict]] = []

    for _, g in work.groupby(["_amt", "_norm"], sort=False):
        if len(g) < 2 or g["source"].nunique() < 2:
            continue

        records = g.sort_values("_date").to_dict("records")
        used: set[int] = set()

        for i, base in enumerate(records):
            if i in used:
                continue
            cluster = [base]
            for j in range(i + 1, len(records)):
                if j in used:
                    continue
                gap = abs((records[j]["_date"] - base["_date"]).days)
                if gap <= max_day_gap and records[j]["source"] != base["source"]:
                    cluster.append(records[j])
                    used.add(j)
            if len(cluster) > 1:
                used.add(i)
                groups.append(
                    [
                        {
                            "date": r["_date"].strftime("%Y-%m-%d %H:%M"),
                            "source": r["source"],
                            "merchant": r["merchant"],
                            "amount": float(r["_amt"]),
                        }
                        for r in cluster
                    ]
                )

    return groups
