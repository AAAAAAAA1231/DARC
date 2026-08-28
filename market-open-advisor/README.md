# 开盘建议（OpenAdvisor）

双击打开后，按**当前打开时刻**、按**交易场所**给出操作建议。

建议取值是：用该场所指数的历史日收益，在「与今天相同的趋势状态」里做条件自助抽样；这个模型在 **100 亿次独立模拟** 下的结果，就是经验分布的解析极限（大数定律）。程序启动时再跑数百万次流式蒙特卡洛核验，确认数值偏差。

## 交易场所

- 上交所主板（上证指数）
- 深交所主板（深证成指）
- 创业板（创业板指）
- 科创板（科创50）
- 北交所（北证50）
- 港交所（恒生指数）
- 美股（纳斯达克100）

## 数据

同花顺展示的是交易所公开成交。本工具读取 Yahoo / 腾讯 / 新浪 / 东方财富的公开行情（同一套交易所打印），**不是**同花顺 iFinD / 同花顺客户端的授权接口，也没有去破解或扫描同花顺。打开时按可用性自动切换源。

## Windows 可执行文件

在 Windows 上：

```powershell
cd market-open-advisor
python -m pip install -e . pyinstaller numpy
powershell -File packaging/build_windows.ps1
```

生成 `dist/OpenAdvisor.exe`。打开即算，无需安装 Python。

本仓库的 GitHub Actions 工作流 `Build Market Open Advisor EXE` 会在 Windows runner 上打出同一份 EXE，可从 Actions 产物下载。

Linux 可运行：

```bash
cd market-open-advisor
python3 -m pip install -e .
python3 -m market_advisor --once
python3 -m market_advisor
```

## 说明

这是量化研究工具，**不是投资建议**，也不是收益承诺。100 亿次模拟提高的是抽样估计的精度，不能消灭模型风险、数据风险和市场风险。
