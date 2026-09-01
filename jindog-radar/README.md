# 金狗雷达（JinGouRadar）

Windows 可执行文件：`dist/JinGouRadar.exe`

按加密狗 [@jiamigou](https://x.com/jiamigou/status/2075057589457735949) 长文
《Robinhood Chain 「Memecoin」打新--保姆级教程（全流程）》里的**发现顺序**做公开数据筛选。

## 筛选顺序（不可跳步）

1. **双监控发现**：Dexscreener New Pairs + NOXA Fun Trending。
2. **年龄窗口**：优先 < 30 分钟，观察带 5–60 分钟；太老机会小。
3. **叙事快筛**：Twitter/TG 是否存在；Robinhood / GME / 官方 / 猫狗叙事。
4. **数据确认**：成交量上升、买入主导、早期市值（几万到百万美金）。
5. **链上核查**：持仓是否过度集中、流动性相对市值是否健康。
6. **聪明钱确认**：去 GMGN 人工看聪明钱与地毯警告。

程序只做这六步过滤并打标（金狗候选 / 观察 / 回避）。开仓仓位和止盈止损不在顺序里。

## 明确不会做的事

- 不保存助记词 / 私钥
- 不自动买入（原文：自动买入风险极高，建议先关闭）
- 不构成投资建议

## 运行

双击 `JinGouRadar.exe`，会打开本地页面 `http://127.0.0.1:17890/`。关掉黑色窗口即停止。

源码编译：

```bash
cd jindog-radar
go test ./...
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o dist/JinGouRadar.exe
```
