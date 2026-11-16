# openbb-wmshare

[![PyPI](https://img.shields.io/pypi/v/openbb-wmshare)](https://pypi.org/project/openbb-wmshare/) [![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-blue)](LICENSE)

> **English TL;DR** — An [OpenBB Platform](https://github.com/OpenBB-finance/OpenBB) provider
> extension for **[wmshare](https://github.com/open-winmale/wmshare)**, the Python SDK for China
> A-share / Hong Kong / US market data. 32 standard OpenBB models plus 5 provider-exclusive
> commands: K-lines, quotes, company profiles, the three financial statements, server-precomputed
> metrics, derived ratios, ownership, analyst estimates, growth series, dividends, and A-share
> index membership. **Install**: `pip install openbb-wmshare`, then `openbb-build`.

把 [wmshare](https://github.com/open-winmale/wmshare) 接进 OpenBB Platform：用标准 OpenBB 命令
取 A股/港股/美股数据，不需要为每个数据源写一套取数代码。

## 简介

### 这是什么

本仓是一个 **OpenBB Platform provider 扩展**。它不是数据源、不是代理服务、也不重新实现取数
逻辑，而是一层**进程内的薄适配层**：导入 `wmshare` SDK，把它的调用翻译成 OpenBB 的标准模型，
于是你写的是 OpenBB 语法，跑的是 wmshare 的数据。

```
你的代码 / CLI / REST / MCP / Workspace
        │  obb.equity.fundamental.income(symbol="600519", provider="wmshare")
        ▼
openbb-wmshare（本仓：翻译参数、映射字段、统一单位）
        │  client.statements.income(...)
        ▼
wmshare SDK  ──AppId 认证──▶  生产网关
```

关键点：`equity.fundamental.income` 这类命令**由 OpenBB 自己的 router 声明**，本仓只是把自己的
fetcher 注册到已有的模型名上（见 `openbb_wmshare/__init__.py` 的 `fetcher_dict`）。所以你装的任何
其他 provider 可以并存，用 `provider=` 切换。

### 给谁用

- 已经在用 OpenBB（Python / REST / MCP / Workspace），想补 A股 + 港股 + 美股数据的人。
- 要在同一套接口下横向对比多市场、多数据源的人。
- 想给 AI agent 挂一个中国市场数据工具的人（走 MCP 或 REST 都是现成的）。

### 选本 provider 还是直接调 wmshare SDK

| 你的情况 | 建议 |
|---|---|
| 已有 OpenBB 工作流，或要与其它 provider 并存对比 | **用本 provider**：统一模型、统一单位、`.to_df()`、REST/MCP/Workspace 一次到手 |
| 需要 provider 未覆盖的能力（2752 个指标码全量、全市场批量取数、任意 XS 表达式） | **直接调 [wmshare SDK](https://github.com/open-winmale/wmshare)**：本仓只暴露了其中 37 个命令 |

### 能力概览

**32 个 OpenBB 标准模型 + 5 个自建命令**（`obb.wmshare.*`），共 37。覆盖：

- 行情：日/周/月 K（前/后复权）、实时快照、涨跌榜
- 公司：档案、高管、定期报告、股本、机构与高管持股、分产品/分地区收入
- 财报：三表（利润/资产负债/现金流，`period=annual|quarter`）、三表 YoY、财务比率、服务端预计算指标
- 预测与日历：机构 EPS/PE 预测、预约披露日、分红日历
- 指数：日线、盘中快照、成分与权重、检索、估值分位
- 自建：`screener`（XS 全市场扫描）、`moneyflow`、`margin`、`cbond_board`、`index_valuation_trend`

逐市场完整矩阵与限制见 [docs/COVERAGE.md](docs/COVERAGE.md)。

**数据性质**：所有数据需 wmshare 账号（AppId + API Key），走认证网关并消耗 EC 配额；本仓只是
客户端适配，不含也不缓存数据。条款见 [许可与数据服务](#许可与数据服务)。

### 常见问题

| 现象 | 原因 | 处置 |
|---|---|---|
| 命令没有 `provider="wmshare"` 这个选项 | 装完没重建 OpenBB 索引 | 重跑 `openbb-build` |
| `UnauthorizedError` | 凭证缺失或过期 | 检查 `wmshare_client_id` / `wmshare_client_secret`（配置文件或 `WMSHARE_*` 环境变量） |
| 报超出 EC 配额 | 区间或标的数太大 | 缩小区间、减少标的、调小 `limit` |
| 返回空（HTTP 204 / `EmptyDataError`） | 该标的这一期确实没有这项披露 | 换标的或换参数，通常不是故障 |

### 目录

[简介](#简介) · [安装](#安装) · [配置凭证](#配置凭证) · [快速上手](#快速上手) ·
[支持的端点](#支持的端点) · [使用约定](#使用约定) · [三种程序化用法](#三种程序化用法) ·
[图形界面](#图形界面openbb-workspace自托管) · [开发](#开发)

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

`equity.search` 走随包离线代码表，**无需凭证、零额度**，可用来验证安装是否成功。
`index.search` / `index.available` 虽然也不需要 OpenBB 层预检查，但实际要读服务端指数清单
（`client.index.universe_keys`），**仍需凭证**。

## 快速上手

三步跑到你的第一份数据。

### 第 1 步：验证安装（不需要凭证）

```python
from openbb import obb

hits = obb.equity.search(query="茅台", provider="wmshare").to_df()
print(hits[["symbol", "name"]])
```

预期输出（离线代码表，不联网、不消耗额度）：

```
      symbol  name
0  600519.SH  贵州茅台
```

能打印出 `600519.SH` 就说明 provider 已被 OpenBB 正确发现。报错见[常见问题](#常见问题)。

### 第 2 步：配置凭证

按[配置凭证](#配置凭证)填好 AppId 与 API Key，然后验证一次真实取数：

```python
quote = obb.equity.price.quote(symbol="600519", provider="wmshare").to_df()
print(quote[["symbol", "close", "change_percent"]])
```

### 第 3 步：取第一份财报

```python
income = obb.equity.fundamental.income(symbol="600519", provider="wmshare", limit=2).to_df()
print(income[["fiscal_year", "total_revenue", "eps_basic"]])
```

预期输出（2026-11-16 实测）：

| fiscal_year | total_revenue | eps_basic |
|---|---|---|
| 2025 | 168,838,102,514.79 | 65.66 |
| 2024 | 170,899,152,276.34 | 68.64 |

三表共用一套参数：`symbol`、`limit`（=**期数**，默认 5，上限 12）、`period`（`annual` 年报档
/ `quarter` 季报档）、`market`（默认 `cn`）。

### 参数约定

- **`market=`**：默认 `cn`。只对**裸代码**生效（如 `symbol="700"` + `market="hk"`）；代码带后缀
  时（`00700.HK`）以后缀为准，`market` 被忽略。
- **多标的**：多数命令支持逗号分隔一次取多只，如 `symbol="600519,000858"`，返回按标的分组。
- **`limit` 语义随命令变化**：三表是**期数**（年/季），K 线是**根数**，日历是**条数**。

### 更多示例

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

# A 股季报档利润表（Q1..Q4 逐期）
q = obb.equity.fundamental.income(
    symbol="600519.SH", limit=8, period="quarter", provider="wmshare"
).to_df()

# 财务比率（全部为小数：0.32 = 32%）
ratios = obb.equity.fundamental.ratios(symbol="600519.SH", limit=3, provider="wmshare").to_df()

# 服务端预计算指标：PE / PB / ROE(TTM) / 股息率 / PE 十年分位
metrics = obb.equity.fundamental.metrics(symbol="600519.SH", provider="wmshare").to_df()

# 分红历史
divs = obb.equity.fundamental.dividends(symbol="600519.SH", provider="wmshare").to_df()

# 沪深300 成分与权重
members = obb.index.constituents(symbol="index.hs300", provider="wmshare").to_df()

# 自建命令：全市场按 ROE 筛选
picks = obb.wmshare.screener(where="$ROE_TTM_LAST > 0.15", limit=10, provider="wmshare").to_df()
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
| `index.price.historical` | cn | 指数日线（自动把 `index.hs300` 转规范码）；**仅日频**，`interval` 传周/月会报错 |
| `index.snapshots` | cn | 全部指数盘中快照，单次批量 |
| `index.constituents` | cn | 成分股 + 披露权重 + 市值/估值 |
| `index.search` | cn | 指数键检索（中英文名）；读服务端指数清单，需凭证 |
| `index.available` | cn | 全部可用指数键；同上，需凭证 |
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

## 三种程序化用法

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

需要 OpenBB 的 MCP 配置项，详见 [OpenBB 官方文档](https://docs.openbb.co/platform)。

## 图形界面：OpenBB Workspace（自托管）

OpenBB Platform 后端本身只提供 API，图形界面由 **OpenBB Workspace** 承担。Workspace 已由官方
开源（[OpenBB-finance/workspace](https://github.com/OpenBB-finance/workspace)，Apache-2.0），
其中 `lite/` 是自带前端 + 后端的单镜像打包，可完全本地跑起来。托管版 `pro.openbb.co` 目前
跳转至 `workspace.brightquery.com`（显示 Coming Soon），所以**自托管是当前可行路径**。

### 接入流程

```bash
# 1. 起数据后端（本仓的 provider 在这一层生效）
openbb-api --port 7788

# 2. 取 Workspace 源码并构建镜像
git clone --depth 1 https://github.com/OpenBB-finance/workspace.git
cd workspace/lite

# 3. 构建（需先修下面两个上游断点，见「已知构建问题」）
./build-local.sh --local          # 或 DOCKER_BUILDKIT=1 docker build -t openbb/lite:dev .

# 4. 运行
docker run -d -p 3000:3000 -v openbb-data:/data --name openbb openbb/lite:dev
docker exec openbb credentials    # 打印自动生成的管理员密码
```

打开 `http://127.0.0.1:3000`，用 `admin@openbb.co` + 上一步的密码登录，然后：

1. 左侧 **Connections → Connect Backend**
2. Name 填 `wmshare`，Endpoint URL 填 `http://127.0.0.1:7788`
3. 点 **Test**，看到 `Test successful` 后点 **add**

### 实测结果（2026-11-16，`openbb/lite:dev`）

连接成功后 Workspace 从本仓读到：

| 项 | 数量 |
|---|---|
| Apps | 38 |
| Widgets | 983 |
| Prompts | 7 |

建看板后添加 `Margin` widget 并填 `symbol=600519`，表格正确渲染 2026-11-13 起的融资融券数据，
即 A 股数据在图形界面里端到端可用。

### 已知构建问题（上游，需自行修补）

开源仓的 `lite/Dockerfile` 目前不能直接构建，两处断点：

1. **`COPY terminalpro/package-lock.json` + `npm ci`（Dockerfile:25-26）**：仓库只带 `bun.lock`，
   没有 `package-lock.json`。需先生成 lockfile，或把该行改成
   `RUN npm install --legacy-peer-deps --no-audit --no-fund`。
2. **`terminalpro/package.json` 漏声明 `vega-embed`**：`react-vega` 依赖它，缺失会让
   `vite build` 报 `failed to resolve import "vega-embed"`。补进 `dependencies` 即可。

### 注意事项

- **Workspace 只是前端壳**，必须先起 `openbb-api`，否则 Test 必然失败。
- 容器显示 `unhealthy` 是**误报**：镜像内没有 `curl`，健康检查命令本身无法执行，服务实际正常。
- 连接配置存在容器内 `/data/openbb.db`（SQLite）。`docker stop/start` 不影响；
  删掉 `openbb-data` volume 才会丢失。
- 想换端口就改 `-p 8080:3000`（容器内固定 3000）。

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
