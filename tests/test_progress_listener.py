"""One progress vocabulary for every operation; the null listener and the dashboard speak it."""

from shadecast.service.null_progress import NullProgress
from shadecast.service.progress_listener import ProgressListener
from shadecast.surrogate.simulation_progress import SimulationProgress


def _speak(listener: ProgressListener) -> None:
    listener.started("ahmedabad t43N_249_2547", total=3, done=1)
    listener.phase("baseline physics")
    listener.step_done("baseline", 12.0, {})
    listener.step_started("clustered_0101", {"target": None})
    listener.step_done("clustered_0101", 10.0, {"id": "clustered_0101", "engine_seconds": 10.0})
    listener.step_skipped("random_uniform_0201", "empty placement")
    listener.step_failed("corridor_0302", "engine exited 1")
    listener.warning("one engine was slow")
    listener.finished({"entries": 2})


def test_the_null_listener_accepts_every_event():
    listener = NullProgress()
    assert isinstance(listener, ProgressListener)
    _speak(listener)


def test_the_simulation_dashboard_speaks_the_vocabulary_and_keeps_its_readings():
    progress = SimulationProgress.quiet()
    assert isinstance(progress, ProgressListener)
    with progress:
        _speak(progress)
    assert progress.completed() == 3
    assert progress.baseline_seconds == 12.0
    assert progress.mean_seconds() == 10.0
    assert progress.failed == ["corridor_0302: engine exited 1"]
    assert progress.state == "done"
