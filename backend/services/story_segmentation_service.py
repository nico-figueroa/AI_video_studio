import re


class StorySegmentationService:
    @staticmethod
    def segments(text: str, maximum: int = 6) -> list[str]:
        units = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n\s*\n", text) if part.strip()]
        if len(units) <= maximum:
            return units
        return [
            " ".join(units[len(units)*index//maximum:len(units)*(index+1)//maximum])
            for index in range(maximum)
        ]

    @staticmethod
    def describe(project) -> dict:
        scenes = sorted(project.scenes, key=lambda item: item.scene_number)
        analysis = project.narrative_analysis or {}
        beats = []
        for number in sorted({scene.beat_number for scene in scenes}):
            group = [scene for scene in scenes if scene.beat_number == number]
            details = next((item for item in analysis.get("beats", []) if item["number"] == number), {})
            beats.append({
                "number": number, "title": details.get("title", f"Beat {number}"),
                "purpose": details.get("purpose", "Review supplied or legacy scene grouping."),
                "timeline_progression": details.get("timeline_progression", ""),
                "character_introductions": details.get("character_introductions", []),
                "transition": details.get("transition", ""),
                "scene_ids": [scene.id for scene in group],
            })
        return {"source": analysis.get("source", "supplied_or_legacy_grouping_not_semantic_analysis"), "beats": beats}
