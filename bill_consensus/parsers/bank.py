"""银行卡账单解析器(通用)
银行卡账单格式差异较大,这里做通用智能识别。

支持的银行/格式(启发式匹配):
- 招商银行 / 工商银行 / 建设银行 / 农业银行 / 中国银行 / 交通银行 / 邮储银行...
- 通用格式: 只要含"日期+金额"就能尝试解析

列名候选(中英文、繁简体兼容):
  日期/交易日期/交易日/交易时间/Date/Trans Date/记账日期
  金额/交易金额/Amount/借方金额/贷方金额/收入金额/支出金额
  方向/收/支/借贷标志/收付标志/Direction
  摘要/备注/交易描述/Description/Memo

格式容错:
- 日期: 2026-08-15 / 2026/08/15 / 20260815 / 2026.08.15 / 2026年8月15日 / Excel日期序列号
- 金额: ¥1,234.56 / 1234.56 / 1,234.56 / (1234.56)负数括号表示法
- 编码: UTF-8 / GBK / GB18030 / UTF-16 自动检测
"""
from __future__ import annotations

import re
import pandas as pd

from .base import BaseParser, Transaction
from .smart_csv import smart_read_csv, smart_read_excel


# 列名候选(按优先级)
DATE_COLS = [
    "交易日期", "交易日", "交易时间", "日期", "记账日期", "转账日期",
    "Date", "date", "Trans Date", "Value Date", "Posting Date",
]
AMOUNT_COLS = [
    "交易金额", "金额", "Amount", "amount", "Txn Amount",
    "借方金额", "贷方金额", "发生额", "交易发生额",
]
INCOME_COLS = ["收入金额", "贷方金额", "贷方发生额", "Credit", "credit", "收入"]
EXPENSE_COLS = ["支出金额", "借方金额", "借方发生额", "Debit", "debit", "支出"]
DIRECTION_COLS = [
    "收/支", "借贷标志", "收付标志", "Direction", "direction", "收支",
    "借贷", "收付", "标志",
]
DESC_COLS = [
    "摘要", "交易摘要", "备注", "交易描述", "Description", "Memo",
    "摘要说明", "附言", "用途",
]
MERCHANT_COLS = [
    "对方信息", "对手方", "对方账户", "对方", "交易对方", "对方名称",
    "Merchant", "Counterparty", "收款方", "付款方",
]
BALANCE_COLS = ["余额", "账户余额", "Balance", "balance", "可用余额"]
ACCOUNT_COLS = ["账号", "卡号", "账户", "Account", "卡号末四位", "交易卡号"]


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """在 df 中找到第一个匹配的列名(精确匹配 → 大小写不敏感 → 子串匹配)"""
    cols = [str(c).strip() for c in df.columns]

    # 第一轮: 精确匹配
    for cand in candidates:
        if cand in cols:
            return cand

    # 第二轮: 大小写不敏感
    lower_map = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]

    # 第三轮: 子串匹配(列名包含候选词)
    for cand in candidates:
        for col in cols:
            if cand in col or col in cand:
                return col
    return None


def _parse_date(val) -> pd.Timestamp | None:
    """容错解析日期。
    支持: 2026-08-15 / 2026/08/15 / 20260815 / 2026.08.15 / 2026年8月15日 / Excel 序列号
    """
    if pd.isna(val):
        return None

    # 已经是 Timestamp/datetime
    if isinstance(val, (pd.Timestamp,)):
        return val

    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return None

    # 纯数字 8 位: 20260815
    if re.fullmatch(r"\d{8}", s):
        try:
            return pd.Timestamp(year=int(s[:4]), month=int(s[4:6]), day=int(s[6:8]))
        except ValueError:
            return None

    # 纯数字 6 位: 260815 (默认 20 世纪)
    if re.fullmatch(r"\d{6}", s):
        try:
            return pd.Timestamp(year=2000 + int(s[:2]), month=int(s[2:4]), day=int(s[4:6]))
        except ValueError:
            return None

    # 纯数字可能是 Excel 日期序列号 (1900-01-01 后)
    if re.fullmatch(r"\d{4,6}", s):
        try:
            ts = pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(s))
            if 2000 <= ts.year <= 2100:
                return ts
        except (ValueError, OverflowError):
            return None

    # 中文日期: 2026年8月15日
    s = s.replace("年", "-").replace("月", "-").replace("日", "")
    # 统一 . / 为 -
    s = re.sub(r"[./]", "-", s)

    try:
        return pd.to_datetime(s)
    except Exception:
        return None


def _parse_amount(val) -> float | None:
    """容错解析金额。
    支持: ¥1,234.56 / 1,234.56 / 1234.56 / (1234.56)负数括号 / -1234.56 / +1234.56
    """
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", ""):
        return None

    # 括号负数表示法: (1234.56) → -1234.56
    neg_by_paren = False
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
        neg_by_paren = True

    # 去除货币符号/千分位/空格
    s = s.replace(",", "").replace("¥", "").replace("￥", "").replace("元", "")
    s = s.replace("$", "").replace("RMB", "").replace(" ", "")
    s = s.replace("+", "")  # "+123.45" → "123.45"

    try:
        amount = float(s)
    except ValueError:
        return None

    return -amount if neg_by_paren else amount


class BankParser(BaseParser):
    """通用银行卡账单解析器"""
    name = "bank"
    supported_extensions = (".csv", ".xlsx", ".xls")

    def can_parse(self, file_path: str) -> bool:
        """能识别日期 + 金额两列,且不像微信/支付宝"""
        try:
            if file_path.lower().endswith((".xlsx", ".xls")):
                head = smart_read_excel(file_path).head(3)
            else:
                head = smart_read_csv(file_path, nrows=3)
            cols = list(head.columns)

            # 排除微信/支付宝特征(它们有专门的解析器)
            if "交易对方" in cols and "收/支" in cols:
                return False
            if "交易对方" in cols and any(
                c in cols for c in ["收入金额", "支出金额"]
            ):
                return False

            date_ok = _find_col(head, DATE_COLS) is not None
            amt_ok = _find_col(head, AMOUNT_COLS) is not None
            return date_ok and amt_ok
        except Exception:
            return False

    def parse(self, file_path: str) -> list[Transaction]:
        if file_path.lower().endswith((".xlsx", ".xls")):
            df = smart_read_excel(file_path)
        else:
            df = smart_read_csv(file_path)

        date_col = _find_col(df, DATE_COLS)
        amount_col = _find_col(df, AMOUNT_COLS)
        direction_col = _find_col(df, DIRECTION_COLS)
        income_col = _find_col(df, INCOME_COLS)
        expense_col = _find_col(df, EXPENSE_COLS)
        desc_col = _find_col(df, DESC_COLS)
        merch_col = _find_col(df, MERCHANT_COLS)
        balance_col = _find_col(df, BALANCE_COLS)  # noqa: F841 (保留字段供未来用)
        account_col = _find_col(df, ACCOUNT_COLS)

        if not date_col or not amount_col:
            return []

        transactions: list[Transaction] = []
        for _, row in df.iterrows():
            try:
                date = _parse_date(row.get(date_col))
                if date is None:
                    continue

                desc = str(row.get(desc_col, "")).strip() if desc_col else ""
                merchant = str(row.get(merch_col, "")).strip() if merch_col else ""
                account = str(row.get(account_col, "")).strip() if account_col else ""

                # 解析金额与方向
                if income_col and expense_col:
                    income = _parse_amount(row.get(income_col)) or 0.0
                    expense = _parse_amount(row.get(expense_col)) or 0.0
                    if income > 0:
                        amount, t_type = income, "income"
                    elif expense > 0:
                        amount, t_type = -expense, "expense"
                    else:
                        continue
                else:
                    raw_amount = _parse_amount(row.get(amount_col))
                    if raw_amount is None or raw_amount == 0:
                        continue
                    direction = ""
                    if direction_col:
                        direction = str(row.get(direction_col, "")).strip()

                    # 推断方向
                    if direction in ("收入", "贷", "贷方", "进", "入", "C", "Credit", "credit", "+"):
                        amount, t_type = abs(raw_amount), "income"
                    elif direction in ("支出", "借", "借方", "出", "D", "Debit", "debit", "-"):
                        amount, t_type = -abs(raw_amount), "expense"
                    else:
                        # 无方向列: 正数收入,负数支出
                        if raw_amount >= 0:
                            amount, t_type = raw_amount, "income"
                        else:
                            amount, t_type = raw_amount, "expense"

                transactions.append(
                    Transaction(
                        date=date.to_pydatetime() if hasattr(date, "to_pydatetime") else date,
                        source="bank",
                        amount=amount,
                        type=t_type,
                        merchant=merchant or desc,
                        description=desc,
                        account=account,
                    )
                )
            except Exception:
                continue

        return transactions