# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from langchain_core.tools import BaseTool

from src.runtime.middleware.base import RuntimeContext
from src.runtime.tools.wrapper import wrap_tool

ToolFactory = Callable[[dict[str, Any]], BaseTool]


@dataclass
class ToolSpec:
    name: str
    factory: ToolFactory
    timeout_seconds: Optional[float] = 60
    source: str = "native"
    description: str = ""


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        factory: ToolFactory | BaseTool,
        *,
        timeout_seconds: Optional[float] = 60,
        source: str = "native",
        description: str = "",
    ) -> None:
        if isinstance(factory, BaseTool):
            tool = factory
            self._specs[name] = ToolSpec(
                name=name,
                factory=lambda _cfg, _tool=tool: _tool,
                timeout_seconds=timeout_seconds,
                source=source,
                description=description or getattr(tool, "description", ""),
            )
            return
        self._specs[name] = ToolSpec(
            name=name,
            factory=factory,
            timeout_seconds=timeout_seconds,
            source=source,
            description=description,
        )

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._specs.get(name)

    def names(self) -> list[str]:
        return sorted(self._specs)

    def bind(
        self,
        names: list[str],
        config: Optional[dict[str, Any]] = None,
        *,
        allowed_tools: Optional[list[str]] = None,
        ctx: Optional[RuntimeContext] = None,
    ) -> list[BaseTool]:
        """Build the visible tool set. Tools not listed here never reach the agent."""
        visible = names if allowed_tools is None else [name for name in names if name in allowed_tools]
        bound: list[BaseTool] = []
        runtime_ctx = ctx or RuntimeContext(allowed_tools=allowed_tools)
        if allowed_tools is not None:
            runtime_ctx.allowed_tools = allowed_tools
        for name in visible:
            spec = self._specs.get(name)
            if spec is None:
                raise KeyError(f"Tool '{name}' is not registered")
            instance = spec.factory(config or {})
            bound.append(
                wrap_tool(
                    instance,
                    ctx=runtime_ctx,
                    timeout_seconds=spec.timeout_seconds,
                )
            )
        return bound

    def wrap(
        self,
        tool: BaseTool,
        *,
        source: str = "native",
        timeout_seconds: Optional[float] = None,
        ctx: Optional[RuntimeContext] = None,
    ) -> BaseTool:
        spec = self._specs.get(tool.name)
        if spec is None:
            self.register(
                tool.name,
                tool,
                timeout_seconds=timeout_seconds or 60,
                source=source,
                description=getattr(tool, "description", ""),
            )
            spec = self._specs[tool.name]
        return wrap_tool(
            tool,
            ctx=ctx,
            timeout_seconds=timeout_seconds if timeout_seconds is not None else spec.timeout_seconds,
        )

    def wrap_all(
        self,
        tools: list[BaseTool],
        *,
        source: str = "native",
        ctx: Optional[RuntimeContext] = None,
    ) -> list[BaseTool]:
        return [self.wrap(tool, source=source, ctx=ctx) for tool in tools]


_registry: Optional[ToolRegistry] = None


def register_builtin_tools(registry: ToolRegistry) -> None:
    from src.tools.crawl import crawl_tool
    from src.tools.python_repl import python_repl_tool
    from src.tools.search import get_web_search_tool

    registry.register(
        "web_search",
        lambda cfg: get_web_search_tool(cfg.get("max_search_results", 3)),
        timeout_seconds=30,
        description="Search the public web",
    )
    registry.register(
        "crawl",
        crawl_tool,
        timeout_seconds=45,
        description=getattr(crawl_tool, "description", "Crawl a URL"),
    )
    registry.register(
        "crawl_tool",
        crawl_tool,
        timeout_seconds=45,
        description=getattr(crawl_tool, "description", "Crawl a URL"),
    )
    registry.register(
        "python_repl",
        python_repl_tool,
        timeout_seconds=15,
        description=getattr(python_repl_tool, "description", "Execute Python"),
    )
    registry.register(
        "python_repl_tool",
        python_repl_tool,
        timeout_seconds=15,
        description=getattr(python_repl_tool, "description", "Execute Python"),
    )


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        register_builtin_tools(_registry)
    return _registry


def set_tool_registry(registry: Optional[ToolRegistry]) -> None:
    global _registry
    _registry = registry
