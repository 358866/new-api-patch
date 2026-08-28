# new-api-patch

NewAPI (QuantumNous/new-api) 自定义补丁分支，基于 `v1.0.0-rc.26`。

## 补丁内容

针对 `/v1/messages` 流式端点，当上游是 OpenAI 兼容且输出推理内容（`reasoning_content` + `content`）时，修复两个问题：

### 补丁 1：缺失终止事件（message_stop）
- 文件：`relay/channel/openai/helper.go`
- 问题：某些上游把 `finish_reason` 和 usage 分开发送，或最后一个 chunk 没触发终止事件，导致 `content_block_stop / message_delta / message_stop` 缺失，Claude Code 报 "Streaming response ended"。
- 修复：`HandleFinalResponse` 中调用 `FinalizeClaudeStreamResponse` 兜底补发。

### 补丁 2：正文 content 被丢弃
- 文件：`relaykit/relayconvert/internal/oai_chat/to_claude_messages_resp.go`
- 问题：`doneChunk` 分支在 usage 缺失时提前 `return`，把同 chunk 的正文 `content` 直接丢弃（NVIDIA NIM 等上游把正文与 `finish_reason` 放在同一个 chunk 且不带 usage）。
- 修复：删除提前 return，正文与 `message_stop` 正常发出。

### 辅助改动
- `relaykit/relayconvert/response_compat.go`：导出 `FinalizeClaudeStreamResponse`。

## 官方 issue

- https://github.com/QuantumNous/new-api/issues/4697 （/v1/messages 流式缺少终止事件，至今 OPEN）

## 构建

```bash
git clone https://github.com/358866/new-api-patch.git
cd new-api-patch
docker build --no-cache -t new-api-patched -f Dockerfile .
```

替换容器（保留数据卷）：

```bash
docker stop new-api && docker rm new-api
docker run -d --name new-api -p 3000:3000 -e TZ=Asia/Shanghai \
  -v /path/to/data:/data --restart unless-stopped new-api-patched:latest
```

## 加模型脚本

`add_model.py` 一键加模型（写渠道 models + ModelRatio=0 + 重建 abilities + 重启容器）：

```bash
python add_model.py "model-name" --channel 8   # 加到指定渠道
python add_model.py "model-name" --all          # 加到所有渠道
python add_model.py --list                      # 列出渠道
```

## 迭代说明

- 升级官方版本：`git fetch origin` + 重新拉取新 tag，把上述两个补丁重新应用到新版本。
- 云服务器部署：见上方 `docker run` 命令，把数据卷映射到云盘路径即可。
