"""Non-fatal, JSON-safe Forward performance and process-memory diagnostics."""
import ctypes
import importlib
import os
import time


def _empty_memory(reason="unavailable"):
    return {"telemetry_available": False, "total_physical_memory_bytes": None,
        "available_physical_memory_bytes": None, "process_working_set_bytes": None,
        "process_lifetime_peak_working_set_bytes": None,
        "physical_memory_telemetry_available": False,
        "process_memory_telemetry_available": False,
        "physical_memory_unavailable_reason": reason,
        "process_memory_unavailable_reason": reason,
        "unavailable_reason": reason}


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong),
        ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong),
        ("total_page_file", ctypes.c_ulonglong), ("available_page_file", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
        ("available_extended_virtual", ctypes.c_ulonglong)]


def get_process_memory_snapshot():
    """Observe current memory without exposing machine/user/path information."""
    result = _empty_memory()
    if os.name != "nt":
        return result
    try:
        status = _MemoryStatusEx()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx returned failure")
        result["total_physical_memory_bytes"] = int(status.total_physical)
        result["available_physical_memory_bytes"] = int(status.available_physical)
        result["physical_memory_telemetry_available"] = True
        result["physical_memory_unavailable_reason"] = None
    except BaseException:
        result["physical_memory_unavailable_reason"] = "windows_global_memory_status_unavailable"
    try:
        diagnostics = importlib.import_module("System.Diagnostics")
        process = diagnostics.Process.GetCurrentProcess()
        result["process_working_set_bytes"] = int(process.WorkingSet64)
        result["process_lifetime_peak_working_set_bytes"] = int(process.PeakWorkingSet64)
        result["process_memory_telemetry_available"] = True
        result["process_memory_unavailable_reason"] = None
    except BaseException:
        result["process_memory_unavailable_reason"] = "dotnet_process_memory_unavailable"
    result["telemetry_available"] = bool(result["physical_memory_telemetry_available"] or
        result["process_memory_telemetry_available"])
    result["unavailable_reason"] = None if result["telemetry_available"] else "windows_memory_telemetry_unavailable"
    return result


def select_duration_chunk_size(memory_snapshot=None, requested_chunk_size=None):
    """Choose execution chunk only; calculation resolution and precision never change."""
    snapshot = memory_snapshot if isinstance(memory_snapshot, dict) else _empty_memory("invalid_telemetry")
    available = snapshot.get("available_physical_memory_bytes")
    working_set = snapshot.get("process_working_set_bytes")
    fallback = False
    reason = None
    if requested_chunk_size is not None:
        try:
            selected = max(4096, min(32768, int(requested_chunk_size)))
            reason = "explicit_test_or_internal_override"
        except (TypeError, ValueError, OverflowError):
            selected, fallback, reason = 8192, True, "invalid_requested_chunk_size"
    elif not isinstance(available, (int, float)) or available < 0:
        selected, fallback, reason = 8192, True, "available_memory_unavailable"
    elif available < 1024 ** 3:
        selected, reason = 4096, "low_available_memory"
    elif available < 4 * 1024 ** 3:
        selected, reason = 8192, "moderate_available_memory"
    else:
        selected, reason = 32768, "high_available_memory"
    return {"telemetry_available": bool(snapshot.get("telemetry_available")),
        "available_memory_bytes": available, "process_working_set_bytes": working_set,
        "selected_chunk_size": selected, "fallback_used": fallback,
        "fallback_reason": reason if fallback else None, "selection_reason": reason,
        "minimum_chunk_size": 4096, "maximum_chunk_size": 32768}


class ForwardPerformanceRecorder(object):
    def __init__(self, snapshot_provider=None, clock=None):
        self._snapshot = snapshot_provider or get_process_memory_snapshot
        self._clock = clock or time.perf_counter
        self._total_before = self._safe_snapshot()
        self._started = self._clock()
        self._active = {}
        self.stages = {}

    def _safe_snapshot(self):
        try: return self._snapshot()
        except BaseException: return _empty_memory("snapshot_failure")

    def begin(self, name):
        before = self._safe_snapshot()
        started = self._clock()
        self._active[name] = (started, before)

    def end(self, name):
        ended = self._clock()
        started, before = self._active.pop(name, (ended, _empty_memory("stage_not_started")))
        after = self._safe_snapshot()
        self.stages[name] = {"elapsed_ms": (ended - started) * 1000.0,
            "process_working_set_before_bytes": before.get("process_working_set_bytes"),
            "process_working_set_after_bytes": after.get("process_working_set_bytes")}

    def result(self, workload_summary=None):
        ended = self._clock()
        final = self._safe_snapshot()
        stages = dict(self.stages)
        stages["total"] = {"elapsed_ms": (ended - self._started) * 1000.0,
            "process_working_set_before_bytes": self._total_before.get("process_working_set_bytes"),
            "process_working_set_after_bytes": final.get("process_working_set_bytes")}
        return {"available": True, "memory": final, "stages": stages,
            "workload_summary": dict(workload_summary or {}),
            "stage_elapsed_excludes_boundary_memory_snapshot_time": True,
            "total_elapsed_includes_instrumentation_between_total_boundaries": True,
            "stage_memory_values_are_observations_not_peaks": True}
