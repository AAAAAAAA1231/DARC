# 三大联赛胜负推理

双击 `三大联赛胜负推理.exe`（需联网），等待几分钟，窗口会列出西甲 / 德甲 / 意甲近期未赛场次的：

- 90 分钟赛果
- 最终结果与比分
- 主胜 / 平 / 客胜 概率

程序会自动综合历史实力、主客场、伤停和赛前网络信息。结果仅供观赛参考。

Windows 重新打包：`pip install numpy pyinstaller && pyinstaller --noconfirm football_predictor.spec`
