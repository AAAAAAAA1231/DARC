# 工作台

把三个原来的桌面工具放进**同一个 exe**：

1. **50 倍雷达**（新场子 / 新叙事 / 浅开盘）
2. **三大联赛胜负推理**（西甲 / 德甲 / 意甲）
3. **链上雷达的合约模块**（永续信号、1R 仓位、波动自适应止损）

## 下载

双击即开浏览器，不是压缩包：

**https://github.com/AAAAAAAA1231/DARC/releases/latest/download/GongZuoTai.exe**

关掉那个黑窗口等于退出。未签名 exe 可能被 SmartScreen 拦截，选「仍要运行」。

本机调试：

```bash
cd desk-suite
pip install -r requirements.txt
python desk_suite.py
```

侧栏三个按钮就是三个模块。合约分析仍走原来的风控：阈值 0.22、止损约 1.8 ATR、单笔风险 0.5%、同屏最多 3 仓。
