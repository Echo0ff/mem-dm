from collections.abc import Generator
from typing import Any

import time
import httpx
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


_RESOLVE_CACHE: dict[str, float | str] = {"value": None, "ts": 0.0}
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

    chosen = candidates[0] if candidates else raw.rstrip("/")
    _RESOLVE_CACHE["value"] = chosen
    _RESOLVE_CACHE["ts"] = now
    return chosen


class MemDmRetrieveTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        base_raw: str = self.runtime.credentials["base_url"]
        base_url: str = _select_reachable_base_url(base_raw)

        # 按模板构造 payload：必传 query 与 user_id；其它可选
        payload: dict[str, Any] = {
            "query": tool_parameters["query"],
            "user_id": tool_parameters["user_id"],
        }
        if tool_parameters.get("run_id"):
            payload["run_id"] = tool_parameters["run_id"]
        if tool_parameters.get("agent_id"):
            payload["agent_id"] = tool_parameters["agent_id"]
        if tool_parameters.get("filters"):
            payload["filters"] = tool_parameters["filters"]
        if tool_parameters.get("limit") is not None:
            payload["limit"] = tool_parameters["limit"]
        if tool_parameters.get("threshold") is not None:
            payload["threshold"] = tool_parameters["threshold"]

        url = f"{base_url}/search"
        max_retries = 3
        timeout_s = 10.0
        backoff_base = 0.6

        last_error_text = None
        for attempt in range(1, max_retries + 1):
            try:
                with httpx.Client(timeout=timeout_s) as client:
                    resp = client.post(url, json=payload)
                    if 500 <= resp.status_code < 600 and attempt < max_retries:
                        last_error_text = f"{resp.status_code} {resp.text[:200]}"
                        time.sleep(backoff_base * attempt)
                        continue
                    resp.raise_for_status()
                    try:
                        data = resp.json()
                    except Exception:
                        data = {}

                    if isinstance(data, dict):
                        raw_results = data.get("results", [])
                        relations = data.get("relations", [])
                    else:
                        raw_results = data if isinstance(data, list) else []
                        relations = []

                    # 仅保留指定字段
                    keep_keys = {"memory", "created_at", "updated_at", "score", "metadata", "user_id"}
                    results: list[dict[str, Any]] = []
                    for item in raw_results:
                        if isinstance(item, dict):
                            filtered = {k: v for k, v in item.items() if k in keep_keys}
                            results.append(filtered if filtered else item)
                        else:
                            results.append(item)

                    payload_out = {"results": results, "relations": relations}
                    yield self.create_json_message(payload_out)

                    top_mem = results[0]["memory"] if results and isinstance(results[0], dict) and results[0].get("memory") else ""
                    yield self.create_text_message(f"Endpoint: {url}\nQuery: {tool_parameters['query']}\nTop: {top_mem}")
                    return

            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                last_error_text = f"network timeout/connect error: {str(e)}"
                if attempt < max_retries:
                    time.sleep(backoff_base * attempt)
                    continue
                break
            except httpx.HTTPStatusError as e:
                try:
                    detail = e.response.json().get("detail")
                except Exception:
                    detail = e.response.text[:200]
                last_error_text = f"HTTP {e.response.status_code} | detail={detail}"
                break
            except Exception as e:
                last_error_text = f"unexpected error: {str(e)}"
                break

        msg = f"SEARCH request failed | url={url} | error={last_error_text}"
        yield self.create_json_message({"status": "error", "error": msg})
        yield self.create_text_message(msg)


