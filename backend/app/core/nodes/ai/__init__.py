"""AI provider nodes (Claude, OpenAI) — auto-register with the node registry."""

from app.core.nodes.ai.claude_node import ClaudeNode
from app.core.nodes.ai.openai_node import OpenAINode

__all__ = ["ClaudeNode", "OpenAINode"]
