"""MCP backend: drives the OFH DoS attacker sweep through the ran-tester-ue MCP server.

Spawns the same MCP server opencode uses (``docker compose run --rm mcp-server``
over stdio) via the mcp Python SDK client, then calls the exposed tools:

  - list_components
  - start_component(component_type, config_json, rf_config, component?)
  - stop_component(component_id)
  - get_component_logs(component_id, component_type)

The stderr of the spawned MCP server is piped to a log file for debugging.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ofh_sweep.spec import COMPONENT_REPO, COMPONENT_TYPE


class McpBackend:
    def __init__(self, project_dir: Path, stderr_log: Path | None = None, use_sudo: bool = True):
        self.project_dir = project_dir
        self.stderr_log = stderr_log
        self.use_sudo = use_sudo

    def _cmd(self) -> list[str]:
        base = ["docker", "compose", "run", "--rm", "mcp-server"]
        if self.use_sudo:
            return ["sudo", *base]
        return base

    async def _run_tool(self, session: ClientSession, name: str, arguments: dict[str, Any] | None = None):
        result = await session.call_tool(name, arguments)
        if result.isError:
            raise RuntimeError(f"MCP tool {name} error: {result.content}")
        texts = [getattr(c, "text", json.dumps(c, default=str)) for c in result.content]
        return "\n".join(texts)

    async def _execute(self, tool, tool_args: dict[str, Any] | None = None):
        params = StdioServerParameters(
            command=self._cmd()[0],
            args=self._cmd()[1:],
            cwd=str(self.project_dir),
        )
        errlog = sys.stderr
        close_errlog = False
        if self.stderr_log is not None:
            self.stderr_log.parent.mkdir(parents=True, exist_ok=True)
            errlog = self.stderr_log.open("a", encoding="utf-8")
            close_errlog = True
        try:
            try:
                client_cm = stdio_client(params, errlog=errlog)
            except TypeError:  # older mcp SDKs without the errlog kwarg
                client_cm = stdio_client(params)
            async with client_cm as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    text = await self._run_tool(session, tool, tool_args)
                    return text
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"MCP client failure for tool '{tool}': {exc}") from exc
        finally:
            if close_errlog:
                errlog.close()

    def start(self, config: dict[str, Any], rf: dict[str, Any]) -> str:
        args = {
            "component_type": COMPONENT_TYPE,
            "config_json": config,
            "rf_config": rf,
            "component": COMPONENT_REPO,
        }
        return asyncio.run(self._execute("start_component", args))

    def stop(self, run_id: str) -> str:
        return asyncio.run(self._execute("stop_component", {"component_id": run_id}))

    def list(self) -> str:
        return asyncio.run(self._execute("list_components"))

    def logs(self, run_id: str) -> str:
        return asyncio.run(
            self._execute("get_component_logs", {"component_id": run_id, "component_type": COMPONENT_TYPE})
        )