# A股量化交易辅助系统

面向**上证主板、深证主板、创业板、科创板**的研究与风控工具：在流动性与上市时间达标的分层股票池上，把趋势、动量、均值回归、波动率、相对强弱等多类信号做**滚动样本外动态加权**，在 **T 日收盘后**给出次日可执行的参考仓位，并输出 **ATR/波动率自适应止盈止损** 与 **收益置信区间**。

系统定位是**概率信号 + 风险控制**，不声称能判断全部个股未来走势，也不是券商下单通道。实盘前必须经过充分模拟盘；仓位上限、单票风险预算始终优先于信号排序。

## 设计约束（已写入引擎，而不是事后检查）

| 规则 | 实现 |
| --- | --- |
| 股票池 | 成交额 / 市值 / 停牌天数 / 上市天数 / ST 过滤，再按流动性或市值分层，限制计算规模 |
| T+1 | 信号 T 收盘 → 委托 T+1 开盘；当日买入的仓位最早下一交易日可卖（T+2 相对信号日） |
| 涨跌停 | 主板 ±10%、创业板/科创板 ±20%、ST ±5%、上市初无涨跌停；一字板成交概率为 0 |
| 最小单位 | 100 股整手 |
| 成本 | 佣金（含最低 5 元）、卖出印花税、过户费、ATR 相关滑点 |
| 集成 | 各方法用滚动样本外代理收益的指数加权 Sharpe 做 softmax 权重，近期失效自动降权 |
| 验证 | Walk-Forward（稳健分数选参，而非样本内最高收益）+ 有限次蒙特卡洛（收益序列 block bootstrap，以及滑点/成交抖动） |
| 风控 | 总仓、单票、板块、持仓只数、流动性参与率；模拟分布可下调仓位与方法权重上限 |

## 安装

```bash
cd ashare-quant
python3 -m pip install -e ".[dev]"
```

默认使用**合成 A 股日线**（含涨跌停、停牌、ST、次新、流动性分层），用于规则验证与演示。把真实日线存成 CSV 后，通过 `--data path.csv` 接入，列名见下文。

## 命令

```bash
# 完整流水线：选股 → 信号 → 回测 → Walk-Forward → 蒙特卡洛 → 报告
python3 -m ashare_quant demo --output ./output

# 分层股票池 / 当日候选 / 样本外验证 / 模拟盘
python3 -m ashare_quant universe
python3 -m ashare_quant signals
python3 -m ashare_quant walkforward
python3 -m ashare_quant paper --days 40

# 研究面板（先跑 demo 再打开）
python3 -m ashare_quant serve --port 8765
```

面板展示股票池规模、动态方法权重、带置信区间的候选表、Walk-Forward 净值与蒙特卡洛回撤分布。

## 真实数据 CSV

至少包含：

```
date,symbol,open,high,low,close,volume,amount,market_cap,float_shares,suspended,limit_status,board,name,listing_date,is_st,benchmark_close
```

- `symbol`：6 位代码（`600000` / `000001` / `300001` / `688001`）
- `board`：`sse_main` | `szse_main` | `chinext` | `star`
- `limit_status`：`normal` | `touch_up` | `sealed_up` | `touch_down` | `sealed_down`
- `benchmark_close`：指数或股票池基准，用于相对强弱

配置见 `config/default.yaml`（成交额阈值、仓位上限、ATR 倍数、Walk-Forward 窗口、蒙特卡洛次数等）。

## 方法与加权

1. **趋势**：快慢 EMA + ADX 强度  
2. **动量**：ROC + RSI  
3. **均值回归**：价格 Z 分数反向  
4. **波动率**：ATR 通道突破 + 波动挤压  
5. **相对强弱**：个股超额基准收益  

每个方法映射到 `[-1, 1]`。权重来自「当日分数 × 次日收益」的滚动样本外表现，半衰期可配；负 Sharpe 会被地板截断并降低权重，避免单一规则把结果写死。

Walk-Forward 在训练段末尾的验证窗上用

`robust_score = Sharpe - 惩罚 × |MaxDD| - 换手惩罚`

选择有限网格参数，再在测试段拼接真正的样本外净值。蒙特卡洛对这段 OOS 收益做 block bootstrap，并对滑点乘数、涨跌停成交概率做有限次扰动；若「回撤差于阈值」的模拟占比过高，则下调总仓、单票风险预算，并收紧单一方法权重上限。

## 测试

```bash
cd ashare-quant
python3 -m pytest tests -q
```

覆盖板块识别、股票池过滤、T+1 冻结、一字板无法成交、印花税仅卖出、ATR 止盈止损非固定点、置信区间、仓位上限、Walk-Forward 与蒙特卡洛校准。

## 免责声明

输出是参考性概率与风险区间，不是投资建议，也不能作为「必涨 / 必跌」的点预测。合成行情只验证规则与流程；接入真实数据后仍须更长样本外与模拟盘，再考虑任何实盘资金。
