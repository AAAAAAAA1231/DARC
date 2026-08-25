# 西甲 / 德甲 / 意甲 胜负推理桌面程序

覆盖西甲、德甲、意甲的足球比赛结果推理工具。每次预测都会：

1. 用近几年历史赛果拟合 **时间衰减 Dixon-Coles 攻防模型** 与 **Elo**
2. 综合 **主客场优势、近期状态、伤停、天气、赛前舆情**
3. 用最近赛果做 **概率校准（历史纠偏）**
4. 若有市场隐含概率，再做一次融合纠偏
5. 输出 **90 分钟内（含补时）胜平负 + 最可能比分**，以及联赛的 **最终结果**（常规赛无加时，二者一致）

> 预测用于研究与观赛参考，不能保证场场命中，也不构成投注建议。

## 运行（开发）

需要 Python 3.10+（Windows 建议 3.12）。

```bash
cd football-predictor
pip install numpy
python run.py
```

命令行：

```bash
python run.py --cli upcoming
python run.py --cli predict --league laliga --home Valencia --away "Real Betis"
```

联赛参数：`laliga`（西甲）、`bundesliga`（德甲）、`seriea`（意甲）。

## 打包成 Windows EXE

本机（Windows）：

```bash
pip install numpy pyinstaller
pyinstaller --noconfirm football_predictor.spec
```

生成文件：`dist/三大联赛胜负推理.exe`。仓库中的 GitHub Action  
`.github/workflows/build-football-predictor.yml` 会在 Windows runner 上自动打出该 exe。

首次启动会下载历史赛果并拟合模型（需联网），之后缓存约 12 小时。

## 模型要点

| 模块 | 作用 |
|------|------|
| football-data.co.uk 历史比分 / xG / 赔率 | 拟合攻防、主场因子、校准 |
| ESPN 赛程 / 阵容近况 / 伤停 / 新闻 / 赔率 | 实时赛程与市场纠偏 |
| Google 新闻 RSS | 赛前伤停、帅位、战意、德比等舆情 |
| Open-Meteo | 主场降水、风力、气温 |

升班马会并入对应二级联赛历史，避免「没有顶级数据」时退化成联赛平均。
