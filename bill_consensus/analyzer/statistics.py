"""账单统计分析"""
from __future__ import annotations

from datetime import datetime
import pandas as pd


def filter_by_date(
    df: pd.DataFrame,
    start: datetime | str | None = None,
    end: datetime | str | None = None,
) -> pd.DataFrame:
    """按日期范围筛选账单"""
    if df.empty:
        return df
    out = df.copy()
    if start:
        start = pd.to_datetime(start)
        out = out[out["date"] >= start]
    if end:
        # end 包含当天
        end = pd.to_datetime(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        out = out[out["date"] <= end]
    return out


def compute_summary(df: pd.DataFrame) -> dict:
    """计算关键汇总指标"""
    if df.empty:
        return {
            "total_income": 0.0,
            "total_expense": 0.0,
            "net": 0.0,
            "transaction_count": 0,
            "date_range": [None, None],
            "by_category": [],
            "by_source": [],
            "by_month": [],
            "top_merchants": [],
            "by_day_of_week": [],
        }

    income_df = df[df["type"] == "income"]
    expense_df = df[df["type"] == "expense"]

    total_income = income_df["amount"].sum()
    total_expense = abs(expense_df["amount"].sum())
    net = total_income - total_expense

    # 按分类聚合(仅支出)
    cat_group = (
        expense_df.groupby("category")
        .agg(amount=("amount", lambda x: abs(x).sum()), count=("amount", "count"))
        .reset_index()
        .sort_values("amount", ascending=False)
    )
    by_category = [
        {"category": row["category"], "amount": float(row["amount"]), "count": int(row["count"])}
        for _, row in cat_group.iterrows()
    ]

    # 按来源(平台)
    src_group = (
        df.groupby("source")
        .agg(
            income=("amount", lambda x: x[x > 0].sum()),
            expense=("amount", lambda x: abs(x[x < 0]).sum()),
        )
        .reset_index()
    )
    by_source = [
        {
            "source": row["source"],
            "income": float(row["income"]),
            "expense": float(row["expense"]),
        }
        for _, row in src_group.iterrows()
    ]

    # 按月聚合
    df_month = df.copy()
    df_month["month"] = df_month["date"].dt.to_period("M").astype(str)
    month_group = (
        df_month.groupby("month")
        .agg(
            income=("amount", lambda x: x[x > 0].sum()),
            expense=("amount", lambda x: abs(x[x < 0]).sum()),
            count=("amount", "count"),
        )
        .reset_index()
    )
    by_month = [
        {
            "month": row["month"],
            "income": float(row["income"]),
            "expense": float(row["expense"]),
            "count": int(row["count"]),
        }
        for _, row in month_group.iterrows()
    ]

    # Top 商户
    top_merch = (
        expense_df[expense_df["merchant"].str.len() > 0]
        .groupby("merchant")
        .agg(amount=("amount", lambda x: abs(x).sum()), count=("amount", "count"))
        .reset_index()
        .sort_values("amount", ascending=False)
        .head(10)
    )
    top_merchants = [
        {"merchant": row["merchant"], "amount": float(row["amount"]), "count": int(row["count"])}
        for _, row in top_merch.iterrows()
    ]

    # 按星期聚合(消费习惯洞察)
    df_dow = expense_df.copy()
    df_dow["dow"] = df_dow["date"].dt.dayofweek
    dow_group = (
        df_dow.groupby("dow")
        .agg(amount=("amount", lambda x: abs(x).sum()))
        .reset_index()
    )
    dow_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    by_day_of_week = [
        {"dow": dow_names[int(row["dow"])], "amount": float(row["amount"])}
        for _, row in dow_group.iterrows()
    ]

    return {
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "net": float(net),
        "transaction_count": int(len(df)),
        "date_range": [
            df["date"].min().strftime("%Y-%m-%d"),
            df["date"].max().strftime("%Y-%m-%d"),
        ],
        "by_category": by_category,
        "by_source": by_source,
        "by_month": by_month,
        "top_merchants": top_merchants,
        "by_day_of_week": by_day_of_week,
    }


def compute_mom(df: pd.DataFrame) -> dict:
    """计算环比(本月 vs 上月)收支变化。

    "本月"取数据中最新的月份; 若上一个月不在数据范围内则返回空 dict。
    变化率为 None 表示上月基数为 0,无法计算百分比。
    """
    if df.empty:
        return {}

    months = sorted(df["date"].dt.to_period("M").unique())
    if len(months) < 2:
        return {}

    current, previous = months[-1], months[-2]
    if previous != current - 1:
        return {}  # 月份不连续,环比没有意义

    cur_df = df[df["date"].dt.to_period("M") == current]
    prev_df = df[df["date"].dt.to_period("M") == previous]

    cur_expense = abs(cur_df[cur_df["type"] == "expense"]["amount"].sum())
    prev_expense = abs(prev_df[prev_df["type"] == "expense"]["amount"].sum())
    cur_income = cur_df[cur_df["type"] == "income"]["amount"].sum()
    prev_income = prev_df[prev_df["type"] == "income"]["amount"].sum()

    def pct(now: float, before: float):
        if before == 0:
            return None
        return round((now - before) / before * 100, 1)

    return {
        "current_month": str(current),
        "prev_month": str(previous),
        "expense_current": float(cur_expense),
        "expense_prev": float(prev_expense),
        "expense_change_pct": pct(cur_expense, prev_expense),
        "income_current": float(cur_income),
        "income_prev": float(prev_income),
        "income_change_pct": pct(cur_income, prev_income),
    }