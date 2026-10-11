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

from bill_consensus.analyzer import classify_dataframe, compute_summary
from bill_consensus.parsers.base import transactions_to_df
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
