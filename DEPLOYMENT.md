# 部署 e-cell

e-cell 是面向贴壁细胞培养条件探索的 Streamlit 研究原型。部署不会把它变成经验证的实验或临床软件；公开部署前应保留 README 中的科学边界、数据隐私与证据等级说明。

## 本地运行

要求：Python 3.11 或 3.12。

```bash
git clone https://github.com/umasouno2007-design/virtual-cell-simulator.git
cd virtual-cell-simulator
python -m venv .venv
```

激活环境后：

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

在浏览器打开终端显示的地址，通常是 <http://localhost:8501>。如 8501 已被占用，请使用 Streamlit 输出的替代端口。

## Streamlit Community Cloud

1. 将仓库推送到 GitHub，且确保根目录包含 `app.py`、`requirements.txt` 与 `assets/`。
2. 在 <https://share.streamlit.io/> 使用 GitHub 账户创建应用。
3. 选择此仓库和要部署的分支，入口文件填写 `app.py`，然后部署。
4. 在生成的应用日志中确认依赖安装和启动成功，再把实际 URL 更新到 README 顶部的 Demo 链接位置。

## 部署前检查

```bash
python -m unittest discover -s tests -p "test_*.py"
python scripts/validate_a549_teaching_case.py
python scripts/smoke_check.py
```

- 不要提交 `.streamlit/secrets.toml`、令牌、密码、患者资料、可识别供体资料、未公开实验数据或内部仪器日志。
- `data/a549_teaching_synthetic.csv` 是公开可分发的教学合成数据；不能替换为真实实验数据后仍沿用其“教学合成”表述。
- Streamlit Cloud 的本地文件存储是临时的；配置快照、CSV 和事件记录应及时下载保存，不应被当作 GLP/GMP 审计系统。

## 上线后人工验证

首次部署后，在空浏览器会话中人工确认：默认模拟能推进；教学 CSV 可读取；无效 CSV 和场景 JSON 显示面向研究用户的说明而非技术堆栈；场景可导出/再导入；数据质量报告、校准热图和 CSV 导出可用；窄屏下版本、数据状态和关键警告仍可见。云端文件系统不是持久数据库，不能保存实测原始数据或作为审计追踪。

已知限制：当前依赖 Python 3.11/3.12；示例 A549 数据为教学合成数据；细胞器状态是教学相对指数；两参数网格搜索只是参数初值探索，不能替代真实实验校准或独立验证。
