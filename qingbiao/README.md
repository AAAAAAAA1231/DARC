# 清标助手

本地离线运行的建设工程投标文件清标工具，面向**中国大陆内网/单机**环境：不访问境外接口，浏览器只连本机 `127.0.0.1`。

## 做什么

1. **经济标模块**（Excel）  
   - 先上传最高投标限价，再分别上传 **不少于 3 家**（可继续加）投标报价清单。  
   - 按项目编码/名称与限价**逐项**对比：单价相同、单价相近、超限价、漏项。  
   - 各家之间**横向**对比：单价相同/相近、合价合计相同。  
   - 比对 Excel 文件属性（作者、最后修改者、公司、软件版本、创建时间等），提示是否疑似同一账号或同一计算机环境。

2. **技术标模块**（Word / 可选中文字的 PDF）  
   - 先填写概况：层数、建筑面积、结构类型等。  
   - **单份验证**：是否引用过期标准、是否漏引 GB 550xx 强制性通用规范、错别字、与结构类型不匹配、层数/面积与概况不符。  
   - **横向对比**：全文或段落高度一致。

3. **总报告**  
   生成 Word《清标报告.docx》，写明什么标、谁家、什么问题、程度。

## 本机运行（Windows）

**推荐：双击 exe。** 下载后不要关弹出的黑窗口，浏览器会打开 http://127.0.0.1:8790  
上传的标书和报告写在 **exe 同目录的 `data/`**。

- 仓库文件：https://github.com/AAAAAAAA1231/DARC/blob/cursor/qingbiao-local-f8d9/qingbiao/dist/QingBiao.exe
- 直接下载：https://github.com/AAAAAAAA1231/DARC/raw/cursor/qingbiao-local-f8d9/qingbiao/dist/QingBiao.exe
- 也可在 GitHub Actions 产物 `QingBiao-windows` 中下载。

本机有 Python 时也可双击 `run.bat`，或：

```bat
cd qingbiao
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

浏览器打开 http://127.0.0.1:8790

Linux / macOS：

```bash
cd qingbiao
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

上传的标书和报告只写在程序目录下的 `data/`，不会出网。

## 经济标 Excel 要求

清单表头需能识别下列列（名称近似即可）：

- 项目编码 / 清单编码  
- 项目名称  
- 计量单位  
- 工程量  
- **综合单价**（必须）  
- 合价  

封面、汇总表没有单价列时会自动跳过，请传分部分项工程量清单计价表。

## 技术标说明

扫描件 PDF 若无文字层，无法查错别字和雷同，请改用 Word。标准库内置常用现行/废止对照（含 GB 55001、GB 55008 等强制性通用规范），可按项目在 `qingbiao/resources/standards.json` 自行增补。

## 测试

```bash
cd qingbiao
python -m pytest tests -q
```

本工具辅助清标复核，不替代评标委员会结论。

## 打包 Windows EXE

本机（需 Windows + Python 3.12）：

```bat
cd qingbiao
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm QingBiao.spec
```

生成 `dist/QingBiao.exe`。仓库已配置 GitHub Actions：`.github/workflows/build-qingbiao.yml`。

