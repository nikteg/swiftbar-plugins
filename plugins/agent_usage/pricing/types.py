"""Per-million-token prices, and the credit rates derived from them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TokenPrice:
    input: float
    cached_input: float
    cache_write: float
    output: float


@dataclass(frozen=True)
class LongContextTokenPrice(TokenPrice):
    threshold_tokens: float = 0.0


@dataclass(frozen=True)
class ModelPrice(TokenPrice):
    long_context: LongContextTokenPrice | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ModelPrice:
        long_context = value.get("long_context")

        return cls(
            input=value["input"],
            cached_input=value["cached_input"],
            cache_write=value["cache_write"],
            output=value["output"],
            long_context=(
                LongContextTokenPrice(
                    input=long_context["input"],
                    cached_input=long_context["cached_input"],
                    cache_write=long_context["cache_write"],
                    output=long_context["output"],
                    threshold_tokens=long_context["threshold_tokens"],
                )
                if long_context
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        value = {
            "input": self.input,
            "cached_input": self.cached_input,
            "cache_write": self.cache_write,
            "output": self.output,
        }

        if self.long_context is not None:
            value["long_context"] = {
                "input": self.long_context.input,
                "cached_input": self.long_context.cached_input,
                "cache_write": self.long_context.cache_write,
                "output": self.long_context.output,
                "threshold_tokens": self.long_context.threshold_tokens,
            }

        return value

    def scaled(self, factor: float) -> ModelPrice:
        return ModelPrice(
            input=self.input * factor,
            cached_input=self.cached_input * factor,
            cache_write=self.cache_write * factor,
            output=self.output * factor,
            long_context=(
                LongContextTokenPrice(
                    input=self.long_context.input * factor,
                    cached_input=self.long_context.cached_input * factor,
                    cache_write=self.long_context.cache_write * factor,
                    output=self.long_context.output * factor,
                    threshold_tokens=self.long_context.threshold_tokens,
                )
                if self.long_context is not None
                else None
            ),
        )
