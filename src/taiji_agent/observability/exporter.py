"""
Trace Exporters - 追踪数据导出器
支持Console、File、LangSmith等导出方式
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .tracing import TraceSpan

logger = logging.getLogger(__name__)


class TraceExporter(ABC):
    @abstractmethod
    def export(self, spans: list[TraceSpan]) -> None:
        raise NotImplementedError

    def flush(self) -> None:
        raise NotImplementedError


class ConsoleExporter(TraceExporter):
    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def export(self, spans: list[TraceSpan]) -> None:
        for span in spans:
            if self.verbose:
                print(f"\n{'=' * 60}")
                print(f"Span: {span.name}")
                print(f"Kind: {span.kind.value}")
                print(f"Duration: {span.duration_ms():.2f}ms")
                print(f"Status: {span.status.value}")
                if span.error_message:
                    print(f"Error: {span.error_message}")
                if span.inputs:
                    print(f"Inputs: {json.dumps(span.inputs, ensure_ascii=False, indent=2)}")
                if span.outputs:
                    print(f"Outputs: {json.dumps(span.outputs, ensure_ascii=False, indent=2)}")
                if span.events:
                    print("Events:")
                    for event in span.events:
                        print(f"  - {event.name}: {event.attributes}")
            else:
                status_icon = "✓" if span.status.value == "ok" else "✗"
                print(f"{status_icon} {span.name} ({span.kind.value}) - {span.duration_ms():.2f}ms")


class FileExporter(TraceExporter):
    def __init__(
        self,
        directory: str = "./traces",
        format: str = "jsonl",
        max_file_size_mb: int = 100,
    ):
        self.directory = Path(directory)
        self.format = format
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.directory.mkdir(parents=True, exist_ok=True)
        self._current_file: Optional[Path] = None
        self._file_size = 0

    def _get_current_file(self) -> Path:
        today = datetime.now().strftime("%Y%m%d")
        if self._current_file is None:
            files = list(self.directory.glob(f"traces_{today}_*.{self.format}"))
            if files:
                self._current_file = files[-1]
                self._file_size = self._current_file.stat().st_size if self._current_file.exists() else 0
            else:
                idx = len(files)
                self._current_file = self.directory / f"traces_{today}_{idx:04d}.{self.format}"
        if self._file_size >= self.max_file_size:
            idx = len(list(self.directory.glob(f"traces_{today}_*.{self.format}")))
            self._current_file = self.directory / f"traces_{today}_{idx:04d}.{self.format}"
            self._file_size = 0
        return self._current_file

    def export(self, spans: list[TraceSpan]) -> None:
        file_path = self._get_current_file()
        with open(file_path, "a", encoding="utf-8") as f:
            if self.format == "jsonl":
                for span in spans:
                    f.write(json.dumps(span.to_dict(), ensure_ascii=False) + "\n")
                    self._file_size += len(json.dumps(span.to_dict()))
            elif self.format == "json":
                data = [span.to_dict() for span in spans]
                f.write(json.dumps(data, ensure_ascii=False, indent=2))
        logger.debug(f"Exported {len(spans)} spans to {file_path}")


class LangSmithExporter(TraceExporter):
    def __init__(
        self,
        api_key: Optional[str] = None,
        project_name: str = "taiji_agent",
        endpoint: str = "https://api.smith.langchain.com",
    ):
        self.api_key = api_key or os.getenv("LANGSMITH_API_KEY")
        self.project_name = project_name
        self.endpoint = endpoint
        self._client: Optional[Any] = None
        if self.api_key:
            self._init_client()

    def _init_client(self) -> None:
        try:
            import httpx

            self._client = httpx.Client(
                base_url=self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        except ImportError:
            logger.warning("httpx not installed, LangSmith export disabled")

    def export(self, spans: list[TraceSpan]) -> None:
        if not self._client:
            logger.warning("LangSmith client not initialized")
            return
        if not spans:
            return
        try:
            for span in spans:
                self._client.post(
                    "/api/v1/runs",
                    json=self._convert_to_langsmith_run(span),
                )
            logger.debug(f"Exported {len(spans)} spans to LangSmith")
        except Exception as e:
            logger.error(f"Failed to export to LangSmith: {e}")

    def _convert_to_langsmith_run(self, span: TraceSpan) -> dict[str, Any]:
        return {
            "id": span.span_id,
            "trace_id": span.trace_id,
            "name": span.name,
            "run_type": span.kind.value,
            "start_time": datetime.fromtimestamp(span.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(span.end_time).isoformat() if span.end_time else None,
            "extra": {
                "attributes": span.attributes,
                "events": [e.to_dict() for e in span.events],
            },
            "error": span.error_message,
            "inputs": span.inputs or {},
            "outputs": span.outputs or {},
        }


class MultiExporter(TraceExporter):
    def __init__(self, exporters: list[TraceExporter]):
        self.exporters = exporters

    def export(self, spans: list[TraceSpan]) -> None:
        for exporter in self.exporters:
            try:
                exporter.export(spans)
            except Exception as e:
                logger.error(f"Exporter {exporter.__class__.__name__} failed: {e}")

    def flush(self) -> None:
        for exporter in self.exporters:
            exporter.flush()
