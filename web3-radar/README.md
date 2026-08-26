# 链上雷达 ChainRadar

Windows 桌面终端，也提供 Mac 安装包（也可在本机用 Python 直接运行）。覆盖合约综合研判、单边快讯、妖币监控、大使招募、打新、高融资空投，以及 OKX 等 Web3 钱包连接与确认队列。

## 功能

1. **合约分析**  
   取 CoinGecko 市值前 100 与币安 USDT 永续的交集（若期货接口被地区限制，自动改用 OKX SWAP / Binance Vision 现货 K 线）。对每标的计算 TD Sequential（TD9/TD13）、谐波（Gartley/Bat/Butterfly/Crab/Cypher/Shark/ABCD）、艾略特简化浪、Ichimoku、MACD、RSI、Supertrend 等约 30 项指标。  
   以初始份额为 Dirichlet 先验，做 **10 亿次** 权重模拟，对收益期望最高的分位做加权平均，得到综合分，结论为 **涨 / 跌 / 观望**，并给出建仓、止盈、止损（ATR 倍数可调）。

2. **单边快讯**  
   监测可能把震荡切成单边的消息：FOMC / CPI / 非农、ETF、监管、黑客、稳定币脱锚、暂停提现。高影响会即时提醒，并给出偏多/偏空和操作备忘。不是投资建议。

3. **妖币监控**  
   聚合 GMGN、Pump.fun、DexScreener。过滤条件：短期买入人数/成交笔数上升、持币地址估计增加、**池子深度 ≥ $1,000,000**。展示链、价格、流动性、来源链接。

4. **大使功能**  
   检索一周内大使招募（Twitter API 或公共镜像）。关键词含 ambassador / 招募大使等。给出优先级与期限，可标记：关注中 / 已申请 / 已参与成功 / 未通过。

5. **打新监测**  
   关键词：打新、新平台、launch、presale、IDO、IEO、launchpad，并结合新池与 Pump.fun 新盘。

6. **空投雷达**  
   DefiLlama 融资数据：融资金额 **> $2000 万**、知名机构数量、是否未发币。按融资、机构、发币预期排序，可标记交互状态。

7. **钱包**  
   浏览器打开连接页，对接 OKX / MetaMask / Rabby 注入钱包。可把空投、打新、妖币、合约信号加入队列。  
   **不会索取助记词或私钥**；链上动作必须在钱包里确认。单笔 USD 上限可配。币安合约无法用链上钱包直接下单，队列仅生成备忘。

## 本地运行

```bash
cd web3-radar
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

浏览器打开 http://127.0.0.1:8787

建议在「设置」中填写 Twitter Bearer Token，以提高大使/打新覆盖率。

## 下载（不要点小箭头）

仓库文件旁的向下箭头对大文件经常没反应。把对应链接复制到浏览器地址栏回车：

**Windows**  
https://github.com/AAAAAAAA1231/DARC/releases/latest/download/ChainRadar.exe  
下完后双击 `ChainRadar.exe`。

**苹果电脑**  
https://github.com/AAAAAAAA1231/DARC/releases/latest/download/ChainRadar-mac.zip  
下完后双击「链上雷达」。要是打不开：按住 Control 再点一下，选打开。

比较旧的 Intel 苹果电脑用：  
https://github.com/AAAAAAAA1231/DARC/releases/latest/download/ChainRadar-mac-intel.zip

## 打包 Windows EXE / Mac 应用

Windows（需 Python 3.12 + MSVC）：

```bash
cd web3-radar
pip install -r requirements.txt
pyinstaller --noconfirm ChainRadar.spec
```

生成 `dist/ChainRadar.exe`。CI 会先用 MSVC 现场编译 PyInstaller 启动器再打包，避免公共启动器被杀毒误杀。首次运行会在 EXE 同目录创建 `data/`。

Mac：

```bash
cd web3-radar
pip install -r requirements.txt pyinstaller==6.14.2
python packaging/make_icns.py
pyinstaller --noconfirm ChainRadar.spec
```

生成 `dist/ChainRadar.app`。数据写在 `~/Library/Application Support/ChainRadar/`。

仓库已配置 GitHub Actions：`.github/workflows/build-web3-radar.yml`，推送后会发布 Windows EXE 与 Mac 应用。

## 测试

```bash
cd web3-radar
python -m pytest tests -q
```

## 风险说明

本工具提供研究与信息聚合，不是投资建议。妖币、打新、合约均有极高风险。自动队列默认仍需钱包二次确认，请勿对未知合约无限授权。
