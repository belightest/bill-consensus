"""冒烟测试:用 sample_bills/ 里的示例账单跑通 解析 → 分类 → 统计 全流程。

运行方式(项目根目录):
    pip install pytest
    pytest -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bill_consensus.analyzer import (
    classify_dataframe,
    compute_mom,
    compute_summary,
    dedup_files,
    detect_subscriptions,
    find_suspected_duplicates,
    normalize_dataframe,
    normalize_merchant,
)
from bill_consensus.analyzer.classifier import classify
from bill_consensus.parsers.base import Transaction, transactions_to_df
from bill_consensus.parsers.factory import auto_parse, parse_file

SAMPLES = {
    "wechat": "wechat_bill_sample.csv",
    "alipay": "alipay_bill_sample.csv",
    "bank": "bank_bill_sample.csv",
}


def _sample_path(filename: str) -> Path:
    p = PROJECT_ROOT / "sample_bills" / filename
    if not p.exists():
        pytest.skip(f"示例账单缺失: {p}")
    return p


@pytest.mark.parametrize("platform,filename", list(SAMPLES.items()))
def test_parse_sample(platform: str, filename: str) -> None:
    """每个示例账单都应被正确识别并解析出交易记录"""
    source, txs = parse_file(str(_sample_path(filename)))
    assert len(txs) > 0, f"{platform} 解析出 0 条交易"
    assert all(t.date is not None for t in txs), f"{platform} 存在无日期记录"
    assert any(t.amount != 0 for t in txs), f"{platform} 金额全为 0"


def test_classify_and_summary() -> None:
    """合并解析 → 分类 → 汇总统计 应产出有效结果"""
    files = [str(_sample_path(name)) for name in SAMPLES.values()]
    txs = auto_parse(files)
    assert len(txs) > 0, "合并解析结果为 0 条"

    df = transactions_to_df(txs)
    classify_dataframe(df)

    assert "category" in df.columns, "缺少 category 列"
    assert df["category"].notna().all(), "存在未分类记录"

    summary = compute_summary(df)
    assert summary["total_expense"] > 0, "总支出为 0"
    assert summary["total_income"] > 0, "总收入为 0"


# ============= 新增功能测试 =============

def _df(rows: list[tuple[str, str, float, str, str]]):
    """(日期, 来源, 金额, 类型, 商户) -> DataFrame"""
    from datetime import datetime

    txs = [
        Transaction(
            date=datetime.strptime(d, "%Y-%m-%d %H:%M"),
            source=s,
            amount=a,
            type=t,
            merchant=m,
        )
        for d, s, a, t, m in rows
    ]
    return transactions_to_df(txs)


def test_normalize_merchant() -> None:
    """商户归一化: 剥门店后缀 + 品牌别名,且不过度合并"""
    assert normalize_merchant("美团外卖") == "美团"
    assert normalize_merchant("美团-某某店") == "美团"
    assert normalize_merchant("星巴克(国贸店)") == "星巴克"
    assert normalize_merchant("瑞幸咖啡") == "瑞幸"
    assert normalize_merchant("京东商城") == "京东"
    assert normalize_merchant("某某科技有限公司") == "某某科技"
    assert normalize_merchant("7-11") == "7-11"  # 剩余太短,不剥
    assert normalize_merchant("") == ""


def test_normalize_dataframe_keeps_original() -> None:
    """归一化结果放新列,原始商户名不动"""
    df = _df([("2026-08-01 12:00", "wechat", -30.0, "expense", "美团外卖")])
    normalize_dataframe(df)
    assert df.loc[0, "merchant"] == "美团外卖"
    assert df.loc[0, "merchant_norm"] == "美团"


def test_classify_longest_keyword_first() -> None:
    """关键词应按长度优先,且"充值"不再被"通讯"类抢走"""
    assert classify("", "美团外卖订单", "") == "餐饮"
    assert classify("", "油卡充值", "") == "充值"
    assert classify("", "中国移动营业厅", "") == "通讯"


def test_dedup_files(tmp_path) -> None:
    """内容相同的文件只保留一个"""
    a = tmp_path / "a.csv"
    a.write_text("x,y\n1,2\n", encoding="utf-8")
    b = tmp_path / "b.csv"  # 内容相同,文件名不同
    b.write_text("x,y\n1,2\n", encoding="utf-8")
    c = tmp_path / "c.csv"
    c.write_text("x,y\n9,9\n", encoding="utf-8")

    kept, skipped = dedup_files([str(a), str(b), str(c)])
    assert len(kept) == 2
    assert len(skipped) == 1
    assert skipped[0][0] == str(b)


def test_suspected_duplicates_cross_platform_only() -> None:
    """只有"跨平台 + 同金额 + 同商户 + 时间接近"才算疑似重复"""
    cross = _df([
        ("2026-08-01 12:00", "wechat", -30.0, "expense", "美团外卖"),
        ("2026-08-01 12:30", "alipay", -30.0, "expense", "美团"),
    ])
    dup = find_suspected_duplicates(cross)
    assert len(dup) == 1 and len(dup[0]) == 2

    same_platform = _df([
        ("2026-08-01 12:00", "wechat", -30.0, "expense", "美团外卖"),
        ("2026-08-01 12:30", "wechat", -30.0, "expense", "美团外卖"),
    ])
    assert find_suspected_duplicates(same_platform) == []

    diff_amount = _df([
        ("2026-08-01 12:00", "wechat", -30.0, "expense", "美团外卖"),
        ("2026-08-01 12:30", "alipay", -31.0, "expense", "美团"),
    ])
    assert find_suspected_duplicates(diff_amount) == []


def test_detect_subscriptions() -> None:
    """固定商户 + 等额 + 规律间隔 才算订阅"""
    df = _df([
        ("2026-08-01 10:00", "wechat", -25.0, "expense", "腾讯视频"),
        ("2026-09-01 10:00", "wechat", -25.0, "expense", "腾讯视频"),
        ("2026-10-01 10:00", "wechat", -25.0, "expense", "腾讯视频"),
    ])
    subs = detect_subscriptions(df)
    assert len(subs) == 1
    assert subs[0]["merchant"] == "腾讯视频"
    assert subs[0]["count"] == 3
    assert subs[0]["interval_days"] == 30

    # 金额跳动太大,不算订阅
    irregular = _df([
        ("2026-08-01 10:00", "wechat", -25.0, "expense", "腾讯视频"),
        ("2026-09-01 10:00", "wechat", -80.0, "expense", "腾讯视频"),
    ])
    assert detect_subscriptions(irregular) == []


def test_compute_mom() -> None:
    """环比: 支出从 100 涨到 150 应为 +50%"""
    df = _df([
        ("2026-08-05 10:00", "wechat", 1000.0, "income", "公司"),
        ("2026-08-05 11:00", "wechat", -100.0, "expense", "肯德基"),
        ("2026-09-05 10:00", "wechat", 1000.0, "income", "公司"),
        ("2026-09-05 11:00", "wechat", -150.0, "expense", "肯德基"),
    ])
    mom = compute_mom(df)
    assert mom["current_month"] == "2026-09"
    assert mom["prev_month"] == "2026-08"
    assert mom["expense_change_pct"] == 50.0

    # 只有一个月 → 无环比
    single = _df([("2026-08-05 10:00", "wechat", 1000.0, "income", "公司")])
    assert compute_mom(single) == {}
