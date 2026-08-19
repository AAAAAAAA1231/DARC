# 建筑施工图自动生成器

本机工具。输入建筑物性质、面积、层数、单层面积、柱网、结构形式等需求，按规则自动生成 **建筑、结构、给排水、电气、采暖、通风、消防** 全套 A3 图纸（SVG + DXF）。

## 用法

双击 `dist/ShiGongTu.exe`，或在本目录执行：

```bash
pip install -r requirements.txt
python run.py
```

浏览器打开 http://127.0.0.1:8796

命令行出一套示例图：

```bash
python run.py --cli --type 办公楼 --floors 6 --floor-area 1200 --name 示例办公楼
```

Windows 可把本目录打成 `ShiGongTu.exe`（GitHub Actions 工作流 `.github/workflows/build-shigongtu.yml`，或本机 `pyinstaller --noconfirm ShiGongTu.spec`）。

## 会做什么

- 按办公楼 / 住宅 / 商业 / 厂房 / 学校 / 医院 / 酒店模板排布柱网、房间、门窗、楼梯电梯
- 出各层平面、总图、立面、剖面、楼梯详图、门窗表、设计说明
- 结构：基础、柱网/剪力墙、梁板示意
- 水、电、暖、风、消防系统图与平面点位（消火栓、喷淋、报警、防排烟）
- 导出图纸目录、每张 SVG（可打印成 PDF）和 CAD 用 DXF，打包 ZIP

## 不会做什么

- **不是**施工图审查合格的正式施工图，不能直接报建或施工
- 不做结构内力计算、水电暖负荷计算、消防水量计算
- 不替代注册建筑师、结构师及其他专业负责人签章
- 节点大样、做法表、图集索引需深化时补全

生成稿须各专业审核后再使用。
