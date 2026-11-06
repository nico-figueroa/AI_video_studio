from models.models import Estimate, Project


PLAN_SETTINGS: dict[str, dict[str, float | int | str]] = {
    "economy": {
        "scene_cost": 0.09,
        "minutes_per_scene": 0.7,
        "resolution": "720p",
        "quality_score": 62,
        "storage_mb": 10,
        "gpu_minutes": 0.4,
    },
    "balanced": {
        "scene_cost": 0.24,
        "minutes_per_scene": 1.4,
        "resolution": "1080p",
        "quality_score": 82,
        "storage_mb": 24,
        "gpu_minutes": 1.2,
    },
    "premium": {
        "scene_cost": 0.52,
        "minutes_per_scene": 2.8,
        "resolution": "1080p enhanced",
        "quality_score": 94,
        "storage_mb": 48,
        "gpu_minutes": 2.8,
    },
}


class EstimationService:
    def calculate(self, project: Project, scene_count: int) -> list[dict[str, object]]:
        estimates = []
        for name, settings in PLAN_SETTINGS.items():
            estimates.append(
                {
                    "plan_name": name,
                    "estimated_cost": round(float(settings["scene_cost"]) * scene_count, 2),
                    "estimated_minutes": max(
                        1, round(float(settings["minutes_per_scene"]) * scene_count)
                    ),
                    "resolution": settings["resolution"],
                    "quality_score": settings["quality_score"],
                    "storage_mb": float(settings["storage_mb"]) * scene_count,
                    "gpu_minutes": round(float(settings["gpu_minutes"]) * scene_count, 1),
                }
            )
        return estimates

    @staticmethod
    def as_comparison(estimates: list[Estimate]) -> dict[str, object]:
        plans = {estimate.plan_name: estimate for estimate in estimates}
        return {
            name: {
                "plan_name": name,
                "estimated_cost": estimate.estimated_cost,
                "estimated_minutes": estimate.estimated_minutes,
                "resolution": estimate.resolution,
                "quality_score": estimate.quality_score,
                "storage_mb": estimate.storage_mb,
                "gpu_minutes": estimate.gpu_minutes,
            }
            for name, estimate in plans.items()
        } | {"simulated": True, "actual_provider_cost": 0.0}
