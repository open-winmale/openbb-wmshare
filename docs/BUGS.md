# 上游 / SDK 缺陷清单

本文件登记 **wmshare SDK、script 层、数据面** 已确认的缺陷。每条含证据与修复归属，供后续
统一补充时逐条销账。能力缺口（数据有没有）见 [GAPS.md](GAPS.md)；本文件只记「有数据但行为错」。

状态：`open`（未处理）/ `worked-around`（provider 侧已绕开，上游仍待修）/ `fixed`。

---

## SDK 层（修复归属：`../wmshare`）

### SDK-1 `volume_amount` 守卫误杀指数 bar — `worked-around`

- **症状**：`kline.bars("399300.INDEX", ...)` 触发 `DataError`：`volume*close/amount ≈ 216.9`，
  超出个股守卫带 `[0.4, 2.5]`。指数的量/额口径与个股不同，守卫不应套用。
- **证据**：`kline.query_at_anchor(sym="399300.INDEX", ...)` 无此检查，返回正常序列
  （2026-11-13 实测 692 根，2024-01-02 → 2026-11-12）。
- **绕开**：provider 走 `query_at_anchor`（`openbb_wmshare/models/index_historical.py`）。
- **修复建议**：守卫按 `symbol` 类型（`*.INDEX`）跳过或用指数专用量级带。

### SDK-2 `kline.bars` 错误提示与实际签名不符 — `open`

- **症状**：传不支持的单位参数时，报错文案提示可用 `_units="native"`，但 `kline.bars`
  实际不接受该 kwarg（直接 `TypeError`）。
- **证据**：2026-11-13 探测，报错文案与调用失败并存。
- **修复建议**：要么支持该参数，要么改提示。

### SDK-3 `index.keys()` 返回不透明 ID — `worked-around`

- **症状**：`cli.index.keys()` 返回 `idx_1_0bf8044711d50038` 之类内部 ID，而
  `members/weights/trend/query_index_last_live` 全部要求 `index.hs300` 形式的键。
  按 keys() 的返回值去调 members 会失败。
- **证据**：2026-11-13 实测 `keys()` → 6 个 `idx_1_*`；`universe_keys("broad")` → 11 个真键。
- **绕开**：provider 一律走 `universe_keys(group)`（`utils/index_universe.py`）。
- **修复建议**：`keys()` 返回真键，或文档标注其为内部 ID。

### SDK-4 `demo_client()` 签名漂移 — `open`

- **症状**：demo 的 `kline.bars` 不接受 `freq`；demo 指数键用 `index.hs300` 形式而 live
  `keys()` 返回 `idx_1_*`。按 demo 签名写的测试/代码在 live 上崩，反之亦然。
- **证据**：2026-11-13，`DemoClient._kline_bars() got an unexpected keyword argument 'freq'`。
- **影响**：demo 作为「离线试跑」入口的契约保证失效。
- **修复建议**：demo 签名与 `Client` 对齐（接受并显式拒绝不支持参数，返回 `demo_unsupported`）。

### SDK-5 `kline.snapshot` `returns_shape` 少声明 — `open`

- **症状**：目录声明返回 `symbol/close/percent/chg_20d` 4 字段，实际返回 22 字段
  （`mv/mv_free/ma20/60/120/chg_5d/10d/90d/roi_1y/vol_ratio_5/is_st/is_suspend/...`）。
- **证据**：2026-11-13 实测字段清单（`docs/COVERAGE.md` §2.3）。
- **影响**：按目录写代码的调用方错过可用字段；目录的「防编造」承诺失真。
- **修复建议**：目录补齐 shape 声明。

### SDK-6 `min1` 休市行为与 docstring 不符 — `open`

- **症状**：docstring 称「休市返回上一交易日」，实际非交易日且超出 36h 保留窗时返回
  `None`（2026-11-14 周六实测 `min1("600519") = None`，上周五数据已过 36h）。
- **影响**：按 docstring 写的空值处理会 `AttributeError`。
- **修复建议**：docstring 改为「交易日盘后 36h 内返回当日分时，否则 None」。

---

## script / 网关层（修复归属：script 仓，跨仓协同）

### S-1 `$STYLE_INDUSTRY` 美股上下文未定义 → 整包 eval 400 — `worked-around`

- **症状**：5 个 profile 码塞进同一个 eval，`$STYLE_INDUSTRY` 在美股无定义，导致**整个请求**
  `HTTP 400: undefined variable`，其余 4 个本来有值的码一并失败。
- **证据**：2026-11-13，`InfoApi.profile("AAPL")` 400；裁掉该码后其余码正常返回。
- **绕开**：provider 改走 `indicator.metrics` + `MARKET_PROFILE_EXCLUSIONS` 按市场裁剪
  （`openbb_wmshare/models/equity_info.py`）。
- **修复建议**：未定义码应返回 null 而非整包失败。

### S-2 `rptdom.statement` 港美返空，数据实际在库 — `open`（= GAPS A1）

- **症状**：`rptdom.statement` 对 `00700`/`AAPL` 返回 `[]`；但
  `store.get("fin.income", "us.AAPL", 2025, "Q4")` 返回 56 个 USGAAP 字段、
  `hk.00700` 返回 60 个（2026-11-14 复测确认）。
- **根因**：`bssaa/config.py::_rptdom_bssaa_task_configs()` 把 dest 硬编码为 `"cn"`；
  港美走独立 V1 管线（`hk/income`、`us/income`），未接入 rptdom 的 `alt.bssaa` 宽表。
- **过渡通路**：provider 可经 `eval_result("return store.get(...)")` 直读域宽表（字段为
  USGAAP 驼峰 + `CreatedAt/UpdatedAt/catalog` 元数据键，需清洗与列名映射）。
- **修复建议**：script 层为港美补 `xs:catalog` 暴露函数，重跑 `extract_from_scripts.py`。

### S-3 `bonus.query_count_window` 恒返 0 — `open`

- **症状**：窗口分红计数聚合缺陷，恒返回 0（`disc.bonus` 目录 notes 自认）。
- **绕开**：SDK 的 `dividend.window_stats` 已自行计数绕开。
- **修复建议**：修上游 count 聚合。

---

## 数据面（修复归属：airflow / 数据管线）

### D-1 `000300.INDEX` 停更序列与 `399300.INDEX` 并存 — `open`

- **症状**：直觉别名 `000300.INDEX`（沪深300 常规代码）是**另一只**指数，序列止于
  2024-12-06；真序列在 `399300.INDEX`。误用会拿到两年前的静默错数据。
- **证据**：2026-11-13 双探针对比。
- **绕开**：provider 用 `airflow/catalog/index_registry_live.json` canon 段的别名快照解析
  （`utils/index_canon.py`，`tools/refresh_index_canon.py --check` 为漂移门禁）。
- **修复建议**：上游确认 000300.INDEX 语义，停更序列应废弃或补数。

### D-2 指数 bar `percent` 为百分数、个股为小数 — `worked-around`

- **症状**：指数 quote store 的 `percent=-0.7798` 表示 -0.78%；个股 bar 的 `percent`
  是小数。同类字段跨域口径不一致，混用即 ×100 错位。
- **证据**：2026-11-13，provider 用 `close/prev_close-1` 反推校验后才敢除 100。
- **绕开**：`models/index_historical.py::_to_bar` 归一为小数并做价格反推校验。
- **修复建议**：上游统一为小数口径。

### D-3 `stocks.query_list`（us）单次 ~851k EC — `open`（成本警示，非错误）

- **症状**：美股全表 5194 行单次 eval 消耗 851,224 EC（提示阈值 100k），按次调用不可承受。
- **证据**：2026-11-14 `UserWarning: 本次 eval 消耗 851224 EC`。
- **影响**：任何「全表拉取再过滤」的 provider 实现都要避免按次触发；低成本路径是
  `stocks.industry_members(ind=...)`（单行业仅数十行）。
- **修复建议**：全表类接口走服务端一次取数（如 `moneyflow.board()` 那样的预聚合），或提供
  按代码点查。

---

## 维护约定

- 销账时把状态改 `fixed` 并注明修复 commit/版本；新增缺陷附「证据命令 + 日期」。
- 探测复跑入口：[GAPS.md §5](GAPS.md#5-探测脚本上游变更后重跑)。
