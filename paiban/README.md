# 装修排版神器

本机离线工具。根据地砖、墙砖、吊顶、家具做法自动排版，并按 GB 50210 / GB 50327 / 常用施工工艺校核边砖、龙骨间距、家具通道。输入支持 **CAD（DXF）**、**PDF**、**语言描述**。

## Windows EXE（下载就能用，不用联网）

https://github.com/AAAAAAAA1231/DARC/blob/cursor/zhuangxiu-paiban-2d31/paiban/dist/PaiBan.exe

直接下载：https://github.com/AAAAAAAA1231/DARC/raw/cursor/zhuangxiu-paiban-2d31/paiban/dist/PaiBan.exe

双击 `PaiBan.exe`，不要关黑窗口，浏览器打开 http://127.0.0.1:8799

## 源码运行

```bash
pip install -r requirements.txt
python run.py
```

## 会做什么

- 地砖：正铺 / 工字错缝 / 斜铺，自动偏移避免边砖小于整砖 1/3
- 墙砖：四面展开，门洞套割，非整砖提示放阴角
- 吊顶：石膏板错缝 + 轻钢龙骨（主龙骨≤1m、次龙骨 300～400、吊杆距墙≤300）或铝扣板；灯位与检修口
- 家具：按房间类型布置并校核通道、沙发茶几距
- 导出 SVG / DXF / 工程量，全部本机计算

## 不会做什么

- 不替代施工图会审和现场放线
- 复杂异形房间以 CAD 外包矩形近似
- 规范正文请以正式文本为准
