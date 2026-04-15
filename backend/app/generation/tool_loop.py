"""Completion-with-tools loop.

Kimi's Coding API has no server-resolved web search: the model emits
``finish_reason="tool_calls"`` and expects the client to run the tool
itself, then feed results back as a ``role="tool"`` message. Providers
that genuinely one-shot (Anthropic ``web_search_20250305``, Gemini
``google_search``) return ``finish_reason="stop"`` immediately — this
loop handles both by simply iterating until the model stops asking for
tool calls.

This module deliberately knows nothing about providers or newsletter
content — it takes a ``completion`` callable and a tool executor and
drives the conversation. Trace entries are JSON-safe primitives so the
caller can persist them as diagnostic evidence.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

# Type alias for the tool executor callback.
ToolExecutor = Callable[[str, str], str]


def run(
    *,
    completion: Callable[..., Any],
    model: str,
    messages: list[dict[str, Any]],
    api_key: str,
    completion_kwargs: dict[str, Any],
    max_iterations: int = 8,
    tool_executor: ToolExecutor | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    """Drive a chat-completion conversation until the model stops emitting
    ``tool_calls``.

    When ``tool_executor`` is provided (client-side tools), each tool call is
    resolved via the executor and its output is sent back as the tool message
    content. When ``tool_executor`` is None (server-resolved tools), the
    arguments are echoed back unchanged — this was the old Moonshot
    ``$web_search`` builtin protocol; kept as a safe fallback, though current
    server-resolved providers typically never enter this branch because they
    one-shot on iteration 0.

    If ``max_iterations`` is reached with the model still asking for more
    tool calls, a final "force-close" completion is issued with the ``tools``
    kwarg stripped, so the model is obliged to produce content instead of
    returning an empty response with ``finish_reason="tool_calls"``.

    Returns ``(final_response, trace)`` where trace records per-iteration
    finish_reason, tool_calls count, and token usage so operators can tell
    from the Logs page whether the tool actually fired.
    """
    conversation = list(messages)
    last_response = None
    trace: list[dict[str, Any]] = []

    for iteration in range(max_iterations + 1):
        last_response = completion(
            model=model,
            messages=conversation,
            api_key=api_key,
            **completion_kwargs,
        )
        choice = last_response.choices[0]
        message = choice.message
        finish_reason = getattr(choice, "finish_reason", None)
        tool_calls_raw = getattr(message, "tool_calls", None)
        tool_calls = tool_calls_raw if isinstance(tool_calls_raw, list) else []

        usage = getattr(last_response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage is not None else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage is not None else None
        trace.append(
            {
                "iteration": iteration,
                "finish_reason": finish_reason if isinstance(finish_reason, str) else None,
                "tool_calls_count": len(tool_calls),
                "prompt_tokens": prompt_tokens if isinstance(prompt_tokens, int) else None,
                "completion_tokens": completion_tokens
                if isinstance(completion_tokens, int)
                else None,
            }
        )

        if finish_reason != "tool_calls" or not tool_calls:
            return last_response, trace

        # Replay the assistant turn that asked for tools, then add a
        # tool-response message for each call so the next iteration has
        # the full history.
        assistant_entry: dict[str, Any] = {
            "role": "assistant",
            "content": getattr(message, "content", None) or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        }
        conversation = copy.deepcopy(conversation)
        conversation.append(assistant_entry)

        for tc in tool_calls:
            if tool_executor is not None:
                tool_content = tool_executor(tc.function.name, tc.function.arguments)
            else:
                # Server-resolved protocol — echo args back unchanged.
                tool_content = tc.function.arguments
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": tool_content,
                }
            )

    # Max iterations reached with the model still asking for tools. Make one
    # final call without the tools kwarg and with an explicit nudge, so the
    # model is forced to produce content instead of more tool_calls. Without
    # this, the caller would get back a response with ``content=None`` and
    # ``finish_reason="tool_calls"`` — which looks like an empty generation.
    final_kwargs = {k: v for k, v in completion_kwargs.items() if k != "tools"}
    conversation.append(
        {
            "role": "user",
            "content": (
                "You have gathered enough information. Produce the final "
                "newsletter output now in the exact JSON schema requested, "
                "with no further tool calls and no surrounding prose."
            ),
        }
    )
    last_response = completion(
        model=model,
        messages=conversation,
        api_key=api_key,
        **final_kwargs,
    )
    choice = last_response.choices[0]
    usage = getattr(last_response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage is not None else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage is not None else None
    trace.append(
        {
            "iteration": max_iterations + 1,
            "finish_reason": (
                getattr(choice, "finish_reason", None)
                if isinstance(getattr(choice, "finish_reason", None), str)
                else None
            ),
            "tool_calls_count": 0,
            "prompt_tokens": prompt_tokens if isinstance(prompt_tokens, int) else None,
            "completion_tokens": completion_tokens if isinstance(completion_tokens, int) else None,
            "force_closed": True,
        }
    )
    return last_response, trace
