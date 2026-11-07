from pydantic import BaseModel, Field


class CharacterSeed(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=120)
    premise: str = Field(min_length=1, max_length=2000)


class ThreeActStructure(BaseModel):
    act_one: str
    act_two: str
    act_three: str


class StoryBibleData(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=6000)
    genre: str = Field(max_length=120)
    target_audience: str = Field(max_length=240)
    three_act_structure: ThreeActStructure
    main_characters: list[CharacterSeed]


class CharacterBibleData(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str
    personality: str
    appearance: str
    motivations: str
    relationships: str
    portrait_prompt: str
    clothing: str = ""
    age: str = Field(default="", max_length=120)
    distinctive_traits: str = ""
    negative_prompt: str = ""
    facial_features: str = ""


class CharacterBible(BaseModel):
    characters: list[CharacterBibleData]


class ScenePlanData(BaseModel):
    scene_number: int = Field(ge=1)
    scene_title: str = Field(min_length=1, max_length=160)
    scene_description: str
    visual_description: str
    image_prompt: str
    estimated_duration: int = Field(ge=1, le=3600)
    beat_number: int = Field(default=1, ge=1, le=6)


class ScenePlan(BaseModel):
    scenes: list[ScenePlanData]


class NarrativeBeatData(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=2000)
    timeline_progression: str
    character_introductions: list[str]
    transition: str
    scenes: list[ScenePlanData] = Field(min_length=2, max_length=4)


class NarrativeScenePlan(BaseModel):
    beats: list[NarrativeBeatData] = Field(min_length=2, max_length=6)
