"""Judge a surrogate against engine truth on designs it never trained on, and keep the report."""

from __future__ import annotations

import json
from pathlib import Path

from ..corpus import tile_lookup
from ..corpus.tile_paths import TilePaths
from ..surrogate.assessment import assess
from ..surrogate.assessment_inputs import AssessmentInputs
from ..surrogate.patches import tile_key
from .assessment_outcome import AssessmentOutcome
from .assessment_request import AssessmentRequest
from .json_file import read_object
from .missing_stage import MissingStage
from .model_catalog import ModelCatalog
from .model_summary import ModelSummary
from .progress_listener import ProgressListener

PHASE = "comparing surrogate against engine truth"


class AssessmentService:
    """Finds a city's model and the tile to judge it on, runs the comparison, writes the report."""

    def __init__(self, tiles_root: Path, models_root: Path) -> None:
        self._tiles_root = Path(tiles_root)
        self._models = ModelCatalog(models_root)

    def assess(self, request: AssessmentRequest, progress: ProgressListener) -> AssessmentOutcome:
        model_dir, surrogate_dir, bundle = self._inputs(request)
        progress.phase(PHASE)
        report = assess(AssessmentInputs(model_dir, surrogate_dir, bundle, only=request.design))
        report_path = model_dir / assessment_name(model_dir, bundle)
        report_path.write_text(json.dumps(report, indent=2))
        progress.finished(report)
        headline = report.get("headline", {})
        return AssessmentOutcome(
            model_dir=str(model_dir),
            report_path=str(report_path),
            skill=float(headline.get("mean_skill", 0.0)),
            beats_nothing=bool(headline.get("all_beat_predicting_nothing", False)),
            error=float(headline.get("mean_aggregate_relative_error", 0.0)),
            spearman=report.get("ranking", {}).get("spearman"),
            speedup=report.get("speed", {}).get("speedup"),
            report=report,
        )

    def model_for(
        self, target: str, model: str | None, tile: str | None
    ) -> tuple[Path, Path, Path]:
        """For a city: the model directory, the surrogate directory and the bundle to judge it on.

        Three answers because an assessment needs all three, and three arguments because the
        model and the tile are each optional refinements of the city.
        """
        paths = self._assessment_tile(target, tile)
        found = self.model_summary(target, model)
        return Path(found.path), paths.surrogate, paths.bundle

    def model_summary(self, target: str, model: str | None) -> ModelSummary:
        """The named model of the city, or its newest."""
        centre = tile_lookup.centre_id(target)
        return self._models.named(centre, model) if model else self._models.newest(centre)

    def _inputs(self, request: AssessmentRequest) -> tuple[Path, Path, Path]:
        if Path(request.target).is_dir():
            if request.surrogate_dir is None or request.bundle is None:
                raise ValueError("a model directory needs SURROGATE_DIR and BUNDLE after it")
            return Path(request.target), Path(request.surrogate_dir), Path(request.bundle)
        return self.model_for(request.target, request.model, request.tile)

    def _assessment_tile(self, target: str, tile: str | None) -> TilePaths:
        try:
            found = tile_lookup.generated_tiles(target, None, self._tiles_root)
        except ValueError as exc:
            raise MissingStage(
                "physics", target, f"sdc surrogate treeshade generate {target}"
            ) from exc
        if tile is None:
            return tile_lookup.densest_generated_tile(target, self._tiles_root)
        chosen = [paths for paths in found if paths.tile.id == tile]
        if not chosen:
            raise ValueError(f"{target} tile {tile} has no generated physics")
        return chosen[0]


def assessment_name(model_dir: Path, bundle: Path) -> str:
    """assessment.json for a model of one tile; assessment-<tile>.json for a pooled model."""
    tiles = read_object(Path(model_dir) / "manifest.json").get("data", {}).get("tiles", [])
    if len(tiles) <= 1:
        return "assessment.json"
    return f"assessment-{tile_key(bundle).replace(':', '-')}.json"
