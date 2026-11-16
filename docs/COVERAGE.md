# 数据覆盖矩阵（命令 × 市场）

本文件是 `openbb-wmshare` 的能力基线，也是补数据的对照表。**每一项都经真实取数验证**
（2026-11-13，wmshare SDK 1.19.1，OpenBB Platform 5.0 / openbb-core 2.0.1）。未经验证的
结论不写进来。

图例：✅ 可用 ｜ ⚠️ 可用但有明确限制 ｜ ❌ 未注册（上游有数据，provider 未接）｜ ⛔ 上游无数据 

---

## 一、已注册端点（32 个标准模型 + 5 个自建命令）

| OpenBB 命令 | 标准模型 | cn | hk | us | 状态 |
|---|---|---|---|---|---|
| `equity.price.historical` | EquityHistorical | ✅ | ✅ | ✅ | ✅ |
| `equity.price.quote` | EquityQuote | ✅ | ✅ | ✅ | ✅ |
| `equity.search` | EquitySearch | ✅ | ✅ | ✅ | ✅ |
| `equity.profile` | EquityInfo | ✅ | ⚠️ | ⚠️ | hk 行业名待实测；industry_name 走低成本 `industry_members` 路径 |
| `equity.fundamental.income` | IncomeStatement | ✅ | ✅ | ✅ | 全市场统一走 SDK 门面 `cli.statements`（`period=annual\|quarter`；三加一含 indicators）——SDK 内置读取脚本读 fin_* 宽表（专业版同款 window 批量），不依赖上游 script 部署 |
| `equity.fundamental.balance` | BalanceSheet | ✅ | ✅ | ✅ | 同上（AAPL total_assets 4045 亿 USD live） |
| `equity.fundamental.cash` | CashFlowStatement | ✅ | ✅ | ✅ | 同上 |
| `equity.fundamental.metrics` | KeyMetrics | ✅ | ✅ | ✅ | ✅ 仅 10 码 |
| `equity.fundamental.ratios` | FinancialRatios | ✅ | ⛔ | ⛔ | ⚠️ 本地重算 |
| `equity.fundamental.dividends` | HistoricalDividends | ✅ | ✅ | ✅ | ✅ |
| `equity.fundamental.trailing_dividend_yield` | TrailingDividendYield | ✅ | ✅ | ✅ | 时点值（TTM），无历史序列；`limit` 无效 |
| `equity.fundamental.filings` | CompanyFilings | ✅ | ⛔ | ⛔ | `kind=all\|annual\|semi\|quarter`；无 pdf_url 的行跳过 |
| `equity.fundamental.management` | KeyExecutives | ✅ | ⛔ | ⛔ | 高管名册（学历/年龄/任职等透传） |
| `equity.ownership.share_statistics` | ShareStatistics | ✅ | ⛔ | ⛔ | 最新股本快照；free_float=free/total |
| `equity.ownership.institutional` | InstitutionalOwnership | ✅ | ⛔ | ⛔ | 机构持有人明细（比率已归一小数） |
| `equity.ownership.insider_trading` | InsiderTrading | ✅ | ⛔ | ⛔ | 仅最新一条高管持股变动（上游无分页）；全字段 Optional |
| `equity.fundamental.revenue_per_segment` | RevenueBusinessLine | ✅ | ⛔ | ⛔ | `dim=product\|business`；期间取 segments.periods().clean_last；无 tr 的行跳过 |
| `equity.fundamental.revenue_per_geography` | RevenueGeographic | ✅ | ⛔ | ⛔ | clean domestic/overseas 两桶（tr/pct/margin/yoy） |
| `equity.calendar.earnings` | CalendarEarnings | ✅ | ⛔ | ⛔ | **symbol 必填**（上游按标的查询）；report_date←预约日；eps_* 上游无 |
| `equity.estimates.forward_eps` | ForwardEpsEstimates | ✅ | ⛔ | ⛔ | 按机构逐行 + 近六月平均聚合行；mean=eps1；无 low/high/median 分布 |
| `equity.estimates.forward_pe` | ForwardPeEstimates | ✅ | ⛔ | ⛔ | year1..4←PE1..4（上游仅 4 年） |
| `equity.fundamental.income_growth` | IncomeStatementGrowth | ✅ | ⛔ | ⛔ | 本地 YoY（上游无行项增长码）；零基/缺基为 None |
| `equity.fundamental.balance_growth` | BalanceSheetGrowth | ✅ | ⛔ | ⛔ | 同上 |
| `equity.fundamental.cash_growth` | CashFlowStatementGrowth | ✅ | ⛔ | ⛔ | 同上 |
| `equity.calendar.dividend` | CalendarDividend | ✅ | ✅ | ✅ | ⚠️ 强制 symbol |
| `equity.discovery.gainers` | EquityGainers | ✅ | ⛔ | ⛔ | ⚠️ 仅 symbol/name/percent（上游无 price/change） |
| `equity.discovery.losers` | EquityLosers | ✅ | ⛔ | ⛔ | ⚠️ 同上 |
| `index.price.historical` | IndexHistorical | ✅ | ⛔ | ⛔ | 别名需转规范码，见 §2.1 |
| `index.snapshots` | IndexSnapshots | ✅ | ⛔ | ⛔ | 全宇宙单次批量；`region` 仅 cn |
| `index.constituents` | IndexConstituents | ✅ | ⛔ | ⛔ | ✅ |
| `index.search` | IndexSearch | ✅ | ⛔ | ⛔ | ✅ |
| `index.available` | AvailableIndices | ✅ | ⛔ | ⛔ | ✅ |

---

## 一.1 自建命名空间 `obb.wmshare.*`（语义不匹配标准模型的独有能力）

| 命令 | 说明 | cn | hk | us | 备注 |
|---|---|---|---|---|---|
| `wmshare.screener` | XS 表达式全市场扫描；`count`=真实命中数，`$码` 透传为列 | ✅ | ⛔ | ⛔ | 语义不匹配 EquityScreener 标准模型 |
| `wmshare.index_valuation_trend` | 周频整体法 PE/PB + 窗口分位（3y/5y/10y） | ✅ | ⛔ | ⛔ | 上游 indices.trend 预热缓存 |
| `wmshare.moneyflow` | 日频主力/超大/大/中/小单净流入 | ✅ | ⛔ | ⛔ | |
| `wmshare.margin` | 融资融券余额 | ✅ | ⛔ | ⛔ | |
| `wmshare.cbond_board` | 转债全市场面板（~1000 行） | ✅ | ⛔ | ⛔ | |

---

## 二、已修复的事实性错误（2026-11-13）

这三条曾是代码与文档里的事实错误，已在阶段 0 修正。**坑本身保留在此**，因为它们是长期
知识，新人改这些端点时必须知道。

### 2.1 指数历史：曾有数据却报「上游不支持」→ 已接通

旧 `index_historical.py` 直接抛 `OpenBBError("wmshare does not publish index price
history")`。结论是错的。实测（2026-11-13）：

```python
cn = Client.from_env(market="cn")
cn.call("kline.query_at_anchor", sym="399300.INDEX", limit=5, anchor_date="2026-11-13")
# → 5 根，最新 2026-11-12，close=4043.9254
```

数据**当天级新鲜**，覆盖沪深主要宽基（airflow `index_registry_live.json` 的 `canon` 段，
538 条有效别名，asof 2026-11-13）：

| 指数键 | 规范码 | 最新一根 |
|---|---|---|
| `index.hs300` | `399300.INDEX` | 2026-11-12 ✅ |
| `index.shzs` | `000001.INDEX` | 2026-11-12 ✅ |
| `index.csi500` | `000905.INDEX` | 2026-11-12 ✅ |
| `index.sz50` | `000016.INDEX` | 2026-11-12 ✅ |
| `index.cybz` | `399006.INDEX` | 2026-11-12 ✅ |
| `index.star50` | `000688.INDEX` | 2026-11-12 ✅ |

**三个必须记住的坑：**

1. **别名不是直觉写法**：`index.hs300` → `399300.INDEX`，**不是** `000300.INDEX`。
   后者是另一只指数，序列陈旧到 2024-12-06 —— 用错会静默取到错误数据。
   解析逻辑在 `utils/index_canon.py`，快照由 `tools/refresh_index_canon.py` 从
   airflow 注册表重生成（`--check` 可做漂移门禁）。
2. **不能把 `index.*` 直接传给 `kline.bars`** → 返回 `[]`。
3. **不能走 `kline.query_bars` 的规范化路径** —— 指数 volume 单位与个股不同，会触发
   SDK 的 `volume_amount` 不变量误判（比值 ~217，超出 [0.4, 2.5]）。本 provider 改用
   `kline.query_at_anchor`（该函数未声明该检查）。
4. **`percent` 是百分数不是小数**：指数行 `percent = -0.7798` 意为 -0.78%，
   而个股 kline 的 `percent` 已是小数。fetcher 统一除以 100 并做价格反推校验。
5. **原始行没有 `date`**，只有 `samplingTs`（epoch 秒），需自行转换。

分页：`query_at_anchor` 按根数取、按 anchor 日期向前翻，provider 以每页最老日期为
新 anchor 循环（上限 20 页），实测 2.8 年窗口返回 692 根。

### 2.2 美股 `equity.profile`：曾整体 400 → 已修复

```
us = Client.from_env(market="us")
us.info.profile("AAPL")
# 旧: ApiError: HTTP 400: openapi:1: undefined variable "$STYLE_INDUSTRY"
```

`InfoApi.profile` 把 5 个指标码塞进**一个** eval，其中 `$STYLE_INDUSTRY` 在美股上下文
未定义，导致整包失败。修复方式：provider 不再调用 `info.profile`，改走
`indicator.metrics` 并按市场裁剪（`MARKET_PROFILE_EXCLUSIONS`，us 去掉该码），
缺失字段保持 `None`。实测三市场均正常：

| 市场 | 结果 |
|---|---|
| cn / 600519 | 贵州茅台，industry.S340501，大消费，2001-08-27 |
| hk / 00700 | 腾讯控股，industry.H702015，style=None，2004-06-16 |
| us / AAPL | 苹果，industry.Y100103，style=None，1980-12-12 |

### 2.3 `equity.price.quote` 字段映射：映射本身是对的，但 `exchange` 是错的

`kline.snapshot` 实测返回 22 个字段，provider 映射的
`mv/mv_free/ma20/ma60/ma120/chg_5d/chg_20d/chg_90d/roi_1y/kline_date` **全部存在**
（SDK catalog 的 `returns_shape` 声明不完整，只写了 `symbol/close/percent/chg_20d`，
是声明滞后，不影响取数）。

但 `exchange` 原先填的是 `snapshot["industry"]`（如 `industry.S34`）—— 那是行业键，
不是交易所。已改为按代码前缀推导（`.SH`→SSE、`.SZ`→SZSE、`.BJ`→BSE、`.HK`→HKEX、
裸码→US）。

### 2.4 顺带修正的两个指标码

`key_metrics.py` 里两个码位用错，已改：

| 字段 | 旧码 | 新码 | 原因 |
|---|---|---|---|
| `market_cap` | `$ID_MV_LAST` | `$MV_LAST` | `ID_` 是行业聚合族，单标的返回 nil |
| `dividend_yield_ttm` | `$BONUS_TTM_RATE_LAST` | `$BONUS_RATE_TTM_LAST` | 前者是**派息率**，后者才是**股息率** |

实测（2026-11-13）：茅台市值 1.794e12、股息率 3.62%；腾讯 3.515e12、1.37%；
苹果 5.157e12、0.23% —— 均符合常识量级。

---

## 三、逐端点限制说明

| 端点 | 限制 |
|---|---|
| `equity.price.historical` | 区间 ≤1825 天/次、`limit` ≤500/次（provider 已自动切块）；日/周/月，**无分钟历史**（只有当日 `query_min1_live`） |
| `equity.price.quote` | 无 bid/ask/买卖量/成交笔数/NBBO；`prev_close`/`change` 由 `close` 与 `percent` 反推 |
| `equity.fundamental.*` | 三表全市场（cn/hk/us）经 SDK 门面 `cli.statements` 供给，`period=annual`（缺省年报档）/`quarter`（季报全档 Q1..Q4 混合）；`scope` 合并/母公司与 growth/ratios 仅 cn。hk/us 行 k=披露科目原文，provider 侧 camel→snake+overrides 映射，币种按市场补 USD/HKD |
| `equity.fundamental.metrics` | 上游有 **2752 个指标码**，provider 只声明了 10 个 |
| `equity.fundamental.ratios` | **双口径**：最新一期用 curated `$码`（口径与平台一致），更早期次由三表本地派生（`$码` 无历史序列）。两类值都是小数。只用 curated 码——未精选的 `*_RATE`/`$SD` 返回原生百分数，混入会造成 ×100 错位 |
| `equity.calendar.dividend` | 强制 `symbol`，OpenBB 模型语义是日期区间 → 无法服务全市场日历；美股 `ex_date` 出现 `2099-01-01` 占位值，需过滤 |
| `index.search` / `available` | `indices.keys()` 返回不透明 id（`idx_1_0bf8...`），必须走 `indices.universe_keys()` 取真键 |
| 全部 | 除 `equity.search` 外均经 AppId 认证的 `POST /v1/analysis/xs/eval` |

---

## 四、单位与代码约定

| 项目 | 约定 |
|---|---|
| A 股代码 | `600519.SH`；接受 `600519`、`sh.600519`、`600519.SS` |
| 港股代码 | `00700.HK`；接受 `700.HK`（补零到 5 位） |
| 美股代码 | `AAPL`；`AAPL.O`/`AAPL.N` 归一为 `AAPL`，`BRK.B` → `BRK_B` |
| 指数键 | `index.hs300`；接受 `hs300`、`HS300`（**内部转 `399300.INDEX`**） |
| 指数 `percent` | 上游是**百分数**（-0.78 意为 -0.78%），provider 统一转小数；个股 `percent` 上游已是小数 |
| 比率 / 涨跌幅 | 小数（`0.0373` = 3.73%） |
| 金额 | 报表原币（cn=CNY / hk=HKD / us=USD） |
| 股数 | 股 |
| 日期区间 | 单次上游 ≤1825 天，provider 自动切块；默认回溯 1 年 |

## 五、凭证

| 端点组 | 是否需要凭证 |
|---|---|
| `equity.search` | 否（随包离线代码表） |
| `index.search` / `index.available` | 是（读 `universe_keys`） |
| 其余全部 | 是（`require_credentials=False`，由 SDK 自行解析并抛 `AuthError`） |

设计理由见 [GAPS.md §凭证解析](GAPS.md#凭证解析)。

## 六、更新纪律

- 本表是**实测基线**，不是设计意图。任何「✅」必须在 `integration/` 有对应 live 用例。
- 任何「上游无此能力」的结论，必须附可复现命令与返回（见 §2.1 的反例）。
- 上游变更后先跑 `docs/GAPS.md §探测脚本`，再改本表。
