"""账单合并工具 - 主入口
用法:
    python -m bill_consensus.main                      # 自动扫描 bills/ 目录
    python -m bill_consensus.main 账单1.csv 账单2.csv    # 指定文件
    python bill_consensus/main.py 账单.zip              # 直接运行也支持
    python -m bill_consensus.main -o 报表.html          # 自定义输出

支持:
- CSV / Excel (.xlsx .xls) / ZIP 压缩包 / 图片(需 Tesseract)
- 微信 / 支付宝 / 任意银行卡账单(自动识别)
- 无参数时自动扫描 bills/ 目录下所有账单
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import webbrowser
import zipfile
from datetime import datetime
from pathlib import Path

# ============= 依赖友好检测 =============
_MISSING_DEPS = []
try:
    import pandas as pd
except ImportError:
    _MISSING_DEPS.append("pandas")
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:
    _MISSING_DEPS.append("jinja2")
try:
    import openpyxl  # noqa: F401
except ImportError:
    _MISSING_DEPS.append("openpyxl")

if _MISSING_DEPS:
    print("=" * 60)
    print("❌ 缺少必要依赖: " + ", ".join(_MISSING_DEPS))
    print()
    print("请运行以下命令安装:")
    print()
    print("    pip install -r requirements.txt")
    print()
    print("或单独安装:")
    print(f"    pip install {' '.join(_MISSING_DEPS)}")
    print("=" * 60)
    sys.exit(1)


# 兼容两种运行方式:
#   1. python -m bill_consensus.main   (包模式)
#   2. python bill_consensus/main.py   (直接运行/VSCode F5/双击)
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from bill_consensus.parsers import auto_parse
    from bill_consensus.parsers.base import transactions_to_df
    from bill_consensus.analyzer import (
        classify_dataframe,
        compute_mom,
        compute_summary,
        dedup_files,
        detect_subscriptions,
        find_suspected_duplicates,
        normalize_dataframe,
    )
else:
    from .parsers import auto_parse
    from .parsers.base import transactions_to_df
    from .analyzer import (
        classify_dataframe,
        compute_mom,
        compute_summary,
        dedup_files,
        detect_subscriptions,
        find_suspected_duplicates,
        normalize_dataframe,
    )


# ============= 路径解析(支持 源码运行 / PyInstaller exe 两种模式) =============
if getattr(sys, "frozen", False):
    # exe 模式:
    #   程序资源(templates 等)在 _MEIPASS 临时解压目录里
    #   用户文件(bills/, output/)放 exe 旁边,方便直接查看
    BASE_DIR = Path(getattr(sys, "_MEIPASS", "")) / "bill_consensus"
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = BASE_DIR.parent  # 项目根目录(含 bills/、output/、run.bat)

TEMPLATE_DIR = BASE_DIR / "templates"
# 输出与账单目录都放在项目根,方便用户直接看到
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "dashboard.html"
BILLS_DIR = PROJECT_ROOT / "bills"

# 所有可识别的账单扩展名
SUPPORTED_EXTS = {".csv", ".xlsx", ".xls", ".zip", ".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def collect_bill_files(args_files: list[str] | None) -> list[str]:
    """收集要解析的账单文件。

    优先级:
    1. 命令行显式指定的文件
    2. bills/ 目录下所有可识别的文件
    3. 都没有: 提示用户
    """
    # 1. 显式指定的文件(可能是 ZIP,先解压)
    result: list[str] = []
    if args_files:
        for f in args_files:
            p = Path(f)
            if not p.exists():
                print(f"  [警告] 文件不存在,已跳过: {f}")
                continue
            if p.suffix.lower() == ".zip":
                result.extend(_extract_zip(p))
            else:
                result.append(str(p))
        return result

    # 2. 自动扫描 bills/ 目录
    if BILLS_DIR.exists():
        files = [
            f for f in BILLS_DIR.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS and not f.name.startswith("~$")
        ]
        if files:
            print(f"📂 在 bills/ 目录找到 {len(files)} 个账单文件:")
            for f in sorted(files):
                print(f"    - {f.name}")
            print()
            # ZIP 在这里就地解压,其余直接返回路径
            for f in sorted(files):
                if f.suffix.lower() == ".zip":
                    result.extend(_extract_zip(f))
                else:
                    result.append(str(f))
            if result:
                return result
        else:
            print(f"📂 bills/ 目录存在但是空的: {BILLS_DIR}")
    else:
        BILLS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"📂 已创建 bills/ 目录: {BILLS_DIR}")

    # 3. 没有任何文件
    print()
    print("=" * 60)
    print("❓ 没找到账单文件。两种使用方式:")
    print()
    print("方式 A (推荐): 把账单文件放进 bills/ 目录,然后重新运行")
    print(f"            目录位置: {BILLS_DIR}")
    print()
    print("方式 B: 直接在命令里指定账单文件路径")
    print("            python -m bill_consensus.main 微信账单.csv 支付宝账单.csv")
    print()
    print("支持的格式: .csv .xlsx .xls .zip .png .jpg")
    print("=" * 60)
    sys.exit(0)


def _extract_zip(zip_path: Path) -> list[str]:
    """解压 ZIP 账单包,返回里面的 CSV/Excel 路径列表。

    微信/支付宝导出的 ZIP 里通常是单个 CSV,但也可能嵌套文件夹。
    解压到临时目录,程序结束后由系统清理。
    """
    print(f"📦 解压 ZIP: {zip_path.name}")
    tmp_dir = Path(tempfile.mkdtemp(prefix="bill_zip_"))

    extracted: list[str] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # 安全检查: 防止 zip slip 攻击
            for member in zf.namelist():
                member_path = (tmp_dir / member).resolve()
                if not str(member_path).startswith(str(tmp_dir.resolve())):
                    print(f"  [警告] 跳过可疑文件: {member}")
                    continue
            zf.extractall(tmp_dir)

        # 找出所有 CSV/Excel
        for f in tmp_dir.rglob("*"):
            if f.is_file() and f.suffix.lower() in {".csv", ".xlsx", ".xls"}:
                extracted.append(str(f))
                print(f"  [解压] {f.relative_to(tmp_dir)}")
    except zipfile.BadZipFile:
        print(f"  [错误] 不是有效的 ZIP 文件: {zip_path.name}")
    except Exception as e:
        print(f"  [错误] 解压失败: {e}")

    return extracted


def run(file_paths: list[str] | None = None, output_path: str | None = None) -> str:
    """主流程:收集文件 → 解析 → 合并 → 分析 → 渲染"""
    print("=" * 60)
    print("📊 账单合并工具 v1.1.0")
    print("=" * 60)

    # 1. 收集文件
    print("\n[1/4] 收集账单文件...")
    files = collect_bill_files(file_paths)
    if not files:
        print("⚠️  没有可解析的文件。")
        sys.exit(1)
    print(f"    共 {len(files)} 个文件待解析")

    # 1.5 文件级去重: 同一个文件被重复丢进 bills/ 时只解析一次
    files, skipped_files = dedup_files(files)
    if skipped_files:
        print(f"    跳过 {len(skipped_files)} 个内容重复的文件:")
        for dup, original in skipped_files:
            print(f"      - {Path(dup).name}  (与 {Path(original).name} 完全相同)")
    print(f"    实际解析 {len(files)} 个文件")

    # 2. 解析 + 合并 + 分类
    print("\n[2/4] 解析账单 + 智能分类...")
    transactions = auto_parse(files)
    if not transactions:
        print()
        print("⚠️  未解析到任何交易记录。可能原因:")
        print("    1. 账单格式不被支持(尝试用 Excel 打开另存为 CSV UTF-8)")
        print("    2. 账单是加密导出的 PDF(请导出为 CSV/Excel 格式)")
        print("    3. 文件编码异常(运行 pip install chardet 后重试)")
        sys.exit(1)
    print(f"    共解析 {len(transactions)} 条交易")

    df = transactions_to_df(transactions)
    classify_dataframe(df)
    normalize_dataframe(df)
    print(f"    已识别 {df['category'].nunique()} 个分类")

    # 3. 统计
    print("\n[3/4] 计算汇总指标...")
    summary = compute_summary(df)
    mom = compute_mom(df)
    suspected = find_suspected_duplicates(df)
    subscriptions = detect_subscriptions(df)

    if mom:
        print(
            f"    环比 {mom['current_month']} vs {mom['prev_month']}: "
            f"支出 {mom['expense_change_pct']}%"
            if mom["expense_change_pct"] is not None
            else f"    环比 {mom['current_month']}: 上月无支出数据"
        )
    if subscriptions:
        print(f"    🔁 识别到 {len(subscriptions)} 项周期性固定支出")
    if suspected:
        print(f"    ⚠️  {len(suspected)} 组疑似重复交易(已在明细中标记,未自动删除)")

    if summary["date_range"][0] and summary["date_range"][1]:
        d_start = datetime.strptime(summary["date_range"][0], "%Y-%m-%d")
        d_end = datetime.strptime(summary["date_range"][1], "%Y-%m-%d")
        days = max(1, (d_end - d_start).days + 1)
    else:
        days = 1
    summary["daily_expense"] = summary["total_expense"] / days
    summary["days"] = days
    summary["saving_rate"] = (
        summary["net"] / summary["total_income"] * 100
        if summary["total_income"] > 0 else 0.0
    )

    print(f"    时间区间: {summary['date_range'][0]} ~ {summary['date_range'][1]}")
    print(f"    总收入:   ¥ {summary['total_income']:.2f}")
    print(f"    总支出:   ¥ {summary['total_expense']:.2f}")
    print(f"    净结余:   ¥ {summary['net']:.2f}")

    # 4. 渲染 HTML
    print("\n[4/4] 生成 HTML 仪表盘...")
    output = Path(output_path) if output_path else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("dashboard.html")

    # 疑似重复交易的标记键: (日期字符串, 来源, 金额绝对值)
    dup_keys: set[tuple[str, str, float]] = set()
    for group in suspected:
        for item in group:
            dup_keys.add((item["date"], item["source"], round(item["amount"], 2)))

    txns_json = json.dumps(
        [
            {
                "date": t.strftime("%Y-%m-%dT%H:%M:%S"),
                "source": row["source"],
                "type": row["type"],
                "category": row["category"],
                "merchant": row["merchant"],
                "merchant_norm": row.get("merchant_norm") or row["merchant"],
                "description": row["description"],
                "account": row["account"],
                "amount": float(row["amount"]),
                "dup": (
                    t.strftime("%Y-%m-%d %H:%M"),
                    row["source"],
                    round(abs(float(row["amount"])), 2),
                ) in dup_keys,
            }
            for t, row in zip(df["date"], df.to_dict("records"))
        ],
        ensure_ascii=False,
    )
    summary_json = json.dumps(summary, ensure_ascii=False)
    mom_json = json.dumps(mom, ensure_ascii=False)
    subscriptions_json = json.dumps(subscriptions, ensure_ascii=False)
    suspected_json = json.dumps(suspected, ensure_ascii=False)

    html = template.render(
        summary=summary,
        summary_json=summary_json,
        txns_json=txns_json,
        mom=mom,
        mom_json=mom_json,
        subscriptions=subscriptions,
        subscriptions_json=subscriptions_json,
        suspected=suspected,
        suspected_json=suspected_json,
    )
    output.write_text(html, encoding="utf-8")
    print(f"    ✅ 已生成: {output.resolve()}")

    print()
    print("=" * 60)
    print("✨ 完成!请用浏览器打开:")
    print(f"   {output.resolve()}")
    print("=" * 60)
    # exe 模式下自动打开浏览器(源码模式由 run.bat 或用户手动打开)
    if getattr(sys, "frozen", False):
        print("🌐 正在自动打开浏览器...")
        try:
            webbrowser.open(output.resolve().as_uri())
        except Exception as e:
            print(f"    (自动打开失败: {e},请手动双击上面的 HTML 文件)")
    return str(output)


def main():
    parser = argparse.ArgumentParser(
        prog="bill-consensus",
        description="账单合并工具 - 微信/支付宝/银行卡账单自动归并分析,生成交互式仪表盘",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                                    自动扫描 bills/ 目录下所有账单
  %(prog)s 微信.csv 支付宝.csv 银行.csv        指定账单文件
  %(prog)s 账单.zip                            支持 ZIP 压缩包自动解压
  %(prog)s -o 我的报表.html                     自定义输出位置
        """,
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="账单文件路径(可选,不填则自动扫描 bills/ 目录)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="输出 HTML 路径(默认: output/dashboard.html)",
    )
    args = parser.parse_args()
    run(args.files or None, args.output)


if __name__ == "__main__":
    main()