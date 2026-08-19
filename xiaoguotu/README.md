# 建筑效果图生成器

按 3ds Max + V-Ray 效果图常用参数，生成室内、大楼外观、整体平面、鸟瞰、夜景。

## Windows EXE（下载就能用）

https://github.com/AAAAAAAA1231/DARC/blob/cursor/xiaoguotu-render-2d31/xiaoguotu/dist/XiaoGuoTu.exe

直接下载：https://github.com/AAAAAAAA1231/DARC/raw/cursor/xiaoguotu-render-2d31/xiaoguotu/dist/XiaoGuoTu.exe

双击 `XiaoGuoTu.exe`，不要关黑窗口，浏览器打开 http://127.0.0.1:8798

## 源码运行

```bash
pip install -r requirements.txt
python run.py
```

选模式即可出图。相机（焦距/眼高/两点透视/ISO）、VRaySun（方位角高度角）、GI 采样和出图尺寸已按效果图公司常用设置填好。可导出 PNG，并下载 3ds Max / V-Ray 参数单。

实时预览是实时光栅效果图，不是照片级终渲。
