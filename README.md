# 语音约碰面地点

本地全栈骨架。当前只提供后端健康检查和可打开的前端页面。

- 后端：Python 3.11，端口 `8003`
- 前端：Node.js 22.12 及以上的 22.x，端口 `5175`
- 密钥填入 `backend/.env`（可从 `backend/.env.example` 复制）。健康检查不依赖这些密钥。

## 启动后端

需要 **Python 3.11**。不要用系统自带的 `python3` / `pip` 直接装包（Homebrew Python 会报 `externally-managed-environment`）。

若本机没有 `python3.11` 命令：

```bash
brew install python@3.11
```

然后在项目里创建虚拟环境并启动：

```bash
cd backend
/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
uvicorn main:app --host 127.0.0.1 --port 8003
```

激活 `.venv` 之后，提示符前应出现 `(.venv)`，此时的 `python` 和 `uvicorn` 都来自虚拟环境。

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5175`。

## 验证健康检查

- 接口：`GET http://localhost:8003/health`
- 文档：`http://localhost:8003/docs`

预期 HTTP 200，响应形如：

```json
{
  "request_id": "uuid",
  "data": {
    "status": "ok"
  }
}
```

模拟测试与真实外部接口验收方法将在后续回合补充。
