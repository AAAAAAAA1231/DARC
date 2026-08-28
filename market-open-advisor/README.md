# 开盘建议（OpenAdvisor）

双击打开后，按**当前打开时刻**、按**交易场所**给出操作建议。

建议取值是：用该场所指数的历史日收益，在「与今天相同的趋势状态」里做条件自助抽样；这个模型在 **100 亿次独立模拟** 下的结果，就是经验分布的解析极限（大数定律）。程序启动时再跑数百万次流式蒙特卡洛核验，确认数值偏差。

## 个股

每个交易场所下列出该场所的活跃个股（A 股按成交额从公开行情列表取，港股/美股用成分样本），**每只股票单独给出**偏多 / 观望 / 偏空。默认每场所 40 只；可用 `--per-market 80` 加大。


- 上交所主板（上证指数）
- 深交所主板（深证成指）
- 创业板（创业板指）
- 科创板（科创50）
- 北交所（北证50）
- 港交所（恒生指数）
- 美股（纳斯达克100）

## 数据

同花顺展示的是交易所公开成交。本工具读取 Yahoo / 腾讯 / 新浪 / 东方财富的公开行情（同一套交易所打印），**不是**同花顺 iFinD / 同花顺客户端的授权接口，也没有去破解或扫描同花顺。打开时按可用性自动切换源。

## Windows 下载（只要 .exe，不要 zip）

直接下载这个文件，双击运行：

https://raw.githubusercontent.com/AAAAAAAA1231/DARC/cursor/market-open-advisor-7a8a/market-open-advisor/release/OpenAdvisor.exe

仓库里的路径是 `market-open-advisor/release/OpenAdvisor.exe`（约 5MB，Go 原生程序）。黑窗口显示拉行情进度，随后浏览器按交易场所列出每只股票的建议。

不要下 GitHub 仓库的 Source zip，也不要下 Actions 产物（GitHub 会把产物再打成 zip）。

Linux 可运行：

```bash
cd market-open-advisor
python3 -m pip install -e .
python3 -m market_advisor --once
python3 -m market_advisor --once --html /tmp/open-advisor.html
python3 -m market_advisor
```

## 说明

这是量化研究工具，**不是投资建议**，也不是收益承诺。100 亿次模拟提高的是抽样估计的精度，不能消灭模型风险、数据风险和市场风险。
