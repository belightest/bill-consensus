"""解析器基类与统一数据结构"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import pandas as pd


@dataclass
class Transaction:
    """统一账单记录"""

    date: datetime
    source: str            # 'wechat' | 'alipay' | 'bank' | 'image'
    amount: float          # 正数=收入, 负数=支出
    type: str              # 'income' | 'expense' | 'transfer'
    merchant: str = ""     # 对手方/商户
    description: str = ""  # 备注/摘要
    category: str = "其他" # 大类
    raw_category: str = "" # 原始分类(平台自带)
    raw_text: str = ""     # 原始行文本(调试用)
    account: str = ""      # 银行卡号/卡尾号

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.strftime("%Y-%m-%d %H:%M:%S")
        return d


def transactions_to_df(transactions: list[Transaction]) -> pd.DataFrame:
    """统一记录列表转 DataFrame"""
    if not transactions:
        return pd.DataFrame(
            columns=[
                "date",
                "source",
                "amount",
                "type",
                "merchant",
                "description",
                "category",
                "raw_category",
                "account",
            ]
        )
    df = pd.DataFrame([t.to_dict() for t in transactions])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


class BaseParser:
    """解析器基类"""

    name: str = "base"
    supported_extensions: tuple = (".csv", ".xlsx", ".xls")

    def can_parse(self, file_path: str) -> bool:
        """判断是否能解析该文件"""
        return file_path.lower().endswith(self.supported_extensions)

    def parse(self, file_path: str) -> list[Transaction]:
        raise NotImplementedError