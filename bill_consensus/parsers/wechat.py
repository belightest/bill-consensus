"""微信账单解析器
微信账单官方导出 CSV 格式:
交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态,交易单号,商户单号,备注

微信导出的账单可能是:
- CSV (UTF-8 或 UTF-8 with BOM)
- ZIP 压缩包里的 CSV (由 main.py 先解压)
- Excel 格式(部分版本)

编码自动检测,前置说明行自动跳过。
"""
from __future__ import annotations

import pandas as pd

from .base import BaseParser, Transaction
from .smart_csv import smart_read_csv, smart_read_excel


class WeChatParser(BaseParser):
    name = "wechat"
    supported_extensions = (".csv", ".xlsx", ".xls")

    def can_parse(self, file_path: str) -> bool:
        """微信账单特征:"交易对方" + "收/支" + 微信特有列("交易时间" 或 "金额(元)")

        注意: 支付宝简化版也有"交易对方"+"收/支",所以必须加微信特有列判定,
        避免误抢支付宝的文件。
        """
        try:
            if file_path.lower().endswith((".xlsx", ".xls")):
                df = smart_read_excel(file_path).head(3)
            else:
                df = smart_read_csv(file_path, nrows=3)
            cols = list(df.columns)
            if "交易对方" not in cols or "收/支" not in cols:
                return False
            # 微信特有列: "交易时间" / "金额(元)"
            return ("交易时间" in cols) or ("金额(元)" in cols)
        except Exception:
            return False

    def parse(self, file_path: str) -> list[Transaction]:
        if file_path.lower().endswith((".xlsx", ".xls")):
            df = smart_read_excel(file_path)
        else:
            df = smart_read_csv(file_path)

        transactions: list[Transaction] = []
        for _, row in df.iterrows():
            try:
                date_val = row.get("交易时间")
                if pd.isna(date_val):
                    continue
                date = pd.to_datetime(date_val)

                direction = str(row.get("收/支", "")).strip()
                amount_val = row.get("金额(元)", row.get("金额", None))
                if pd.isna(amount_val):
                    continue
                # 兼容 "¥100.00" / "100.00" / "1,234.56" 等格式
                amount = _parse_amount(amount_val)

                if "支出" in direction:
                    t_type = "expense"
                    signed_amount = -abs(amount)
                elif "收入" in direction:
                    t_type = "income"
                    signed_amount = abs(amount)
                else:
                    t_type = "transfer"
                    signed_amount = amount

                merchant = str(row.get("交易对方", "")).strip()
                description = str(row.get("商品", "")).strip()
                account = str(row.get("支付方式", "")).strip()
                if account in ("nan", "NaN", ""):
                    account = ""

                transactions.append(
                    Transaction(
                        date=date.to_pydatetime() if hasattr(date, "to_pydatetime") else date,
                        source="wechat",
                        amount=signed_amount,
                        type=t_type,
                        merchant=merchant,
                        description=description,
                        account=account,
                    )
                )
            except Exception:
                continue

        return transactions


def _parse_amount(val) -> float:
    """容错解析金额:兼容 '¥100.00' / '100.00' / '1,234.56' / 100.0"""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", "").replace("¥", "").replace("￥", "").replace("元", "")
    return float(s)