from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class MemDmTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        # 保留占位工具，提示使用具体工具
        yield self.create_text_message("Use mem_dm_add_memory or mem_dm_retrieve_memory tools.")
