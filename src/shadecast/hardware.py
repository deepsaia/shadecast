"""What the machine has and how busy it is, for the progress displays of long runs.

The engine picks CUDA when it exists and the CPU otherwise; it has no path for Apple's
GPU, so on a Mac every run is CPU work and the number of cores is the whole budget.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import psutil
import torch

GIGABYTE = 1e9


@dataclass(frozen=True)
class Hardware:
    cores: int
    physical_cores: int | None
    load_1min: float  # runnable threads averaged over the last minute
    cpu_percent: float
    memory_total_gb: float
    memory_used_gb: float
    engine_device: str

    @classmethod
    def snapshot(cls) -> Hardware:
        """Read the machine now. cpu_percent is since the previous call, 0 on the first."""
        memory = psutil.virtual_memory()
        return cls(
            cores=os.cpu_count() or 1,
            physical_cores=psutil.cpu_count(logical=False),
            load_1min=os.getloadavg()[0],
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_total_gb=memory.total / GIGABYTE,
            memory_used_gb=memory.used / GIGABYTE,
            engine_device="cuda" if torch.cuda.is_available() else "cpu",
        )

    @property
    def cores_free(self) -> float:
        return max(0.0, self.cores - self.load_1min)

    @property
    def memory_free_gb(self) -> float:
        return max(0.0, self.memory_total_gb - self.memory_used_gb)

    def header(self, jobs: int, threads_per_job: int | None) -> str:
        """One line for the start of a run: what there is and what the run will take."""
        threads = f"{threads_per_job} threads each" if threads_per_job else "all threads"
        gpu = "" if self.engine_device == "cuda" else ", GPU unused by the engine"
        return (
            f"{self.cores} cores, {self.memory_total_gb:.0f} GB; engine on {self.engine_device}"
            f"{gpu}; {jobs} engine run{'s' if jobs != 1 else ''} at a time, {threads}"
        )

    def status(self) -> str:
        """A short live reading: cpu, free cores by load, memory."""
        return (
            f"cpu {self.cpu_percent:3.0f}%  load {self.load_1min:.1f}/{self.cores}"
            f"  mem {self.memory_used_gb:.0f}/{self.memory_total_gb:.0f} GB"
        )
