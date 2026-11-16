# 数据缺口与补齐计划

本文件回答两个问题：**wmshare 最缺什么数据能力**，以及**每个缺口该在哪一层补**。
「有数据但行为错」的缺陷清单（SDK/script/数据面）单独登记在 [BUGS.md](BUGS.md)。

验证口径：2026-11-13 真实取数（wmshare 1.19.1 / OpenBB 5.0）；2026-11-14 补充探测
（美股行业、分时窗口、港美 store.get 通路）。所有「有/无」结论均附复现命令。

---

## 0. 分层归属：先认清管线真实形状

用户设想的链路是 `airflow → script → wmshare`。真实形状是：

```
airflow（采集+清洗，写 Mongo）
   │  写 datastore 库：fin_income / fin_balance / fin_cashflow / mkt_kline_* / alt_bssaa ...
   │  以及 V1 冻结表：{cn,hk,us}/index、ref_info ...
   ↓  （没有直接调用）
script（XS 解析层，/datanas/winmale/scripts）
   │  store.get(catalog, symbol) 读 Mongo，向上暴露成 $指标码 / xs:catalog 函数
   ↓  （winmale Go 网关）
winmale  POST /v1/analysis/xs/eval（AppId OAuth2 + EC 计费）
   ↓
wmshare SDK（Python，解析 catalog + 发 eval 请求）
   ↓
openbb-wmshare（本仓，OpenBB provider）
```

**关键含义**：

1. airflow **不触发** script。唯一例外是清洗后调 `xs/tools/clear.xs` 清 memo 缓存。
2. **数据在 Mongo 里存在 ≠ wmshare 能取到**。中间必须有一层 XS 函数把它暴露出来。
   `script` 是**能力闸门**——这是本次盘点最重要的结论。
3. 因此缺口分三类，补法完全不同：

| 缺口类型 | 判定方法 | 补在哪一层 | 本仓可否独立完成 |
|---|---|---|---|
| **A. 数据在库，script 未暴露** | `client.eval_result("return store.get(...)")` 有值，但 `client.call(...)` 无对应函数 | **script**（加 `# xs:catalog` 函数）→ 再 `wmshare/tools/extract_from_scripts.py` 刷目录 | ❌ 需改 script 仓 |
| **B. script 已暴露，provider 未接** | `client.call(...)` 有值，OpenBB 无对应命令 | **openbb-wmshare** | ✅ 本仓即可 |
| **C. 数据本身没有** | `store.get` 也返回空 | **airflow**（新增采集+清洗任务）→ 再走 A | ❌ 需改 airflow |

**本次盘点结果：A 类 3 项、B 类 22 项、C 类 6 项。** 也就是说，**绝大多数缺口不需要动
airflow**，卡点在 script 的暴露层和 provider 的适配层。

---

## 1. A 类缺口：数据在库、script 未暴露（最值得优先补）

### A1. 港股 / 美股三大报表 ⭐ 最高价值（✅ 已定案：全市场统一入口，待 script 部署）

**现状（2026-11-16）**：`rptdom.statement` 升级为全市场统一入口的 script 改动已本地提交
（cn 走 LIST 投影；hk/us 内部路由宽表透视成同行式；mkt_* 摘目录注解降级内部实现），
SDK 门面与 provider 已切换（`period=annual|quarter`），**hk/us 三表待 script push 部署后 live**。
下述旧探测记录保留作历史依据。

实测（注意必须用对应市场的 client，`cn` client 查港股会报 `MARKET_MISMATCH`）：

```
hk.call("rptdom.statement", sym="00700", domain="fin.income_statement")  →  []
us.call("rptdom.statement", sym="AAPL",  domain="fin.income_statement")  →  []
```

**但数据是有的**：

```python
us = Client.from_env(market="us")
us.eval_result('return store.get("fin.income", "us.AAPL", 2025, "Q4")')
# → {"accountingStandard": "USGAAP", "annual": 2025, "basicEps": 7.49,
#    "continuedNetProfit": 112010000000, "currencyName": "", ...}   # 54 个字段

hk = Client.from_env(market="hk")
hk.eval_result('return store.get("fin.income", "hk.00700", 2025, "Q4")')
# → {"accountingStandard": ..., "basicEps": ..., "grossProfit": ..., ...}  # 58 个字段
```

**根因**：`sys/rptdom/*.xs` 只做了 `cn` 的域宽表投影。airflow 侧证据：
- `bssaa/config.py::_rptdom_bssaa_task_configs()` 的 dest 硬编码 `"cn"` + `bssaa`；
- `task_catalog.yaml` 里 `hk_finance_fn_income` / `us_finance_fn_balance` 等任务写的是
  `dest_collection: hk/income`、`us/income`（**V1 主链**），走 `odin → balance` 规则，
  与 rptdom 的 `alt.bssaa` 域宽表是**两套不同的投影**。

而 `fin.income` / `fin.balance` / `fin.cashflow` 的 V2 catalog 映射是**跨市场**的
（`storage/v2/mapping.go:33-35`，`V1Index: market.Income` 不分市场），所以 `hk.00700` /
`us.AAPL` 的数据能读出来——只是**没有 XS 函数把它变成消费面**。

**补法（script 层）**：
1. 在 `sys/rptdom/` 增加 `market` 感知：`rptdom.catalog_list(sym, domain)` 用
   `quote.market(sym)` 拼键（当前已是），但 `rptdom.statement` 需要支持
   **不走 `alt.bssaa` 域宽表、而走 `fin.income` 宽表**的回退路径（港美只有后者）。
2. 港美字段名与 A 股不同（`basicEps` / `continuedNetProfit` / `grossProfit` vs
   `eps_basic` / `np_parent` / `operating_cost`），需在 `sys/rptdom/const.xs` 加
   **港美列映射表**（对齐 `stdlib` 口径）。
3. 遵守 script AGENTS.md：口径唯一、事实层不动、适配层只放 `sys/metric/cn/std_compat.xs`
   或其港美对应文件；改动后走 `fmt-xs.sh → check-xs.sh → eval-xs.sh 锚点复现 → func tests
   → push main`。
4. 完成后 `wmshare/tools/extract_from_scripts.py` 重刷 `_catalog/generated/`，
   再 bump `wmshare` 版本，本仓升级依赖即可。

**验收**：`client.call("rptdom.statement", sym="00700", domain="fin.income_statement")` 返回非空，
且字段与 A 股同口径（同名 + 同单位）。

**标准流程约束**：`store.get` 是存储原语，不是目录函数——provider 侧**禁止**经
`eval_result` 直读（会绕开 AppId 目录合同：无参数校验、无单位守护、无归一化）。上表的
eval 探测仅作**诊断**用途（证明数据在库、定位 A 类缺口），不构成产品路径。港美三表的
服务路径只有一条：script 仓按标准流程补 `xs:catalog` 函数（见上文补法），provider 像
消费其他 XS 接口一样接它。

### A2. 季度报表（A 股季报）（✅ 已定案：sampling 扩 Q 季报全档，待 script 部署）

**现状（2026-11-16）**：单季档（Q1..Q3）已在产线（a778aae7）；季报全档（sampling="Q"，
Q1..Q4 混合、期键 "2026:Q1"、n 截总期数）在本地 script 提交中，随统一入口一并部署。
provider 侧以 `period="quarter"` 暴露。

**数据在库**：`store.get("fin.income", "cn.600519", 2026, "Q1")` 有值；
rptdom 另有 `fin_quarterly` 域宽表（`bssaa/config.py` 的 `_RPTDOM_BSSAA_SPECS` 里有）。

**补法（script 层）**：`rptdom.statement` 的 `opts` 增加 `sampling`（`Q1..Q4`），
放开 `statement_years` 的 Q4 过滤（或新增 `statement_periods` 返回全部 SAS）。
provider 侧 `IncomeStatement` 等的 `fiscal_period` 按 `opts.sampling` 透传。

**验收**：`client.call("rptdom.statement", sym="600519", domain="fin.income_statement",
opts={"n": 4, "sampling": "Q3"})` 返回季报行。

### A3. 逐次送转 / 拆股事件

**现状**：`HistoricalSplits` 无法实现。`equity.query_capital_change` 只返回
**当前**股本快照（`{total_shares, free_shares}`），不是事件流。

**部分数据在库**：`bonus.query_list` 的 `content` 字段是自由文本，形如
「每10股派36.00元转增2股」，含送转比例但**未结构化**。

**补法**：
- 短期（script 层，低成本）：在 `sys/bonus/` 加 `bonus.split_events(sym)`，从 `content`
  正则解析出 `(ex_date, numerator, denominator)`。**必须标注为「文本解析派生，非结构化」**，
  且在 `ranges` 里守住比例上界，防止 `每10股` 与 `每股` 混读。
- 长期（airflow 层，推荐）：新增 `cn_corporate_action_split` 采集任务（交易所披露口径的
  送转实施公告），走标准 `container → clean → alt.bssaa` 链路，结构化落库。
- **不建议** provider 侧自己解析文本——那会把不可靠派生逻辑固化进 OpenBB 语义。

---

## 2. B 类缺口：script 已暴露、provider 未接（本仓可独立完成）

这是投入产出比最高的一批。全部已 live 验证上游返回非空。

**2026-11-14 补充探测**：
- **美股行业数据确认存在**：`stocks.query_list`(us) 行含 `industry`（`industry.Y070102`）与
  `industry_name`（英文名）；`$INDUSTRY_CUR("AAPL")` 返回 `industry.Y100103`。名称解析用
  **目录函数** `stocks.industry_members(ind=...)`（单行业仅几十行），不触全表接口——
  `indicator.metrics` + `industry_members` 均为目录注册函数，与其他 XS 接口同一 AppId
  标准流程。`stocks.query_list`(us) 全表单次 ~851k EC
  （[BUGS.md D-3](BUGS.md#d-3-stocksquery_listus-单次-851k-ec--open成本警示非错误)），
  且 provider 禁止按次全表拉取。
- 港美三表数据在库性已复测确认（us 56 / hk 60 字段），但**只作诊断结论**：服务路径必须走
  script 层标准函数，见 A1 的标准流程约束。

### 2.1 P0：✅ 已完成（阶段 0，2026-11-13；阶段 1 补充见 §2.2 标注）

| 项 | 原问题 | 落地 |
|---|---|---|
| 指数历史 | 抛「上游不支持」，但 `399300.INDEX` 有日线 | ✅ 已接通。`utils/index_canon.py` 做别名映射（快照 `_index_canon.json`，由 `tools/refresh_index_canon.py` 从 airflow 重生成）；取数走 `kline.query_at_anchor`（无 `volume_amount` 检查）；`samplingTs`→date；`percent` 除以 100 并做价格反推校验；长窗口按 anchor 向前翻页 |
| 美股 profile | `undefined variable "$STYLE_INDUSTRY"` | ✅ 已修。弃用 `info.profile`（5 码同一个 eval），改走 `indicator.metrics` + `MARKET_PROFILE_EXCLUSIONS` 按市场裁剪，缺失字段置 `None` |
| ratios 口径 | 本地重算与平台漂移 | ✅ 混合口径。最新一期用 curated `$码`（`$GM`/`$ROE_TTM_LAST`/`$ROIC_LAST`/`$TA_TURNOVER`/`$TL_RATE_LAST`/`$QUICK_RATIO_LAST`），历史期保留本地派生。**只用 curated 码**——未精选码返回原生百分数，会 ×100 错位 |
| quote exchange | `exchange` 填了行业键 | ✅ 已改为按代码前缀推交易所 |
| key_metrics 码位 | `market_cap` 用聚合族码、`dividend_yield_ttm` 用派息率码 | ✅ 改为 `$MV_LAST` / `$BONUS_RATE_TTM_LAST` |

**指数别名映射的坑（长期知识，不要删）**：

```
index.hs300  → 399300.INDEX   ✅ 最新 2026-11-12
000300.INDEX                 ❌ 另一只指数，最新只到 2024-12-06（静默给错数据）
index.hs300 直传 kline.bars  ❌ 返回 []
指数 bar 的 percent 是百分数     ❌ 个股才是小数；混用会 ×100 错位
```

映射表来源：`airflow/catalog/index_registry_live.json`（canon 段，538 条有效别名，
asof 2026-11-13）。快照随包分发，`python tools/refresh_index_canon.py --check` 是漂移门禁。

### 2.2 P0：高价值标准模型（上游全就绪）

2026-11-14 阶段 1 首批已接 4 项（#7/#10/#11/#12，见 ✅ 标注）；`EquityPerformance`（#7）经字段
核对**否决**：标准模型无 `symbol` 参数、`price/change` 必填，是全市场快照语义，与
`kline.snapshot` 多窗口涨跌对不上，与 #10 涨跌榜重复——不再映射，多窗口涨跌已由
`equity.price.quote` 覆盖。

| # | OpenBB 命令 | 标准模型 | 上游函数 | 市场 |
|---|---|---|---|---|
| 1 | `equity.fundamental.revenue_per_segment` | RevenueBusinessLine | `segments.query_products` / `query_business` | cn |
| 2 | `equity.fundamental.revenue_per_geography` | RevenueGeographic | `segments.query_region` | cn |
| 3 | `equity.fundamental.filings` | CompanyFilings | `filings.query`（含 PDF URL） | cn |
| 4 | `equity.key_executives` | KeyExecutives | `equity.query_executives`（12 人，含薪酬/持股/学历） | cn |
| 5 | `equity.share_statistics` | ShareStatistics | `equity.query_capital_change` + `$EQUITY_TOTAL_SHARES`/`$EQUITY_FREE_SHARES` | cn/hk/us |
| 6 | `equity.calendar.earnings` | CalendarEarnings | `forecast.disclosure_rows`（财报预约披露日历） | cn |
| ~~7~~ | ~~`equity.price.performance`~~ | ~~PricePerformance~~ | ❌ 语义不匹配（见上），不映射 | — |
| 8 | `equity.screener` | EquityScreener | `screener.query(where, order, limit, offset)` | cn |
| 9 | `equity.market_snapshots` | MarketSnapshots | `kline.query_last_live_many` / `stocks.query_list` | cn |
| ✅ 10 | `equity.discovery.gainers` / `.losers` | EquityGainers/Losers | `screener.index_top_movers(desc)`；price/change 上游没有，Data 覆写为 Optional | cn |
| ✅ 11 | `index.snapshots` | IndexSnapshots | `kline.query_index_last_live_many(keys=[...])`；规范码反键回 `index.*`；`region` 含命令默认 us（恒返 cn 数据，见模型描述） | cn |
| ✅ 12 | `equity.fundamental.trailing_dividend_yield` | TrailingDividendYield | `dividend.yield_ttm`；时点值单行，`limit` 无效已在描述声明 | cn/hk/us |
| 13 | `equity.estimates.forward_eps` / `.forward_pe` / `.price_target` | ForwardEpsEstimates 等 | `estimates.query_forecast`（EPS1-4/PE1-4，40 行）+ `query_rating` | cn |
| 14 | `equity.ownership.institutional` | InstitutionalOwnership | `equity.query_institution_detail/summary` | cn |
| 15 | `equity.ownership.insider_trading` | InsiderTrading | `equity.query_exec_change` | cn |

另：`equity.profile` 的 `industry_name` 已接（2026-11-14）——`$INDUSTRY_CUR` + 一次廉价的
`stocks.industry_members` 名称解析（US Y 码实测 "Consumer Electronics"），见
`models/equity_info.py::_resolve_industry_name`。

### 2.3 P1：中价值

| OpenBB 命令 | 上游 | 备注 |
|---|---|---|
| `equity.fundamental.growth`（3 个） | 现有三表派生 | 纯本地计算，无新上游依赖 |
| `index.sectors` | `indices.members` 行业键聚合 | 需定义行业映射口径 |
| `equity.compare.peers` | 行业成分 × 指标横截面 | 组合逻辑，非单一上游函数 |
| `equity.ownership.share_statistics` | `equity.query_holder10` / `holdernum` | 十大股东语义与 OpenBB 不完全对齐 |
| `equity.short_interest` | `intl.query_sellshort` | hk/us |
| `equity.fundamental.management_discussion` | `notice` 全文 | 需清洗，优先级低 |

### 2.4 自建命令（语义不匹配标准模型）

`EquityScreener` 的 OpenBB 模型是固定字段参数化筛选，wmshare 是 `$码` 布尔表达式全市场
扫描。**不硬塞标准模型**，改用 `openbb_core_extension` 暴露自有命名空间：

```python
obb.wmshare.screener(where="$ROE_TTM_LAST > 0.15 && $BONUS_RATE_3Y_AVG_LAST > 0.03")
obb.wmshare.index_valuation_trend(key="index.hs300", window="5y")  # indices.trend
obb.wmshare.moneyflow(symbol="600519")  # moneyflow.query_bars
obb.wmshare.margin(symbol="600519")  # margin.query
obb.wmshare.cbond_board()  # cbond.board
```

---

## 3. C 类缺口：确实没有数据（需 airflow 层）

| 缺口 | 现状 | 补法 |
|---|---|---|
| ETF 档案 / 持仓 / 跟踪指数 | 只有 `kline.is_etf` 布尔 + ETF 日线 | airflow 新增 ETF 元数据采集（发行公告/定期持仓披露） |
| 分钟级历史 | 只有当日 `query_min1_live`，无回溯。窗口口径（2026-11-14 归档）：仅交易日盘后 ~36h 内可取；美股仅自身盘中时段写入（北京时间夜间的白天查询为空）；非交易日且超 36h 返回 `None`（SDK docstring「休市返回上一交易日」与实测不符，见 [BUGS.md SDK-6](BUGS.md#sdk-6-min1-休市行为与-docstring-不符--open)） | airflow 落分钟 bar（存储成本高，需先议 TTL） |
| 期权 / 加密 / 外汇 / 固收 | 完全不在数据面 | 不在 wmshare 定位内，建议独立 provider |
| 全市场分红/解禁日历 | 无跨标的事件流函数 | airflow 建事件流索引，或在 script 加轻量聚合 |
| 中信行业估值 | `indices.trend` 覆盖申万一级 31 + 红利 14，中信无 | airflow 补中信行业数据 |
| Level2 / NBBO | 无逐笔 | 数据合作级别，不在范围 |

---

## 4. 补齐计划（按阶段）

### 阶段 0：纠错（本仓）—— ✅ 已完成 2026-11-13

1. ✅ `index_historical.py` 真实取数 + 别名映射（`utils/index_canon.py` + `tools/refresh_index_canon.py`）。
2. ✅ `equity_info.py` 按市场裁剪指标码，修美股 400。
3. ✅ `financial_ratios.py` 混合口径（最新期 `$码`、历史期本地派生）。
4. ✅ `key_metrics.py` 两个码位修正；`equity_quote.py` 的 `exchange` 修正。
5. ✅ 测试：137 passed / 2 skipped；`integration/test_live.py` 新增指数历史与美股 profile 用例。

**验收结果**：`make check` 全绿；`index.hs300` 实测返回 692 根（2024-01-02 → 2026-11-12）；
`equity.profile(symbol="AAPL")` 不再 400。

### 阶段 1：B 类 P0 —— ✅ 已完成（2026-11-14，提交 22483ed/608196b/0187ee9 等）

1. ✅ §2.2 #3/#4/#5/#6/#9(缓行)/#10/#11/#12/#13 + #1/#2（segments 双端点）+ growth×3 + short_interest（探测门禁缓行）。
2. ✅ 自建命名空间 `obb.wmshare.*` 5 命令（screener/index_valuation_trend/moneyflow/margin/cbond_board）。
3. ✅ `equity.profile` 港美 industry_name（`indicator.metrics` + `stocks.industry_members`，全目录函数）。
4. ✅ 探测门禁拦下 3 项并记 GAPS：PriceTarget（无目标价字段）、ShortInterest（行全空）、market_snapshots（无全市场接口）。
5. 探测修正：query_executives 实为 10 字段（目录少声明，BUGS SDK-5）；filings 列为 notice_type/pdf_url。

**待办（下轮）**：index.sectors / peers / management_discussion / market_snapshots（均已有缓行理由）。

**验收**：`openbb-build` 后 `obb.reference` 出现新命令；`pytest -m integration` 全绿。

### 阶段 2：A 类 —— ✅ 已完成（2026-11-14 部署后 live 验证通过）

- **A1+A2 重构（2026-11-16，一套接口定案）**：原 mkt_latest/mkt_get 双通路方案按用户边界原则收编——`rptdom.statement` 升级为全市场统一入口（cn 走 LIST 投影、hk/us 内部路由宽表透视成同行式，mkt_* 摘目录注解降级内部实现），sampling 扩 `Q` 季报全档（script 本地提交，**待部署门禁**）；SDK 门面 `cli.statements` 加 `period=annual|quarter` 二档 + `disc.notice` market 透传 + 文档机制三修（`3cac453`）；provider 单路径全走门面、`sampling` 参数换 OpenBB 惯例 `period` 二值。原 SDK 目录收录 `6c319b6`/`f931285`（v1.4.0/v1.5.0）已被上游 `b362ca7` 撤回，mkt_* 不再申请收录。
- **部署门禁**：script 仓 push main = 生产部署（原子 symlink + Redis 失效），**待用户明示确认后执行**；部署后跑 live 链路（hk.00700 / us.AAPL 三表 + cn 季报）并解锁 COVERAGE 的 🔒 行。

**部署后验证清单**（push main 并等 CI `deploy` stage 完成后依次执行）：

```bash
# 1. 远端复验 mkt_* 函数（us.AAPL basicEps≈7.49 / 归母净利≈1120 亿）
python3 - <<'PY'
import wmshare
us = wmshare.Client.from_env(market="us")
d = us.call("rptdom.mkt_latest", sym="AAPL", domain="fin.income_statement")
print("annual =", d.get("annual"), "| basicEps =", d.get("basicEps"))
g = us.call("rptdom.mkt_get", sym="AAPL", domain="fin.income_statement", annual=2025, sampling="Q4")
print("2025Q4 continuedNetProfit =", g.get("continuedNetProfit"))
PY

# 2. provider 港美三表 + cn 季报 live（自动启用被 skip 的用例）
pytest -m integration -q          # hk/us 三表 + cn sampling=Q1 用例不再 skip

# 3. 解锁文档：COVERAGE.md 三大表行 🔒 → ✅；GAPS 阶段 2 → ✅；BUGS S-2 → fixed
# 4. provider 提交 docs 变更
```

按 A1 > A2 > A3 顺序。A1（港美三表）价值最高且数据已在库。

**script 仓工作流（强制）**：
```
fmt-xs.sh → check-xs.sh → eval-xs.sh 锚点复现 → func tests → push main（CI 部署）
```
禁手动发布。完成后在 `../wmshare` 跑 `python tools/extract_from_scripts.py`，
`python tools/validate_catalog.py`，bump 版本，本仓升级 `wmshare>=1.20`。

**airflow 侧仅在 A3 长期方案与 C 类才需要动**，且必须遵守：
- 新增任务走 `task.*` 原子 DAG（crawl+clean 同 DAG 顺序 operator）；
- 可写源是 `auto_pipeline/config.py` / `bssaa/config.py`，`task_catalog.yaml` 是生成物**禁手改**；
- 跑 `make check`（12 个 drift gate）。

### 阶段 3：C 类（需产品决策）

ETF、分钟历史等需先评估存储成本与业务优先级，不在本仓单方面决定。

---

## 5. 探测脚本（上游变更后重跑）

```bash
cd /Users/congwuzhang/work/src/end/openbb-wmshare
.venv/bin/python - <<'PY'
from wmshare import Client
import datetime, json

def probe(label, fn):
    try:
        r = fn()
        n = len(r) if hasattr(r, "__len__") else r
        print(f"OK   {label:44} n={n}")
        return r
    except Exception as e:
        print(f"FAIL {label:44} {type(e).__name__}: {str(e)[:80]}")

cn, hk, us = (Client.from_env(market=m) for m in ("cn", "hk", "us"))

# --- 指数历史（A1 关键：别名 → 规范码）---
for alias, canon in [("index.hs300", "399300.INDEX"), ("index.shzs", "000001.INDEX")]:
    r = probe(f"index bars {alias} -> {canon}", lambda c=canon: cn.kline.bars(c, n=5, _raw=True))
    if r:
        d = datetime.datetime.fromtimestamp(r[0]["samplingTs"]).date()
        print(f"     latest={d} (需为最近交易日)")

# --- 港美三表：域宽表 vs 原始 catalog ---
# 注意：跨市场查询必须用对应市场的 client，cn client 查港股报 MARKET_MISMATCH
probe("rptdom.statement hk (域宽表)", lambda: hk.call("rptdom.statement", sym="00700",
      domain="fin.income_statement"))
probe("rptdom.statement us (域宽表)", lambda: us.call("rptdom.statement", sym="AAPL",
      domain="fin.income_statement"))
probe("store.get fin.income us.AAPL (原始)", lambda: us.eval_result(
      'return store.get("fin.income", "us.AAPL", 2025, "Q4")'))
probe("store.get fin.income hk.00700 (原始)", lambda: hk.eval_result(
      'return store.get("fin.income", "hk.00700", 2025, "Q4")'))

# --- B 类上游就绪性 ---
probe("segments.query_products", lambda: cn.call("segments.query_products", sym="000333", opts={}))
probe("segments.query_region",   lambda: cn.call("segments.query_region", sym="000333", opts={}))
probe("filings.query",           lambda: cn.call("filings.query", sym="600519", type_key="annual", limit=3))
probe("equity.query_executives", lambda: cn.call("equity.query_executives", sym="600519"))
probe("equity.query_capital_change", lambda: cn.call("equity.query_capital_change", sym="600519"))
probe("forecast.disclosure_rows", lambda: cn.call("forecast.disclosure_rows", sym="600519", limit=3))
probe("screener.query",          lambda: cn.screener.query("$ROE_TTM_LAST > 0.15", limit=3))
probe("index_top_movers",        lambda: cn.screener.index_top_movers(limit=3))
probe("index_last_live_many",    lambda: cn.call("kline.query_index_last_live_many",
                                                 keys=["399300.INDEX"]))
probe("bonus.snapshot_yield_ttm", lambda: cn.call("bonus.snapshot_yield_ttm", sym="600519"))
probe("estimates.query_forecast", lambda: cn.call("estimates.query_forecast", sym="600519"))
probe("equity.query_institution_summary", lambda: cn.call("equity.query_institution_summary",
                                                           sym="600519"))
probe("indices.trend",           lambda: cn.index.trend("index.hs300"))
# 阶段 0 已修复项：以下两行应恒为 OK，变 FAIL 说明回归
probe("us.info.profile (SDK helper)", lambda: us.info.profile("AAPL"))
probe("us indicator.metrics (provider path)",
      lambda: us.indicator.metrics("AAPL", ["$NAME", "$INDUSTRY_CUR"]))
probe("index bar via alias table", lambda: cn.call("kline.query_at_anchor",
      sym="399300.INDEX", limit=5, anchor_date="2026-11-13"))
PY
```

判据：任一行从 `FAIL` 变 `OK` → 对应 C/A 缺口可降级为 B 类，按 §2 接入；
任一行从 `OK` 变 `FAIL` → 本仓文档与测试需同步降级，禁止静默保留 ✅。

注意 `us.info.profile` 是 SDK 自带 helper，**它本身仍会 400**（5 码同一个 eval 的上游
缺陷）。provider 已改走目录指标 `indicator.metrics`，所以该行 FAIL 不影响本仓能力。

---

## 6. 设计原则（不要违反）

- **数据先行**：回答「有没有」前必须 `store.get` 探到底，不要看到上层返回空就断言上游没有
  ——本次 `IndexHistorical` 与港美三表都是**上层结论错误**。
- **只消费目录函数**：provider 一切取数面必须是目录注册函数（AppId + 目录合同：参数校验、
  单位守护、归一化）。禁止 `eval_result` / store 原语直读作为产品路径；`store.get` 只用于
  诊断探测（判断「数据是否在库」），探测结论必须转化为 script 层标准函数后才可接入。
- **不混源**：一个 provider 只报真实可服务能力，不引入第二数据源冒充同口径。
- **不本地重算已有指标**：上游有 `$码` 就用 `$码`（ratios 是反例）。
- **不静默降级**：数据缺失要抛明确错误，不返回空表或占位值。
- **可写源 vs 生成物**：`task_catalog.yaml`、`_catalog/generated/*` 均为生成物，改源头后重跑生成器。
