"""支付宝账单解析器
支持支付宝官方导出的多种格式:

【完整版 CSV】交易号,商家订单号,交易创建时间,付款时间,最近修改时间,交易来源地,
交易状态,商品名称,商品类目,交易对方,订单金额,收入金额,支出金额,红包金额,
支付方式,银行流水号,资金渠道,交易方式,券核销

【简化版 CSV】付款时间,交易分类,交易对方,对方账号,商品说明,收/支,金额,收/付款方式,交易状态...

编码自动检测(UTF-8 / GBK / GB18030 等),自动跳过前面的免责声明行。
"""
from __future__ import annotations

import pandas as pd

from .base import BaseParser, Transaction
from .smart_csv import smart_read_csv, smart_read_excel


class AlipayParser(BaseParser):
    name = "alipay"
    supported_extensions = (".csv", ".xlsx", ".xls")

    def can_parse(self, file_path: str) -> bool:
        """支付宝账单特征:
        - 含"交易对方" + "收/支"列(简化版)
        - 含"交易对方" + "收入金额"/"支出金额"(完整版)
        """
        try:
            if file_path.lower().endswith((".xlsx", ".xls")):
                df = smart_read_excel(file_path).head(3)
            else:
                df = smart_read_csv(file_path, nrows=3)
            cols = list(df.columns)
            if "交易对方" not in cols:
                return False
            # 完整版特征
            if any(c in cols for c in ["收入金额", "支出金额", "订单金额"]):
                return True
            # 简化版特征
            if "收/支" in cols or "收支" in cols:
                return True
            return False
        except Exception:
            return False

    def parse(self, file_path: str) -> list[Transaction]:
        if file_path.lower().endswith((".xlsx", ".xls")):
            df = smart_read_excel(file_path)
        else:
            df = smart_read_csv(file_path)

        # 时间列兼容
        date_col = next(
            (c for c in ["付款时间", "交易创建时间", "交易时间", "时间"] if c in df.columns),
            None,
        )
        if not date_col:
            for c in df.columns:
                if "时间" in c:
                    date_col = c
                    break
        if not date_col:
            raise ValueError("找不到日期列")

        # 金额列兼容: 优先收入/支出分列,否则"金额"+"收/支"
        has_split = "收入金额" in df.columns or "支出金额" in df.columns
        has_simple = "金额" in df.columns and ("收/支" in df.columns or "收支" in df.columns)

        transactions: list[Transaction] = []
        for _, row in df.iterrows():
            try:
                date_val = row.get(date_col)
                if pd.isna(date_val):
                    continue
                date = pd.to_datetime(date_val)

                merchant = str(row.get("交易对方", "")).strip()
                description = (
                    str(row.get("商品说明", "")).strip()
                    or str(row.get("商品名称", "")).strip()
                )
                pay_way = (
                    str(row.get("支付方式", "")).strip()
                    or str(row.get("收/付款方式", "")).strip()
                )
                raw_cat = (
                    str(row.get("商品类目", "")).strip()
                    or str(row.get("交易分类", "")).strip()
                )

                # 解析方向与金额
                if has_split:
                    income = float(row.get("收入金额", 0) or 0) if not pd.isna(row.get("收入金额")) else 0.0
                    expense = float(row.get("支出金额", 0) or 0) if not pd.isna(row.get("支出金额")) else 0.0
                else:
                    amount_raw = float(row.get("金额", 0) or 0) if not pd.isna(row.get("金额")) else 0.0
                    direction = str(row.get("收/支", row.get("收支", ""))).strip()
                    if direction in ("收入", "收", "进账", "+"):
                        income, expense = amount_raw, 0.0
                    elif direction in ("支出", "支", "出账", "-"):
                        income, expense = 0.0, amount_raw
                    else:
                        # 不明确:负数为支出,正数为收入
                        if amount_raw < 0:
                            income, expense = 0.0, abs(amount_raw)
                        else:
                            income, expense = amount_raw, 0.0

                if income > 0:
                    transactions.append(
                        Transaction(
                            date=date.to_pydatetime() if hasattr(date, "to_pydatetime") else date,
                            source="alipay",
                            amount=income,
                            type="income",
                            merchant=merchant,
                            description=description,
                            account=pay_way,
                            raw_category=raw_cat,
                        )
                    )
                elif expense > 0:
                    transactions.append(
                        Transaction(
                            date=date.to_pydatetime() if hasattr(date, "to_pydatetime") else date,
                            source="alipay",
                            amount=-expense,
                            type="expense",
                            merchant=merchant,
                            description=description,
                            account=pay_way,
                            raw_category=raw_cat,
                        )
                    )
            except Exception:
                continue

        return transactions