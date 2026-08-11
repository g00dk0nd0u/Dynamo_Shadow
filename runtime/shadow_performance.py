"""Non-fatal, JSON-safe Forward performance and process-memory diagnostics."""
import importlib
import os
import time


def _empty_memory(reason="unavailable"):
    return {"telemetry_available": False, "total_physical_memory_bytes": None,
        "available_physical_memory_bytes": None, "process_working_set_bytes": None,
        "process_lifetime_peak_working_set_bytes": None, "unavailable_reason": reason}


def get_process_memory_snapshot():
    """Observe current memory without exposing machine/user/path information."""
    result = _empty_memory()
    if os.name != "nt":
        return result
    try:
        diagnostics = importlib.import_module("System.Diagnostics")
        process = diagnostics.Process.GetCurrentProcess()
        result["process_working_set_bytes"] = int(process.WorkingSet64)
        result["process_lifetime_peak_working_set_bytes"] = int(process.PeakWorkingSet64)
        result["telemetry_available"] = True
        result["unavailable_reason"] = None
    except BaseException:
        pass
    try:
        devices = importlib.import_module("Microsoft.VisualBasic.Devices")
        info = devices.ComputerInfo()
        result["total_physical_memory_bytes"] = int(info.TotalPhysicalMemory)
        result["available_physical_memory_bytes"] = int(info.AvailablePhysicalMemory)
        result["telemetry_available"] = True
        result["unavailable_reason"] = None
    except BaseException:
        pass
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
    def __init__(self, snapshot_provider=None):
        self._snapshot = snapshot_provider or get_process_memory_snapshot
        self._started = time.perf_counter()
        self._active = {}
        self.stages = {}

    def begin(self, name):
        try:
            self._active[name] = (time.perf_counter(), self._snapshot())
        except BaseException:
            self._active[name] = (time.perf_counter(), _empty_memory("snapshot_failure"))

    def end(self, name):
        started, before = self._active.pop(name, (time.perf_counter(), _empty_memory("stage_not_started")))
        try: after = self._snapshot()
        except BaseException: after = _empty_memory("snapshot_failure")
        self.stages[name] = {"elapsed_ms": (time.perf_counter() - started) * 1000.0,
            "process_working_set_before_bytes": before.get("process_working_set_bytes"),
            "process_working_set_after_bytes": after.get("process_working_set_bytes")}

    def result(self):
        try: final = self._snapshot()
        except BaseException: final = _empty_memory("snapshot_failure")
        stages = dict(self.stages)
        stages["total"] = {"elapsed_ms": (time.perf_counter() - self._started) * 1000.0,
            "process_working_set_before_bytes": None,
            "process_working_set_after_bytes": final.get("process_working_set_bytes")}
        return {"available": True, "memory": final, "stages": stages,
            "stage_memory_values_are_observations_not_peaks": True}
