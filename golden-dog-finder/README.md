# 金狗雷达 · Golden Dog Radar

链上迷因币发掘器。目标不是“预测谁会涨”，而是只保留 **现价买进去、100x 在几何上还做得到** 的新生盘。

> 迷因币默认归零。高分只说明结构像历史百倍入口，不构成投资建议。

## 我给自己定的发掘条件

你没给条件，所以条件是从 2023–2026 年 Solana / pump.fun / Base 百倍盘的**共同入口结构**反推的，而不是拍脑袋：

1. **市值 $5k–$220k**  
   100x 之后仍落在迷因币可实现终点（约 $50 万–$2200 万）。超过这条，再谈 100x 就是在赌异常值。
2. **开盘 6 分钟–36 小时**  
   前 6 分钟是狙击/捆绑抛压带；超过 36 小时还是微型盘，窗口大概率关了。
3. **真实独立买家，而不是成交额**  
   地址在扩散、买盘占比偏多。成交额畸高但买家极少，视为骗量。
4. **曲线或锁 LP**  
   Pump 内盘 18%–72% 是密度最高的第二波区间；外盘必须 LP 锁定，否则涨幅不属于你。
5. **权限干净**  
   铸造/冻结权还在、正在 5 分钟崩盘、或相对典型 $5k 开盘已经 40x+ 的，直接淘汰——从此处再 100x 需要百亿级市值幻想。

七条基因（空间、时间窗、买盘、流动性、安全、动量、点火）加权打 0–100 分。  
**S/A 不是买点保证，是“结构还没把 100x 路堵死”。**

工具会同时给出：现价再涨到 $1.5M / $5M / $20M 分别是多少倍。若到 $5M 都不够 100x，这只狗根本不该出现在雷达中心。

## 数据

公开接口，无需 API key：

- pump.fun 最新成交 / 新开盘 / 讨论热度
- GeckoTerminal 新池 + 趋势池（Solana / Base / BSC）
- DexScreener 资料、助推、社区接管、配对行情
- RugCheck 权限、LP 锁、持仓（只打分靠前的 Solana 候选）

## 启动

```bash
cd golden-dog-finder
python3 -m pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
PYTHONPATH=. python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8787
```

开发时前后端分离：

```bash
PYTHONPATH=. python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8787
cd frontend && npm install && npm run dev
```

浏览器打开 `http://127.0.0.1:5173`（开发）或 `http://127.0.0.1:8787`（生产构建）。

## Windows 桌面版（双击打开）

本机已安装 Microsoft Edge 或 Chrome 即可，无需 Python / Node。

1. 下载 `GoldenDogRadar.exe`
2. 双击运行，会弹出独立窗口（不是浏览器标签）
3. 关闭窗口即退出

自己打包：

```bash
bash golden-dog-finder/desktop/build.sh
# 产物：golden-dog-finder/desktop/dist/GoldenDogRadar.exe
```

GitHub Actions 工作流 `golden-dog-windows` 也会打出同名 exe，在 Actions 的 Artifacts 里下载。

## 测试

```bash
cd golden-dog-finder
PYTHONPATH=. python3 -m pytest tests -q
```
