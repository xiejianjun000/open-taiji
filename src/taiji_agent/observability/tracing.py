"""
Tracing Core - 追踪核心
参考LangSmith全链路追踪设计
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
class StrEnum(str, Enum):
    pass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .exporter import TraceExporter

logger = logging.getLogger(__name__)

trace_context: ContextVar[Optional[str]] = ContextVar("trace_context", default=None)


class SpanKind(StrEnum):
    AGENT = "agent"
    TOOL = "tool"
    LLM = "llm"
    CHAIN = "chain"
    MEMORY = "memory"
    WORKFLOW = "workflow"
    GUARDRAIL = "guardrail"


class SpanStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class TraceSpan:
    span_id: str
    trace_id: str
    name: str
    kind: SpanKind
    start_time: float
    end_time: Optional[float] = None
    status: SpanStatus = SpanStatus.OK
    error_message: Optional[str] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[TraceEvent] = field(default_factory=list)
    parent_span_id: Optional[str] = None
    inputs: Optional[dict[str, Any]] = None
    outputs: Optional[dict[str, Any]] = None

    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "kind": self.kind.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms(),
            "status": self.status.value,
            "error_message": self.error_message,
            "attributes": self.attributes,
            "events": [e.to_dict() for e in self.events],
            "parent_span_id": self.parent_span_id,
            "inputs": self.inputs,
            "outputs": self.outputs,
        }


@dataclass
class TraceEvent:
    name: str
    timestamp: float
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "attributes": self.attributes,
        }


class TraceSpanContext:
    def __init__(self):
        self._current_span: Optional[TraceSpan] = None
        self._span_stack: list[TraceSpan] = []

    def set_current_span(self, span: TraceSpan) -> None:
        self._current_span = span

    def get_current_span(self) -> Optional[TraceSpan]:
        return self._current_span

    def push_span(self, span: TraceSpan) -> None:
        self._span_stack.append(span)
        self._current_span = span

    def pop_span(self) -> Optional[TraceSpan]:
        if self._span_stack:
            popped = self._span_stack.pop()
            self._current_span = self._span_stack[-1] if self._span_stack else None
            return popped
        return None

    def get_trace_id(self) -> Optional[str]:
        if self._span_stack:
            return self._span_stack[0].trace_id
        return None


_span_context = TraceSpanContext()


class TracingManager:
    def __init__(self):
        self._spans: dict[str, TraceSpan] = {}
        self._exporters: list[TraceExporter] = []
        self._enabled = True
        self._project_name: Optional[str] = None
        self._metadata: dict[str, Any] = {}

    def add_exporter(self, exporter: TraceExporter) -> None:
        self._exporters.append(exporter)

    def set_project(self, name: str) -> None:
        self._project_name = name

    def set_metadata(self, **kwargs) -> None:
        self._metadata.update(kwargs)

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.AGENT,
        attributes: Optional[dict[str, Any]] = None,
        parent_span_id: Optional[str] = None,
        inputs: Optional[dict[str, Any]] = None,
    ) -> TraceSpan:
        trace_id = _span_context.get_trace_id() or str(uuid.uuid4())
        span_id = str(uuid.uuid4())[:16]
        current = _span_context.get_current_span()
        span = TraceSpan(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            kind=kind,
            start_time=time.time(),
            attributes=attributes or {},
            parent_span_id=parent_span_id or (current.span_id if current else None),
            inputs=inputs,
        )
        self._spans[span_id] = span
        _span_context.push_span(span)
        return span

    def end_span(
        self,
        span: TraceSpan,
        status: SpanStatus = SpanStatus.OK,
        outputs: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        span.end_time = time.time()
        span.status = status
        span.outputs = outputs
        if error:
            span.error_message = error
            span.status = SpanStatus.ERROR
        _span_context.pop_span()
        self._export_span(span)

    def add_event(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        span = _span_context.get_current_span()
        if span:
            event = TraceEvent(
                name=name,
                timestamp=time.time(),
                attributes=attributes or {},
            )
            span.events.append(event)

    def record_exception(self, exception: Exception) -> None:
        span = _span_context.get_current_span()
        if span:
            span.status = SpanStatus.ERROR
            span.error_message = str(exception)
            span.events.append(
                TraceEvent(
                    name="exception",
                    timestamp=time.time(),
                    attributes={
                        "exception.type": type(exception).__name__,
                        "exception.message": str(exception),
                    },
                )
            )

    def _export_span(self, span: TraceSpan) -> None:
        for exporter in self._exporters:
            try:
                exporter.export([span])
            except Exception as e:
                logger.error(f"Failed to export span: {e}")

    def get_trace(self, trace_id: str) -> list[TraceSpan]:
        return [s for s in self._spans.values() if s.trace_id == trace_id]

    def get_trace_tree(self, trace_id: str) -> dict[str, Any]:
        spans = self.get_trace(trace_id)
        if not spans:
            return {}
        root_span = next((s for s in spans if s.parent_span_id is None), spans[0])

        def build_tree(span: TraceSpan) -> dict[str, Any]:
            children = [build_tree(s) for s in spans if s.parent_span_id == span.span_id]
            return {
                **span.to_dict(),
                "children": children,
            }

        return build_tree(root_span)

    @asynccontextmanager
    async def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.AGENT,
        attributes: Optional[dict[str, Any]] = None,
        inputs: Optional[dict[str, Any]] = None,
    ):
        span = self.start_span(name, kind, attributes, inputs=inputs)
        try:
            yield span
            self.end_span(span, SpanStatus.OK)
        except Exception as e:
            self.record_exception(e)
            self.end_span(span, SpanStatus.ERROR)
            raise

    def get_stats(self) -> dict[str, Any]:
        total_spans = len(self._spans)
        error_count = sum(1 for s in self._spans.values() if s.status == SpanStatus.ERROR)
        avg_duration = sum(s.duration_ms() for s in self._spans.values()) / total_spans if total_spans > 0 else 0
        spans_by_kind: dict[str, int] = {}
        for span in self._spans.values():
            kind = span.kind.value
            spans_by_kind[kind] = spans_by_kind.get(kind, 0) + 1
        return {
            "total_spans": total_spans,
            "error_count": error_count,
            "error_rate": error_count / total_spans if total_spans > 0 else 0,
            "avg_duration_ms": avg_duration,
            "spans_by_kind": spans_by_kind,
        }


_tracer = TracingManager()


def get_tracer() -> TracingManager:
    return _tracer
