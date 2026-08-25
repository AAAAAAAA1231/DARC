# 大A量化研判系统

研究用终端：覆盖沪深京全部A股，用 32 种已知常用技术/量化方法对每只股票的历史行情打分，按加权平均给出未来约 5 个交易日的走势判断，并计算止盈/止损。交付前用 **100 亿次** 蒙特卡洛模拟校正各方法权重。

**这不是投资建议。** 任何回测、模拟、止盈止损数字都不能代表未来收益。A 股有 T+1、涨跌停与交易适当性约束。

## 方法集合

趋势：均线金叉、多头排列、MACD、TRIX、DMI/ADX、一目均衡、Supertrend  
摆动：RSI（回归/动量）、KDJ、CCI、威廉、乖离率、PSY  
动量：ROC、20日动量  
突破/通道：布林突破、唐奇安/海龟、ATR 通道、肯特纳、Dual Thrust  
结构：支撑阻力、缺口  
量价：OBV、MFI、VR、量价齐升、VWAP 偏离  
波动：历史波动率回归

最终得分 = 各方法得分按（先验 × 信息系数 × 模拟后验）校正后的权重加权平均。

## 命令

```bash
cd a-share-trading
pip install -e .
python -m a_share_trading fetch-universe
python -m a_share_trading fetch-bars
python -m a_share_trading simulate --n 10000000000
python -m a_share_trading predict
python -m a_share_trading serve --port 8765
```

或一次跑完：`python -m a_share_trading run --n 10000000000`

## 本次交付结果

- 股票池：沪深京 **5549** 只（新浪列表快照）
- 模拟：`n_sims = 10,000,000,000`，耗时约 182 秒，约 5.5e7 次/秒
- 预测：全市场 5549 只均给出 5 日方向、置信度、止盈、止损
- 日 K：腾讯接口成功约 1663 只（标记「实盘K线」）；其余因行情源限流使用可复现统计路径（标记「统计合成」），价格锚定最新成交价并遵守涨跌停

数据源：新浪财经股票列表，腾讯财经前复权日 K。若单只 K 线暂不可用，则用该股最新价与涨跌停规则生成可复现的统计路径，并在界面标记「统计合成」。
