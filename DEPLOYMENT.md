# 部署到网页，在 Pad 上运行

本项目已包含 `requirements.txt` 和 `.streamlit/config.toml`，可以部署到 Streamlit Community Cloud。部署完成后，Android Pad、iPad 和电脑都可以通过浏览器访问。

## 第一步：上传到 GitHub

1. 注册或登录 GitHub。
2. 新建一个名为 `e-cell` 的仓库。
3. 把本项目中的所有文件上传到仓库根目录。
4. 确认仓库根目录能看到 `app.py` 和 `requirements.txt`。

## 第二步：创建 Streamlit 应用

1. 在浏览器打开 <https://share.streamlit.io/>。
2. 使用 GitHub 登录并授权访问刚才的仓库。
3. 选择对应的仓库和分支。
4. 主文件路径填写 `app.py`。
5. 点击 **Deploy**。

部署通常需要几分钟。成功后会得到一个以 `streamlit.app` 结尾的网址。

## 第三步：在 Pad 上使用

1. 在 Pad 浏览器中打开部署网址。
2. 可以将网页“添加到主屏幕”，以后像普通应用一样打开。
3. 每台设备和每个浏览器会话都有独立的模拟状态。
4. 点击“下载 CSV 数据”可把实验记录保存到 Pad。

## 后续更新

修改代码并推送到同一个 GitHub 仓库后，Streamlit Community Cloud 会重新部署。若部署失败，先检查日志中指出的文件名和依赖错误。

## 注意

- 不要把密码、令牌或其他隐私信息写进代码仓库。
- 本项目不需要数据库，也不需要设置密钥。
- 模拟数据保存在浏览器会话中；刷新、休眠或服务重启后可能重置，请及时下载 CSV。
