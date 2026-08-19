# 灯具选型（离线 EXE）

Windows 双击 `dist/DengJu.exe`，浏览器打开 **http://127.0.0.1:8801**。不要关掉黑窗口。

下载（本分支 raw 链接，CI 打出 EXE 后会提交到 `dengju/dist/DengJu.exe`）：

https://github.com/AAAAAAAA1231/DARC/raw/cursor/dengju-xuanxing-2d31/dengju/dist/DengJu.exe

## 输入

- 手填：进深 / 开间 / 层高 / 目标照度 / 维护系数
- 中文：如 `普通办公室 7.2x9.0 层高2.8 300lx`
- CAD：闭合 LWPOLYLINE 房间轮廓（.dxf）
- PDF：抽取文字中的尺寸与房间类型

## 算法

利用系数法（GB 50034 思路）：

`N = E · A / (Φ · UF · MF)`

并校核：平均照度、LPD、UGR/Ra 目录匹配、间距与 SHR。应急灯按疏散口/通道示意点位（GB 51309 示意，非点照度计算）。

本工具**不是**逐点照度软件（DIALux），不能替代电气专业盖章设计。

## 开发

```bash
cd dengju
python -m pip install -r requirements.txt
python run.py
python -m pytest tests -q
```
