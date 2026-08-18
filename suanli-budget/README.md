# 算力中心预算编制

本地离线工具：输入算力目标（PFLOPS 或卡数）以及 GPU / CPU / 网络 / 机房等基础数据和单价，输出含税总投资、单卡造价、每 PFLOPS 造价、年电费，并下载 Excel / Word 预算书。

默认单价是 **2026 年公开渠道参考价**，界面里都可以改，改完重新生成即按你的询价出总价。

## Windows EXE

https://github.com/AAAAAAAA1231/DARC/blob/cursor/suanli-budget-f8d9/suanli-budget/dist/SuanliBudget.exe

直接下载：https://github.com/AAAAAAAA1231/DARC/raw/cursor/suanli-budget-f8d9/suanli-budget/dist/SuanliBudget.exe

双击后不要关黑窗口，浏览器打开 http://127.0.0.1:8791

## 源码运行

```bat
cd suanli-budget
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## 测算口径

- 按整机采购：卡数向上取整到整台（默认 8 卡/台）。
- FP16 PFLOPS = 卡数 × 单卡 TFLOPS / 1000，未扣集群效率和稀疏。
- 整机价模式下 CPU/内存默认不重复计列。
- 增值税、预备费、安装/软件按比例计列；年电费单列不进建设投资。

本工具辅助投资估算，不替代正式概预算或中标合同价。
