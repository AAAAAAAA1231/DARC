# 摄像头布置生成器（离线 EXE）

Windows 双击 `dist/SheXiangTou.exe`，浏览器打开 **http://127.0.0.1:8802**。不要关掉黑窗口。

下载：

https://github.com/AAAAAAAA1231/DARC/raw/cursor/shexiangtou-buzhi-2d31/shexiangtou/dist/SheXiangTou.exe

## 输入

- 手填：进深 / 开间 / 层高 / 门数量 / 场所 / 覆盖目标
- 中文：如 `办公室 12x8 层高3.0 2个门 要看清人脸`
- CAD：闭合 LWPOLYLINE 房间 + 0.7～2.6 m 短线作门（.dxf）
- PDF：抽取文字中的尺寸与场所

## 布置

- 每个出入口布置迎面/人脸摄像机
- 按 GB 50348 DORI（监视 / 观察 / 识别 / 辨认）半径补点，抽点覆盖 ≥95%
- 室内半球/筒型，室外枪机/球机
- 导出 SVG / DXF / ZIP 与材料表

本工具是布置建议，不能替代安防专项设计与现场复测。

## 开发

```bash
cd shexiangtou
python -m pip install -r requirements.txt
python run.py
python -m pytest tests -q
```
