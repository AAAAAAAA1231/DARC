# Fifty-X Radar

按最近几个月能核验的 50 倍样本，扫描 **该关注的新场子、新叙事和新盘**。

核心规则只有一条：

> 新场子刚开张 + 独占叙事 + 极浅开盘；能多活几天的，还要有上所或持续收费。

这不是买卖信号，更不是投资建议。50 倍发生在开盘段，不发生在市值过亿之后。

## 有没有 exe？

**没有现成的官网安装包。** 这是一个 Python 工具，仓库里不托管 `.exe` 文件。

Windows 想下 exe，等 GitHub Actions 打好包：

1. 打开 [Actions：Fifty-X Radar Windows exe](https://github.com/AAAAAAAA1231/DARC/actions/workflows/fiftyx-radar-windows.yml)
2. 点最新一次成功的绿色运行
3. 底下 Artifacts 里下载 **FiftyXRadar-windows**
4. 解压后运行 `FiftyXRadar.exe`（双击会弹出黑窗口扫一遍；也可在 cmd 里加 `--html report.html`）

第一次打开 Actions 如果还在排队，等几分钟。杀毒软件偶尔会拦 PyInstaller 打包的未签名 exe，那是误报，不是从商店分发的安装程序。

本机已有 Python 的话，不必等 exe：

```bash
cd fiftyx-radar
python3 -m radar
```

常用参数：

```bash
# 终端名单
python3 -m radar

# JSON
python3 -m radar --json

# 写成网页
python3 -m radar --html report.html

# 生成本地页（默认 http://127.0.0.1:8765/fiftyx-radar-report.html）
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
