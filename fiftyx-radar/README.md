# Fifty-X Radar

按最近几个月能核验的 50 倍样本，扫描 **该关注的新场子、新叙事和新盘**。

核心规则只有一条：

> 新场子刚开张 + 独占叙事 + 极浅开盘；能多活几天的，还要有上所或持续收费。

这不是买卖信号，更不是投资建议。50 倍发生在开盘段，不发生在市值过亿之后。

## 下载 exe

现在三个工具在**同一个工作台**里（50 倍雷达 / 三大联赛 / 合约分析）：

**https://github.com/AAAAAAAA1231/DARC/releases/latest/download/GongZuoTai.exe**

双击后浏览器打开，左侧切换模块。只要雷达源码：

```bash
cd fiftyx-radar
python3 -m radar
```

常用参数：

```bash
# 默认：扫完后打开浏览器
python3 -m radar

# 只要终端名单
python3 -m radar --text

# JSON
python3 -m radar --json

# 写成网页，不打开浏览器
python3 -m radar --html report.html

# 本地 http 页（默认 http://127.0.0.1:8765/fiftyx-radar-report.html）
python3 -m radar --serve

# 只扫部分链
python3 -m radar --networks robinhood,hyperevm,bsc,base
```

## 分数怎么来的

每条最多 100 分，四块各 25 分：

| 块 | 在找什么 |
|---|---|
| 场子 | 新链（Robinhood、HyperEVM 等）、发射台（Pump.fun、Four.meme、Pons、Clanker）、池子是否还在开盘窗口 |
| 叙事 | 发射台自己的币、文化事件、KOL、RWA 缠绕；仿盘/Baby Doge 类扣分 |
| 结构 | 市值大约 $15 万–$2000 万、浅池、高换手 |
| 支柱 | 成交还在、地址数还在、活过了前 3 天 |

- **≥72**：重点关注
- **55–71**：值得跟踪
- 市值已经很大：标「已过大」，不是开盘段买点
- 稳定币、无量盘、极浅到像骗局：降权或剔除

数据来自 GeckoTerminal（各链趋势池/新池）和 DexScreener（付费推广榜，只当热度补充）。

## 测试

```bash
cd fiftyx-radar
python3 -m unittest tests.test_radar -v
```
