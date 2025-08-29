## mem-dm (Dify Tool 插件)

**Author:** zard  
**Version:** 0.0.1  
**Type:** tool

### 简介
本插件将 Dify 工具与自建的 Mem 服务对接，当前默认服务：`http://47.99.246.108:18888`。

### 功能
- 添加记忆：POST /memories
- 检索记忆：POST /search
- 仅 user 消息会被作为记忆（assistant 可选携带）
- 内置超时重试（网络超时/5xx 重试，指数退避）与详细错误信息

### 安装
1. Python 版本 ≥ 3.12（由 Dify 插件运行器提供）。
2. 在 Dify 插件管理中选择此插件目录进行安装，或打包后上传。
3. Provider 凭据：
   - base_url：你的服务地址（默认 `http://47.99.246.108:18888`）。
   - api_key：可选。如果你的服务启用了鉴权，将以 `Authorization: Bearer <api_key>` 方式携带。

### 接口说明（自建 Mem 服务）
- 基础地址：`http://47.99.246.108:18888`

1) 添加记忆
- 路径：`POST /memories`
- 请求体示例：
```json
{
  "messages": [
    {"role": "user", "content": "我喜欢羽毛球。"},
    {"role": "assistant", "content": "那你多久打一次？"}
  ],
  "user_id": "user_01"
}
```
- 返回体示例（简化）：
```json
{
  "results": [
    {"id": "uuid-1", "memory": "…", "event": "ADD"}
  ]
}
```

2) 检索记忆
- 路径：`POST /search`
- 请求体示例：
```json
{
  "query": "我喜欢什么运动",
  "user_id": "user_01"
}
```
- 返回体示例（简化）：
```json
{
  "results": [
    {"id": "uuid-2", "memory": "我喜欢羽毛球。", "score": 0.86, "created_at": "…"}
  ]
}
```

### 工具定义
- Add Memory (mem-dm): `tools/add_memory.yaml`
  - 参数：
    - user (string, required)
    - assistant (string, optional)
    - user_id (string, required)
- Retrieve Memory (mem-dm): `tools/retrieve_memory.yaml`
  - 参数：
    - query (string, required)
    - user_id (string, required)

### 在工作流中配置工具参数
- 添加记忆（Add Memory）：
  - user：绑定到对话的用户输入或 Workflow 变量
  - assistant（可选）：绑定到模型回复或固定文本
  - user_id：绑定到会话/租户的用户标识
- 检索记忆（Retrieve Memory）：
  - query：绑定到需要检索的查询文本
  - user_id：与上保持一致，确保检索到该用户空间下的记忆

### 错误与重试
- 5xx/网络超时：最多 3 次重试，退避系数 0.6s * attempt。
- 4xx：直接返回错误，不重试，并在文本与 JSON 中包含详细错误信息（含 HTTP 状态与 detail）。

### 打包
- 使用 Dify CLI（参考官方文档）
```bash
dify plugin package ./mem-dm
```
- 或在插件开发环境中以目录形式调试运行：
```bash
python -m main
```

### 参考
- Dify Tool 插件开发文档：<https://docs.dify.ai/zh-hans/plugins/quick-start/develop-plugins/tool-plugin>
