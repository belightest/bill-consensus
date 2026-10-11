# 贡献指南

感谢你愿意花时间改进这个项目。

## 最需要的三类贡献

1. **新的银行账单格式** — 覆盖率是这个工具的生命线
2. **分类关键词** — 让归类更准
3. **解析器 bug 修复** — 特别是编码、日期格式相关的边界情况

## 提交 Issue

- 解析失败 → 用 **Bug report** 模板
- 银行不支持 → 用 **New bank format** 模板
- **务必隐去隐私**：姓名、账号、身份证、手机号、具体商户名可替换为 `***`

## 提交 PR

```bash
git clone https://github.com/belightest/bill-consensus.git
cd bill-consensus
pip install -r requirements.txt pytest
pytest -q          # 改动后先跑通冒烟测试
```

**添加新解析器**（以某银行为例）：

1. 在 `bill_consensus/parsers/` 下新建 `mybank.py`，继承 `BaseParser`
2. 实现 `can_parse()`（返回 True 表示"这个文件我能处理"）与 `parse()`（返回 `list[Transaction]`）
3. 在 `parsers/factory.py` 的 `ALL_PARSERS` 里注册
4. 附一份**脱敏的**示例 CSV 到 `sample_bills/`，并在 `tests/test_smoke.py` 里加一条用例

**添加分类关键词**：编辑 `bill_consensus/analyzer/classifier.py` 的 `CATEGORY_RULES`，在对应分类下追加商户名关键词即可。

## 代码风格

- Python 3.10+，保持零额外依赖（`pandas` / `openpyxl` / `jinja2` 之外）
- 解析器不得联网、不得写日志到用户目录
- 提交信息用英文，`feat:` / `fix:` / `docs:` 前缀
