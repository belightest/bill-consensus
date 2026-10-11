"""生成示例账单测试数据"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)

OUT_DIR = Path(__file__).parent / "sample_bills"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ============= 微信账单 =============
def gen_wechat():
    """生成模拟微信账单"""
    merchants_expense = [
        ("星巴克(国贸店)", "餐饮", "咖啡", [25, 50]),
        ("美团外卖", "餐饮", "外卖订单", [20, 80]),
        ("瑞幸咖啡", "餐饮", "咖啡", [15, 35]),
        ("滴滴出行", "交通", "网约车", [10, 60]),
        ("京东商城", "购物", "笔记本电脑", [200, 1500]),
        ("肯德基", "餐饮", "套餐", [30, 80]),
        ("万达影城", "娱乐", "电影票", [40, 90]),
        ("顺丰快递", "居家", "快递服务", [10, 30]),
    ]
    merchants_income = [
        ("公司财务部", "工资", "9月工资"),
        ("朋友小李", "转账", "还款"),
    ]

    rows = []
    base_date = datetime(2026, 8, 1)

    # 支出
    for i in range(40):
        d = base_date + timedelta(days=random.randint(0, 80), hours=random.randint(8, 22), minutes=random.randint(0, 59))
        m, _, desc, (lo, hi) = random.choice(merchants_expense)
        amt = round(random.uniform(lo, hi), 2)
        rows.append({
            "交易时间": d.strftime("%Y-%m-%d %H:%M:%S"),
            "交易类型": "商户消费",
            "交易对方": m,
            "商品": desc,
            "收/支": "支出",
            "金额(元)": amt,
            "支付方式": random.choice(["零钱", "零钱通", "华夏银行信用卡(尾号4521)"]),
            "当前状态": "支付成功",
            "交易单号": f"4200{random.randint(100000000000000, 999999999999999)}",
            "商户单号": f"M{random.randint(100000000, 999999999)}",
            "备注": "",
        })

    # 收入
    rows.append({
        "交易时间": (base_date + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
        "交易类型": "转账",
        "交易对方": "公司财务部",
        "商品": "9月工资",
        "收/支": "收入",
        "金额(元)": 12500.00,
        "支付方式": "零钱通",
        "当前状态": "已入账",
        "交易单号": f"4200{random.randint(100000000000000, 999999999999999)}",
        "商户单号": "",
        "备注": "",
    })
    rows.append({
        "交易时间": (base_date + timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S"),
        "交易类型": "转账",
        "交易对方": "朋友小李",
        "商品": "还款",
        "收/支": "收入",
        "金额(元)": 350.00,
        "支付方式": "零钱",
        "当前状态": "已入账",
        "交易单号": f"4200{random.randint(100000000000000, 999999999999999)}",
        "商户单号": "",
        "备注": "",
    })

    df = pd.DataFrame(rows)
    df = df.sort_values("交易时间").reset_index(drop=True)
    out = OUT_DIR / "wechat_bill_sample.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")  # utf-8-sig 兼容 Excel
    print(f"  [生成] {out}")


# ============= 支付宝账单 =============
def gen_alipay():
    """生成模拟支付宝账单"""
    expense_items = [
        ("淘宝", "购物", "蓝牙耳机", [50, 300]),
        ("天猫超市", "购物", "日用品", [30, 200]),
        ("美团", "餐饮", "外卖订单", [20, 60]),
        ("饿了么", "餐饮", "外卖订单", [20, 60]),
        ("携程", "旅行", "机票预订", [300, 1500]),
        ("12306", "交通", "高铁票", [50, 300]),
        ("中国移动", "通讯", "话费充值", [50, 200]),
        ("网易云音乐", "娱乐", "会员订阅", [15, 30]),
        ("得到APP", "教育", "课程订阅", [50, 200]),
        ("社区医院", "医疗", "门诊费", [50, 500]),
    ]

    rows = []
    base_date = datetime(2026, 8, 1)

    for i in range(35):
        d = base_date + timedelta(days=random.randint(0, 80), hours=random.randint(8, 22), minutes=random.randint(0, 59))
        merch, cat, desc, (lo, hi) = random.choice(expense_items)
        amt = round(random.uniform(lo, hi), 2)
        rows.append({
            "交易号": f"2026{random.randint(1000000000000000000, 9999999999999999999)}",
            "商家订单号": f"OD{random.randint(100000000, 999999999)}",
            "交易创建时间": d.strftime("%Y-%m-%d %H:%M:%S"),
            "付款时间": d.strftime("%Y-%m-%d %H:%M:%S"),
            "最近修改时间": d.strftime("%Y-%m-%d %H:%M:%S"),
            "交易来源地": "上海市",
            "交易状态": "交易成功",
            "商品名称": desc,
            "商品类目": cat,
            "交易对方": merch,
            "订单金额": amt,
            "收入金额": "",
            "支出金额": amt,
            "红包金额": "",
            "支付方式": random.choice(["余额宝", "花呗", "招商银行(尾号8821)"]),
            "银行流水号": "",
            "资金渠道": "",
            "交易方式": "手机网站支付",
            "券核销": "",
        })

    # 退款场景(收入)
    rows.append({
        "交易号": f"2026{random.randint(1000000000000000000, 9999999999999999999)}",
        "商家订单号": f"OD{random.randint(100000000, 999999999)}",
        "交易创建时间": (base_date + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
        "付款时间": (base_date + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
        "最近修改时间": (base_date + timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
        "交易来源地": "上海市",
        "交易状态": "退款成功",
        "商品名称": "退货退款",
        "商品类目": "退款",
        "交易对方": "淘宝",
        "订单金额": -89.00,
        "收入金额": 89.00,
        "支出金额": "",
        "红包金额": "",
        "支付方式": "余额宝",
        "银行流水号": "",
        "资金渠道": "",
        "交易方式": "手机网站支付",
        "券核销": "",
    })

    df = pd.DataFrame(rows)
    df = df.sort_values("交易创建时间").reset_index(drop=True)
    out = OUT_DIR / "alipay_bill_sample.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"  [生成] {out}")


# ============= 银行卡账单 =============
def gen_bank():
    """生成模拟银行卡账单(招商银行格式)"""
    rows = []
    base_date = datetime(2026, 8, 1)

    expense_items = [
        ("ATM取现", "现金", [500, 2000]),
        ("水电费代扣", "缴费", [50, 300]),
        ("房租", "缴费", [2000, 5000]),
        ("工资到账", "工资", [10000, 20000]),  # 收入
        ("基金定投", "理财", [500, 3000]),
        ("保险扣费", "保险", [100, 1000]),
    ]

    for i in range(25):
        d = base_date + timedelta(days=random.randint(0, 80))
        desc, cat, (lo, hi) = random.choice(expense_items)
        amt = round(random.uniform(lo, hi), 2)

        if desc == "工资到账":
            direction = "收入"
            signed = amt
        elif desc == "ATM取现":
            direction = "支出"
            signed = -amt
        else:
            direction = "支出"
            signed = -amt

        rows.append({
            "交易日": d.strftime("%Y-%m-%d"),
            "摘要": desc,
            "交易金额": signed,
            "账户余额": round(random.uniform(5000, 30000), 2),
            "对方信息": "自动转账" if "定投" in desc else "",
            "收/支": direction,
            "币种": "人民币",
            "交易地点": "上海",
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("交易日").reset_index(drop=True)
    out = OUT_DIR / "bank_bill_sample.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"  [生成] {out}")


if __name__ == "__main__":
    print("生成示例账单数据...")
    gen_wechat()
    gen_alipay()
    gen_bank()
    print(f"\n所有示例已生成至: {OUT_DIR}")