# 工程进度（横道图）

本机日常进度工具。维护 WBS、填报完成百分比和施工日志，导出 Excel / PNG 横道图。

## 用法

双击 `dist/JinDu.exe`，或在本目录执行：

```bash
pip install -r requirements.txt
python run.py
```

浏览器打开 http://127.0.0.1:8793

数据保存在本机 `data/workspace.json`，不上传网络。

## 为什么下载/打开 EXE 会提示病毒？

这是**误报**，不是程序里带了木马。

`JinDu.exe` 用 PyInstaller 把 Python 打成**未签名**的单文件。Chrome / Edge / Windows SmartScreen，以及国内 360、腾讯电脑管家，经常把这类包装器判成“木马/病毒”。GitHub 的 `raw` 直链下 `.exe` 也更容易被浏览器拦。

可自行核对：

- 源码就在本目录，不含下载器、键盘记录、对外发包
- EXE 由 GitHub Actions 公开构建（工作流 `Build JinDu EXE`），不是私下塞进去的文件
- 不想用 EXE：本机安装 Python 后执行上面的 `python run.py`，效果相同，一般不会被拦截

若已核对源码仍要用 EXE：在 SmartScreen 选「更多信息 → 仍要运行」，或从该次 Actions 的 Artifacts 下载 `JinDu-windows`，不要从不明网盘转存。长期给别人用需要购买代码签名证书，未签名软件无法从根上消除这类提示。

## 会做什么

- 房屋建筑 / 市政道路 / 装饰装修 / 钢结构厂房 进度模板，按合同开工日展开计划
- 完成-开始（FS）前置、滞后、总时差、关键线路
- 对照今天计算总进度、SPI、滞后项
- 施工日志（天气、人数、完成、问题、明日计划）
- 导出 Excel 横道图（色块按日/周）、任务表、日志；或导出 PNG

## 不会做什么

- 不是 Project / P6，不做资源均衡和挣值全套
- 横道按日历天，不自动扣节假日（可在任务里把工期改成日历天）
