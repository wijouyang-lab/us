# 覆盖池与六大投资流派审计 — P5.1

Date: 2026-11-04
Branch: `research/universe-strategy-audit-p51`
Base: `main` at `2355525e143d4ba8c09d2169e4b9f720d2d6315a`
Status: **AUDIT ONLY — no production or dashboard changes in this PR**

## 1. 结论摘要

当前系统不是全市场研究平台，而是一个 **28 家公司的固定样本**：

```text
28 companies
28 unique SEC CIKs
12 SEC/industry labels
21 NON_FINANCIAL
 2 BANK
 3 INSURANCE
 2 REIT
```

其中 P4.6 研究结果：

```text
SCORE_READY                 10
NOT_READY                   11
INDUSTRY_MODEL_NOT_READY     7
```

六流派没有全部具备可验证的评分/回测。当前可复用的真实状态是：

| 流派 | 当前状态 | 可否进入实际研究 |
|---|---|---|
| Value | **BLOCKED** | 否，缺当前价格和授权股本/市值输入 |
| Quality | **PARTIAL / RESEARCH_ONLY** | 有限，可做当前快照诊断，不可做已验证横截面排名 |
| GARP | **PARTIAL / BLOCKED** | 部分，成长指标可用，PEG/前瞻估值不可用 |
| Trend | **PARTIAL / BLOCKED** | 仅诊断，PIT 覆盖门槛未通过 |
| Dividend | **PARTIAL** | 10 个非金融股息分可用；全市场事件覆盖未完成 |
| Hedge | **BLOCKED** | 否，缺历史对冲成本/期权数据与统一回测 |

Dashboard 尚未有六流派总览；本报告先给出实现契约，下一批再开发。

## 2. 28 家公司从哪里来

### 2.1 硬编码样本，不是全市场

来源：

```text
tools/investment_research/ingest_sample.py
SAMPLE = [ ... 28 entries ... ]
```

样本通过：

```text
SEC company_tickers / Submissions
→ fetch_company()
→ data/sec/cache/companyfacts_<CIK>.json
→ docs/research/sec_fundamentals_snapshot.json
```

生成。每家公司有：

- ticker；
- 唯一 CIK；
- SEC CompanyFacts；
- SEC Submissions 行业/SIC；
- CompanyFacts SHA-256；
- facts_count。

因此 **28 是人工选择的跨行业大中盘样本**，不是：

- S&P 500 全成分；
- 全美股；
- 市值排序；
- 可自动扩展的 universe。

### 2.2 行业分组

| SEC/行业标签 | 公司数 | Tickers |
|---|---:|---|
| Software | 4 | MSFT, GOOGL, CRM, ADBE |
| Technology Hardware | 1 | AAPL |
| Semiconductor | 1 | NVDA |
| Retail | 3 | AMZN, HD, MCD |
| Industrial/Manufacturing | 4 | NKE, CAT, HON, RIVN |
| Unmapped | 1 | UNP（SIC 4011 铁路） |
| Energy | 2 | XOM, CVX |
| Utilities | 2 | NEE, DUK |
| Healthcare | 3 | JNJ, PFE, MRNA |
| Insurance | 3 | UNH, BRK.B, MET |
| Banking | 2 | JPM, BAC |
| REIT | 2 | PLD, O |

P4.6 的治理分类：

```text
NON_FINANCIAL 21
BANK           2
INSURANCE      3
REIT           2
```

银行、保险、REIT **没有**套用非金融 FCF 模型：

```text
BANK:                 BANK_MODEL_NOT_READY
INSURANCE:            INSURANCE_MODEL_NOT_READY
REIT:                  REIT_FFO_REQUIRED / REIT_MODEL_NOT_READY
```

### 2.3 为什么只有 28 家

1. `SAMPLE` 是静态列表；
2. 没有 `company_tickers.json → 全市场` 的批量 ingest；
3. 没有 SEC bulk Financial Statement Data Sets 管道；
4. 当前 `companyfacts` 缓存只覆盖这 28 个 CIK；
5. P4.1/P4.6 的股息研究以这 28 家为边界；
6. Dashboard 已上线部分只覆盖 CAT/BAC 两条定向股息事件。

扩展不是“改一个数字”，而是需要新增：

- universe registry；
- 批量 SEC 下载与断点恢复；
- 行业/SIC 映射；
- 价格/股本/公司行动数据；
- PIT 历史成员与退市处理；
- 分批验证与质量门禁。

## 3. 现有数据资产

### 3.1 SEC 官方、免费、可复现

已在仓库使用或可复用：

```text
SEC company_tickers.json
SEC Submissions API
SEC CompanyFacts API
SEC 8-K / EX-99.1
SEC Financial Statement Data Sets（季度 ZIP）
```

优点：

- 官方一手来源；
- 无 API 付费；
- CIK/accession/文件哈希可追溯；
- 适合基本面、行业、股息公告。

限制：

- SEC 要求真实 User-Agent 和公平访问限速；
- CompanyFacts 单公司请求不适合直接全市场暴力抓取；
- bulk 数据需要本地缓存、分批和失败恢复；
- 财报口径、期间匹配、重述仍需清洗。

### 3.2 免费价格和 PIT 数据

现有研究链路已使用：

```text
Stooq / Yahoo daily prices
Internet Archive Wayback（退市/历史价格兜底）
```

优点：无需付费 key。
限制：

- 退市股票覆盖不完整；
- Yahoo/Stooq 条款和可用性不稳定；
- 未调整 OHLC 与拆股/股息处理需额外验证；
- Wayback 快照不保证完整；
- 免费历史期权链基本不可得。

仓库已有 10Y PIT 诊断门槛：

```text
member-session coverage 91.68%  (gate 95%)
ticker coverage          84.23%  (gate 98%)
704 historical tickers, 498 usable
1,038,059 rows, 2,453 signal dates
```

因此现有 10Y 结果只能作为诊断，不能作为生产排名。

## 4. 六大流派逐项审计

### 4.1 Value

**数据需求**

- 当前价格；
- 当前/历史股本；
- 市值、企业价值；
- PE/PB/EV-EBIT/EV-EBITDA；
- FCF yield / earnings yield；
- 安全边际。

**现有指标**

28 家公司的 SEC 基本面快照中：

```text
pe_ttm       DATA_BLOCKED 28/28
pb           DATA_BLOCKED 28/28
ev_ebit      DATA_BLOCKED 28/28
market_cap   DATA_BLOCKED 28/28
enterprise_value DATA_BLOCKED 28/28
fcf_yield    DATA_BLOCKED 28/28
```

原因明确记录：

```text
authorized market quote/current shares not supplied
```

DCF 仅有情景估算，且 `value_per_share = null`（shares 缺失），不是投资目标或买卖信号。

**状态**

```text
VALUE_DATA_BLOCKED
SCORE_READY = 0/28
BACKTEST = NOT_VALIDATED
```

**免费补齐路径**

- SEC `dei:EntityCommonStockSharesOutstanding`；
- SEC CompanyFacts 的股东权益/债务；
- 免费日线收盘价（Stooq/Yahoo）；
- 所有价格标注来源、抓取时间、PIT 可用时间。

不能把 `DCF scenario estimate` 当作 Value 评分。

### 4.2 Quality

**数据需求**

- 毛利率、营业利润率、净利率；
- ROE、ROIC；
- FCF conversion；
- 债务/EBITDA；
- 收入/盈利稳定性；
- 5 年历史。

**现有指标**

28 家公司的 Quality 指标状态：

```text
OK                    193
INSUFFICIENT_DATA      91
NOT_APPLICABLE         24
```

核心指标示例：

```text
ROE              OK 23 / INSUFFICIENT 4 / N/A 1
FCF conversion   OK 21 / INSUFFICIENT 7
```

但 **10 个核心 Quality 指标全部 OK 的公司只有 4 家**：

```text
AAPL, CRM, ADBE, AMZN
```

**状态**

```text
QUALITY_DATA_PARTIAL
QUALITY_SCORE = NOT_VALIDATED
BACKTEST = NOT_VALIDATED
```

**结论**

Quality 是六流派中当前基本面数据最完整的一个，但还不是已验证可排名的策略。可以进入“当前快照诊断”，不能进入“完整历史质量组合排名”。

### 4.3 GARP

**数据需求**

- revenue / EPS / FCF growth；
- 3Y/5Y CAGR；
- 前瞻 EPS 或合理增长预期；
- PEG 或增长调整估值；
- 价格/股本。

**现有指标**

28 家公司的 GARP 指标状态：

```text
OK                    195
INSUFFICIENT_DATA      70
DATA_BLOCKED           28
NOT_APPLICABLE         15
```

具体：

```text
revenue_growth  OK 27 / INSUFFICIENT 1
eps_growth      OK 24 / INSUFFICIENT 2 / N/A 2
PEG             DATA_BLOCKED 28/28
```

`PEG` 原因：

```text
forward EPS estimates not licensed
```

**状态**

```text
GARP_DATA_PARTIAL
GARP_SCORE = NOT_READY
BACKTEST = NOT_VALIDATED
```

**结论**

不能用“revenue growth + trailing PE”冒充 GARP；前瞻 EPS 缺失时必须保持 blocked，不能自行编造增长预期。

### 4.4 Trend

**数据需求**

- 复权/未复权 OHLCV；
- 拆股/股息处理；
- 20D/60D momentum、ATR、realized vol、RSI、MA slope；
- PIT 历史成员；
- 交易成本、滑点、执行延迟；
- 样本外与 walk-forward。

**现有资产**

```text
tools/research/multi_strategy_comparison.py
tools/research/low_frequency_atr_strategy.py
quant_factor_price_history.csv
quant_factor_validation_report.json
docs/UNIFIED_MULTI_STRATEGY_RESEARCH_STATUS.md
trend_v1_daily_*.csv
trend_v1_signals_*.csv
```

10Y 诊断：

```text
498 tickers
1,038,059 rows
2,453 signal dates
24 non-overlapping test observations
```

但质量门禁失败：

```text
member-session coverage 91.68% < 95%
ticker coverage          84.23% < 98%
```

且价格未完全复权、历史成员退出日期不完整，存在 survivorship 风险。

**状态**

```text
TREND_DIAGNOSTIC_ONLY
TREND_BACKTEST = BLOCKED_BY_PIT_COVERAGE
```

**结论**

Trend 可以在现有免费数据上继续做研究，但只能作为诊断/探索；不能进入生产策略排名。优先补：

1. 拆股/股息复权；
2. 历史成员进入/退出日期；
3. 退市股价格；
4. 交易成本与执行模型。

### 4.5 Dividend

**数据需求**

- SEC 8-K / EX-99.1；
- XBRL DPS；
- 股息宣告、登记日、支付日、除息日；
- 拆股调整口径；
- 历史连续性；
- 全市场事件覆盖。

**现有资产**

P4.1/P4.6：

```text
28 companies
22 dividend payers
10 SCORE_READY
11 NOT_READY
 7 INDUSTRY_MODEL_NOT_READY
```

P4.5 定向事件：

```text
CAT: VERIFIED common $1.63, previous $1.51, +8%
BAC: VERIFIED common $0.32, previous not disclosed, +14%
BAC preferred $1.75: excluded
```

**阻塞**

```text
DPS split basis verified: 0/28
581-accession full scan: NOT_RUN
verified dividend events: 2 (CAT/BAC only)
Dividend event coverage: TARGETED_SAMPLE
```

**状态**

```text
DIVIDEND_SCORE = 10/28 non-financial ready
DIVIDEND_EVENT_COVERAGE = TARGETED_SAMPLE
DIVIDEND_FULL_MARKET = NOT_READY
```

**结论**

不能把 CAT/BAC 两条定向事件包装成全市场股息覆盖。扩展优先级：

1. 继续用 SEC 官方 8-K/EX-99 做全量事件抽取；
2. 拆股/DPS share basis 验证；
3. 扩充到更多股息公司；
4. 通过后才允许 Dashboard 展示全市场股息。

### 4.6 Hedge

**数据需求**

- 指数/ETF 历史价格；
- VIX/波动率；
- beta、相关性、跟踪误差；
- 对冲工具（SPY/期权）价格；
- 借券、融资、交易成本；
- 期权历史链或可复现的替代数据；
- 对冲后净值、回撤、换手。

**现有资产**

Strategy Lab 已有概念入口：

```text
defensive / volatility target
index hedge
```

但没有：

- 统一对冲回测；
- 完整期权历史；
- 借券/融资/执行成本；
- 可核验的策略级收益序列。

实时 `scan_us_option_engine.py` 的 Yahoo 期权链只能用于当前候选，不是历史回测数据。

**状态**

```text
HEDGE_DATA_BLOCKED
HEDGE_BACKTEST = NOT_READY
```

**结论**

Hedge 不应在当前阶段显示评分或收益。先把“防御/波动率目标”和“指数对冲”拆开：

- 防御/波动率目标：可用免费指数价格做研究；
- 期权对冲：没有免费可靠历史期权数据前保持 BLOCKED。

## 5. Dashboard 六流派总览契约

下一批应新增独立数据文件，例如：

```text
dashboard/data/strategy_styles.json
```

字段：

```json
{
  "metadata": {
    "generated_at": "...",
    "source_commit_sha": "...",
    "scope": "RESEARCH_SAMPLE_28",
    "coverage_note": "..."
  },
  "styles": [
    {
      "id": "value",
      "name": "Value",
      "coverage_count": 28,
      "data_ready_count": 0,
      "score_ready_count": 0,
      "blocked_count": 28,
      "status": "BLOCKED",
      "last_updated": "...",
      "sources": ["SEC CompanyFacts", "free price snapshot"],
      "blocker": "current price/shares inputs missing"
    }
  ]
}
```

规则：

- 没有数字评分时 `score_ready_count = 0`，不得显示伪分数；
- `BLOCKED`、`NOT_READY`、`PARTIAL`、`RESEARCH_ONLY` 明确区分；
- 每个流派显示覆盖数、数据就绪数、评分就绪数、阻塞数；
- 六流派卡片不参与生产评分；
- Dividend 明确 `TARGETED_SAMPLE` 和 581 `NOT_RUN`；
- Hedge 明确没有历史期权数据前不展示收益；
- 前端只读，独立加载，不影响主 Dashboard。

建议入口放在 Quant 与 Dividend Quality 附近，桌面三列/两列，手机单列；不允许把 `0` 当作“就绪”。

## 6. 扩展优先级

### P1 — Dashboard 六流派状态总览

- 只展示审计状态；
- 不显示伪造评分/收益；
- 新增 JSON、前端和测试；
- 依赖本报告的状态表。

### P2 — 28 → 100 家免费数据扩展

- SEC company_tickers + Submissions 批量身份；
- SEC CompanyFacts 批量缓存；
- 行业/SIC 注册表；
- 缺失数据保持 NOT_READY；
- 先不发全市场评分。

### P3 — Value/Quality/GARP 当前快照

- 补免费价格和 SEC 股本；
- 先做当前截面的可解释指标；
- 不做历史回测排名。

### P4 — Trend PIT 修复

- 复权价格；
- 成员进入/退出；
- 退市价格；
- 95%/98% 门禁通过后再回测。

### P5 — Dividend 覆盖扩展

- 继续 SEC 官方事件；
- 完成 split/DPS basis；
- 逐步扩展样本，不把 CAT/BAC 当全市场。

### P6 — Hedge

- 先做无期权的防御/波动率目标；
- 历史期权数据不可得时保持 BLOCKED；
- 不展示收益。

## 7. 具体文件与数据来源

审计引用：

```text
tools/investment_research/ingest_sample.py
docs/research/sec_fundamentals_snapshot.json  (P4.6 research branch)
data/research/dividend_quality_p41.json       (P4.1 research branch)
data/research/dividend_quality_p46.json       (P4.6 research branch)
docs/research/dividend_quality_p41.md
docs/research/dividend_quality_p46.md
docs/UNIFIED_MULTI_STRATEGY_RESEARCH_STATUS.md
docs/STRATEGY_LAB.md
strategy-lab.html
dashboard/data/dividend_quality.json
scripts/export_dividend_quality_dashboard.py
tools/research/multi_strategy_comparison.py
tools/research/low_frequency_atr_strategy.py
quant_factor_validation_report.json
```

数据来源：

```text
SEC company_tickers.json
SEC Submissions
SEC CompanyFacts
SEC 8-K / EX-99.1
SEC Financial Statement Data Sets（建议用于扩展）
Stooq / Yahoo daily prices（免费，需校验）
Internet Archive Wayback（免费退市兜底）
```

不使用：

```text
paid market data APIs
paid option history
broker/account data
```

## 8. 测试与验证

本报告不修改生产代码、Dashboard 或评分。现有相关测试：

```text
tests/test_dividend_quality_dashboard.py                 15 passed
tests/test_multi_strategy_comparison.py                   7 passed
tests/test_low_frequency_atr_strategy.py                   6 passed
```

P4.6 研究分支仍以以下状态为准：

```text
10 SCORE_READY
11 NOT_READY
7 INDUSTRY_MODEL_NOT_READY
```

本报告的数值来自已提交研究 JSON，不从新闻、价格或人工文本重算。

## 9. 明确阻塞

1. **Value**：缺授权当前价格/股本；不能计算估值。
2. **GARP**：缺前瞻 EPS；PEG 全部 blocked。
3. **Trend**：PIT 覆盖 91.68%/84.23%，低于 95%/98%；不能生产化。
4. **Dividend**：581 全量未执行；DPS share basis 0/28；仅 CAT/BAC 已验证。
5. **Hedge**：无免费可靠历史期权链和完整对冲成本。
6. **覆盖**：28 是固定人工样本，不是全市场。
7. **Dashboard**：目前只有 Dividend Quality 定向样本，没有六流派总览。

## 10. 结论

这轮审计的结论不是“六流派都可用”，而是：

```text
Quality/部分 Dividend: 可做当前快照研究
Value/GARP/Hedge:       数据或估值输入 blocked
Trend:                  诊断可用，PIT 验证 blocked
28:                     人工样本，不是全市场
```

下一步应先实现 **只读六流派状态总览**，再按 P2–P6 分批扩展；在数据门槛通过前，任何流派都不能显示伪评分、伪收益或“全市场完成”。
