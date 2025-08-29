from collections.abc import Generator
from typing import Any, List

import time
import httpx
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


_RESOLVE_CACHE: dict[str, float | str] = {"value": None, "ts": 0.0}  # 简单缓存已探测成功的 base_url
_RESOLVE_TTL = 60.0


def _select_reachable_base_url(raw: str) -> str:
    import time as _time
    import httpx as _httpx

    now = _time.time()
    cached = _RESOLVE_CACHE.get("value")
    ts = _RESOLVE_CACHE.get("ts", 0.0) or 0.0
    if cached and (now - float(ts) < _RESOLVE_TTL):
        return str(cached)

    raw = (raw or "").strip()
    # 支持多地址：逗号分隔；或特殊值 auto → 先内网再外网
    if "," in raw:
        candidates = [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]
    elif raw.lower() == "auto":
        candidates = [
            "http://192.168.88.51:18888",
            "http://47.99.246.108:18888",
        ]
    else:
        candidates = [raw.rstrip("/")]

    for base in candidates:
        try:
            r = _httpx.get(f"{base}/health", timeout=1.2)
            if 200 <= r.status_code < 500:
                _RESOLVE_CACHE["value"] = base
                _RESOLVE_CACHE["ts"] = now
                return base
        except Exception:
            continue

    # 全部失败则返回第一个候选（让后续请求按原样尝试）
    chosen = candidates[0] if candidates else raw.rstrip("/")
    _RESOLVE_CACHE["value"] = chosen
    _RESOLVE_CACHE["ts"] = now
    return chosen


class MemDmAddTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        base_raw: str = self.runtime.credentials["base_url"]
        base_url: str = _select_reachable_base_url(base_raw)

        # 按模板：必传 content 与 user_id；其余可选未提供则不传
        content: str = tool_parameters["content"]
        messages: List[dict[str, str]] = [{"role": "user", "content": content}]

        payload: dict[str, Any] = {
            "messages": messages,
            "user_id": tool_parameters["user_id"],
        }
        # 可选项
        if tool_parameters.get("agent_id"):
            payload["agent_id"] = tool_parameters["agent_id"]
        if tool_parameters.get("run_id"):
            payload["run_id"] = tool_parameters["run_id"]
        if tool_parameters.get("metadata"):
            # 将 JSON 字符串解析为对象，失败则忽略
            try:
                import json as _json
                payload["metadata"] = _json.loads(tool_parameters["metadata"])
            except Exception:
                pass

        # 使用异步入库接口，避免阻塞调用方流程
        url = f"{base_url}/memories/async"
        max_retries = 3
        # 异步接口应快速返回，缩短超时
        timeout_s = 6.0
        backoff_base = 0.6

        last_error_text = None
        for attempt in range(1, max_retries + 1):
            try:
                with httpx.Client(timeout=timeout_s) as client:
                    resp = client.post(url, json=payload)
                    # 5xx 可重试，4xx 不重试
                    if 500 <= resp.status_code < 600 and attempt < max_retries:
                        last_error_text = f"{resp.status_code} {resp.text[:200]}"
                        time.sleep(backoff_base * attempt)
                        continue
                    resp.raise_for_status()
                    # 兼容 202/accepted 以及历史 200 返回
                    try:
                        data = resp.json()
                    except Exception:
                        data = {"raw": resp.text[:200]}

                    accepted = bool(data.get("accepted")) or resp.status_code == 202
                    if accepted:
                        yield self.create_json_message({
                            "status": "accepted",
                            "accepted": True,
                            "echo": {"user_id": tool_parameters["user_id"]},
                        })

                        text = "Accepted for background processing\n"
                        text += f"Endpoint: {url}\n"
                        text += f"Content: {content[:80]}\n"
                        yield self.create_text_message(text)
                        return
                    else:
                        # 如果服务升级为同步成功也能兼容
                        yield self.create_json_message({
                            "status": "success",
                            "results": data.get("results", data),
                        })
                        yield self.create_text_message(f"Succeeded: {url}")
                        return

            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                last_error_text = f"network timeout/connect error: {str(e)}"
                if attempt < max_retries:
                    time.sleep(backoff_base * attempt)
                    continue
                break
            except httpx.HTTPStatusError as e:
                # 4xx 不重试
                try:
                    detail = e.response.json().get("detail")
                except Exception:
                    detail = e.response.text[:200]
                last_error_text = f"HTTP {e.response.status_code} | detail={detail}"
                break
            except Exception as e:
                last_error_text = f"unexpected error: {str(e)}"
                break

        # 走到这里表示失败
        msg = f"ADD request failed | url={url} | error={last_error_text}"
        yield self.create_json_message({"status": "error", "error": msg})
        yield self.create_text_message(msg)


