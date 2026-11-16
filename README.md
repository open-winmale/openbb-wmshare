# openbb-wmshare

[![PyPI](https://img.shields.io/pypi/v/openbb-wmshare)](https://pypi.org/project/openbb-wmshare/) [![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-blue)](LICENSE)

> **English TL;DR** — An [OpenBB Platform](https://github.com/OpenBB-finance/OpenBB) provider
> extension for **[wmshare](https://github.com/open-winmale/wmshare)**, the Python SDK for China
> A-share / Hong Kong / US market data. 15 standard OpenBB endpoints: K-lines, quotes, company
> profiles, the three financial statements, server-precomputed key metrics derived ratios,
> dividend history, and A-share index membership. **Install**: `pip install openbb-wmshare`.

把 [wmshare](https://github.com/open-winmale/wmshare) 接进 OpenBB Platform：用标准 OpenBB 命令
取 A股/港股/美股数据，不需要为每个数据源写一套取数代码。

## 安装

```bash
pip install openbb-wmshare
openbb-build          # 让 OpenBB 发现新 provider（首次安装或升级后必跑）
```

从源码安装：`pip install -e .` 然后 `openbb-build`。

要求 Python 3.11+、`openbb-core>=2.0.1`（OpenBB Platform 5.x）。

## 配置凭证

wmshare 需要一对凭证（不是单个 API key）。在[开放平台](https://open.winmale.com)
「我的 → 开放平台 → 我的应用」页获取 AppId 与 API Key：

```json
// ~/.openbb_platform/user_settings.json
{
  "credentials": {
    "wmshare_client_id": "<AppId>",
    "wmshare_client_secret": "<API Key>"
  }
}
```

或使用环境变量（OpenBB 会读取凭证名的大写形式）：

```bash
export WMSHARE_CLIENT_ID=<AppId>
export WMSHARE_CLIENT_SECRET=<API Key>
```

`equity.search`、`index.search`、`index.available` 走随包离线代码表，**无需凭证**。

## 快速上手

```python
from openbb import obb

# A 股前复权日线
bars = obb.equity.price.historical(
    symbol="600519.SH",
    start_date="2026-01-01",
    end_date="2026-10-30",
    provider="wmshare",
    adjust="qfq",
).to_df()

# 港股行情快照
quote = obb.equity.price.quote(symbol="00700.HK", provider="wmshare").to_df()

# 美股日线（裸代码；AAPL.O 之类交易所后缀会被归一）
us = obb.equity.price.historical(symbol="AAPL", start_date="2026-06-01", provider="wmshare").to_df()

# A 股利润表（一年一行）
income = obb.equity.fundamental.income(symbol="600519.SH", limit=3, provider="wmshare").to_df()

# 财务比率（全部为小数：0.32 = 32%）
ratios = obb.equity.fundamental.ratios(symbol="600519.SH", limit=3, provider="wmshare").to_df()

# 服务端预计算指标：PE / PB / ROE(TTM) / 股息率 / PE 十年分位
metrics = obb.equity.fundamental.metrics(symbol="600519.SH", provider="wmshare").to_df()

# 分红历史
divs = obb.equity.fundamental.dividends(symbol="600519.SH", provider="wmshare").to_df()

# 沪深300 成分与权重
members = obb.index.constituents(symbol="index.hs300", provider="wmshare").to_df()

# 离线检索，零额度
hits = obb.equity.search(query="茅台", provider="wmshare").to_df()
```

> **指数键会自动转规范码**：wmshare 的指数行情按规范码存储，别名不是直觉写法 ——
> `index.hs300` 对应 `399300.INDEX`（**不是** `000300.INDEX`，那是另一只指数）。
> provider 内部完成映射，使用者只需写 `index.hs300`。详见
> [docs/COVERAGE.md](docs/COVERAGE.md) §2.1。

## 支持的端点

32 个 OpenBB 标准模型 + 5 个自建命令 `obb.wmshare.*`，`provider="wmshare"`：

| 命令 | 市场 | 说明 |
|---|---|---|
| `equity.price.historical` | cn / hk / us | 日/周/月 K，`adjust=none\|qfq\|hfq` |
| `equity.price.quote` | cn / hk / us | 最新快照 + 均线 + 多窗口涨跌 |
| `equity.search` | cn / hk / us | 离线代码表检索，无需凭证 |
| `equity.profile` | cn / hk / us | 名称/行业（含行业名）/组织类型/上市日 |
| `equity.fundamental.filings` | cn | 定期报告清单（kind 过滤，含 PDF 链接） |
| `equity.fundamental.management` | cn | 高管名册（薪酬/持股/学历/任期） |
| `equity.ownership.share_statistics` | cn | 股本快照（总股本/自由流通股/占比） |
| `equity.ownership.institutional` | cn | 机构持有人明细 |
| `equity.ownership.insider_trading` | cn | 最新一条高管持股变动 |
| `equity.fundamental.revenue_per_segment` | cn | 分产品/业务收入（dim 参数） |
| `equity.fundamental.revenue_per_geography` | cn | 境内外收入拆分 |
| `equity.calendar.earnings` | cn | 预约披露日历（**symbol 必填**） |
| `equity.estimates.forward_eps` / `.forward_pe` | cn | 机构逐行预测 + 近六月平均聚合行 |
| `equity.fundamental.income_growth` / `.balance_growth` / `.cash_growth` | cn | 行项 YoY（本地派生，零基为 None） |
| `equity.fundamental.income` | cn / hk / us | 利润表（`period=annual\|quarter`，披露原币；SDK 自带读取脚本读 fin_* 宽表，不依赖上游部署） |
| `equity.fundamental.balance` | cn / hk / us | 资产负债表（同上） |
| `equity.fundamental.cash` | cn / hk / us | 现金流量表（同上） |
| `equity.fundamental.metrics` | cn / hk / us | PE/PB/PS/ROE/股息率/PE 十年分位 |
| `equity.fundamental.ratios` | cn | 毛利率/净利率/ROE/ROA/流动比率等；最新期取平台指标，历史期本地派生 |
| `equity.fundamental.dividends` | cn / hk / us | 分红历史明细 |
| `equity.fundamental.trailing_dividend_yield` | cn / hk / us | TTM 股息率（时点值） |
| `equity.calendar.dividend` | cn / hk / us | 同一数据的日历视图（需传 `symbol`） |
| `equity.discovery.gainers` / `.losers` | cn | 全市场涨跌榜（上游只有涨跌幅） |
| `index.price.historical` | cn | 指数日线（自动把 `index.hs300` 转规范码） |
| `index.snapshots` | cn | 全部指数盘中快照，单次批量 |
| `index.constituents` | cn | 成分股 + 披露权重 + 市值/估值 |
| `index.search` | cn | 指数键检索（中英文名），无需凭证 |
| `index.available` | cn | 全部可用指数键，无需凭证 |
| `obb.wmshare.screener` | cn | XS 表达式全市场扫描（`$码` 透传为列，count=真实命中数） |
| `obb.wmshare.index_valuation_trend` | cn | 周频整体法 PE/PB + 窗口分位 |
| `obb.wmshare.moneyflow` / `.margin` / `.cbond_board` | cn | 资金流 / 两融 / 转债面板 |

**完整覆盖矩阵**（含每个端点逐市场的能力与限制）见 [docs/COVERAGE.md](docs/COVERAGE.md)；
**已知数据缺口与后续补充方案**见 [docs/GAPS.md](docs/GAPS.md)；
**上游 / SDK 缺陷清单**（有数据但行为错的问题登记）见 [docs/BUGS.md](docs/BUGS.md)。

## 使用约定

- **代码格式**：A股 `600519.SH`（也接受 `600519`、`sh.600519`、`600519.SS`）；港股
  `00700.HK`（也接受 `700.HK`，自动补零到 5 位）；美股裸代码 `AAPL`（`AAPL.O`、`BRK.B`
  会被归一为 `AAPL`、`BRK_B`）。
- **单位**：比率与涨跌幅一律小数（`0.0373` = 3.73%）；金额为报表原币（A股=元、港股=港币、
  美股=美元）；股数为股。
- **区间上限**：上游单次查询上限 5 年（1825 天），provider 会自动切块拼接，但长区间会放大
  请求数——默认窗口是最近一年。
- **限流**：不内置本地缓存。请按需缩小区间或减少标的数，避免触发配额。
- **`to_df()` 的索引**：带日期语义的行若模型里有 `date` / `period_ending` 字段，OpenBB 会把它
  提为 DataFrame 索引而不是列（如 `obb.wmshare.moneyflow(...).to_df()` 的索引是交易日）。
  要用列形式时用 `.reset_index()`。

## 三种用法

### 1. Python SDK

```python
from openbb import obb

df = obb.equity.fundamental.income(symbol="600519", provider="wmshare", limit=3).to_df()
```

返回 `OBBject`：`.results` 是 Pydantic 模型列表，`.to_df()` 转 DataFrame，
`.to_dict()` / `.to_json()` 亦可。`provider="wmshare"` 必须显式传（OpenBB 不自动选）。

### 2. REST API（本地服务）

```bash
openbb-api --port 7788          # 启动，Swagger UI 在 /docs，ReDoc 在 /redoc
curl "http://127.0.0.1:7788/api/v1/equity/fundamental/income?provider=wmshare&symbol=600519&limit=3"
```

界面里每个操作都能点 **Try it out** 填参数直接执行，等价于上面这条 curl。

### 3. MCP（给 AI 客户端用）

```bash
openbb-mcp                      # 以 MCP server 形式暴露全部命令
```

需要 OpenBB 的 MCP 配置项，详见 OpenBB 官方文档。

## 开发

```bash
make install     # pip install -e ".[dev]"
make check       # ruff check + ruff format --check + pytest
make integration # 真实取数测试（需凭证，无凭证自动 skip）
```

离线测试用 `tests/conftest.py` 的 `FakeClient`（签名与真实 `wmshare.Client` 一致）驱动完整
的 `Fetcher.fetch_data` 链路，不需要网络或凭证。

## 许可与数据服务

代码 BSD-3-Clause，与 wmshare 一致。**数据本身需 wmshare 账号**，
使用条款见 [wmshare 许可与数据服务](https://github.com/open-winmale/wmshare#许可与数据服务)。
