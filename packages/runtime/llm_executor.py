from __future__ import annotations

import os
import time

from packages.runtime.executor import ToolExecutionResult
from packages.runtime.state import RunState


# Cost per 1M tokens (USD) by model family
_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
}

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MAX_TOKENS = 1024


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost from token counts and model name."""
    input_per_m, output_per_m = _MODEL_COSTS.get(model, (0.15, 0.60))
    return (prompt_tokens * input_per_m + completion_tokens * output_per_m) / 1_000_000


class LLMExecutor:
    """Real LLM executor using OpenAI-compatible API with Langfuse tracing."""

    def __init__(
        self,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        system_prompt: str | None = None,
    ):
        self.model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt or (
            "You are a helpful research assistant. "
            "Provide clear, concise, and accurate responses."
        )

    async def execute(self, state: RunState) -> ToolExecutionResult:
        """Build prompt from state, call LLM, return structured result with Langfuse trace."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return ToolExecutionResult(
                output="",
                error="openai package not installed. Run: pip install openai",
                model=self.model,
            )

        goal = state.goal or ""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": goal},
        ]

        # Try to get Langfuse client from app state if available
        langfuse_client = _get_langfuse_client()
        trace = None
        generation = None

        if langfuse_client:
            try:
                trace = langfuse_client.trace(
                    name="execute_node",
                    input={"goal": goal, "model": self.model},
                    metadata={
                        "run_id": str(state.run_id),
                        "tenant_id": str(state.tenant_id),
                        "iterations": state.iterations,
                    },
                )
                generation = trace.generation(
                    name="llm_call",
                    model=self.model,
                    input=messages,
                )
            except Exception:
                trace = None
                generation = None

        start = time.time()
        try:
            api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("LLM_API_KEY or OPENAI_API_KEY environment variable not set")

            base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
            client_kwargs: dict = {"api_key": api_key}
            if base_url:
                client_kwargs["base_url"] = base_url

            client = AsyncOpenAI(**client_kwargs)
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=self.max_tokens,
            )

            content = response.choices[0].message.content or ""
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            latency_ms = int((time.time() - start) * 1000)
            cost_usd = estimate_cost(self.model, prompt_tokens, completion_tokens)

            # End Langfuse generation with output
            if generation:
                try:
                    generation.end(
                        output=content,
                        usage={
                            "promptTokens": prompt_tokens,
                            "completionTokens": completion_tokens,
                            "totalTokens": prompt_tokens + completion_tokens,
                        },
                        metadata={"cost_usd": cost_usd, "latency_ms": latency_ms},
                    )
                except Exception:
                    pass

            if trace:
                try:
                    trace.end(metadata={"status": "success", "cost_usd": cost_usd})
                except Exception:
                    pass

            return ToolExecutionResult(
                output=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=self.model,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
            )

        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)

            # End Langfuse generation with error
            if generation:
                try:
                    generation.end(error=str(exc))
                except Exception:
                    pass

            if trace:
                try:
                    trace.end(metadata={"status": "error", "error": str(exc)})
                except Exception:
                    pass

            return ToolExecutionResult(
                output="",
                error=str(exc),
                model=self.model,
                latency_ms=latency_ms,
            )


def _get_langfuse_client():
    """Try to get the Langfuse client. Returns None if unavailable."""
    try:
        from langfuse import Langfuse

        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

        if not public_key or not secret_key:
            return None

        return Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    except Exception:
        return None
