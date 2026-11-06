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


class CharacterBible(BaseModel):
    characters: list[CharacterBibleData]


class ScenePlanData(BaseModel):
    scene_number: int = Field(ge=1)
    scene_title: str = Field(min_length=1, max_length=160)
    scene_description: str
    visual_description: str
    image_prompt: str
    estimated_duration: int = Field(ge=1, le=3600)


class ScenePlan(BaseModel):
    scenes: list[ScenePlanData]
