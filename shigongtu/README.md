# 建筑施工图自动生成器

本机工具。输入建筑物性质、面积、层数、单层面积、柱网、结构形式等，生成建筑 / 结构 / 水 / 电 / 暖 / 风 / 消防全套图纸。

## Windows EXE（下载就能用）

https://github.com/AAAAAAAA1231/DARC/blob/cursor/shigongtu-drawings-2d31/shigongtu/dist/ShiGongTu.exe

直接下载：https://github.com/AAAAAAAA1231/DARC/raw/cursor/shigongtu-drawings-2d31/shigongtu/dist/ShiGongTu.exe

把 `ShiGongTu.exe` 存到任意文件夹，双击打开。不要关掉黑色窗口，浏览器会打开 http://127.0.0.1:8796  
填需求 → 点「生成全套施工图」→ 下载 ZIP。

## 源码运行（可选）

```bash
pip install -r requirements.txt
python run.py
```

## 会做什么

- 按办公楼 / 住宅 / 商业 / 厂房 / 学校 / 医院 / 酒店模板排布柱网、房间、门窗、楼梯电梯
- 出各层平面、总图、立面、剖面、楼梯详图、门窗表、设计说明
- 结构：基础、柱网/剪力墙、梁板示意
- 水、电、暖、风、消防系统图与平面点位
- 导出 SVG（可打印）和 DXF（CAD 打开），打包 ZIP

## 不会做什么

- 不是施工图审查合格的正式施工图，不能直接报建或施工
- 不做结构内力计算、水电暖负荷计算、消防水量计算
- 不替代注册建筑师、结构师及其他专业负责人签章

生成稿须各专业审核后再使用。
