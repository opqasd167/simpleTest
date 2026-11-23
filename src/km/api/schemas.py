from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class FeedbackRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    helpful: bool
    comment: str = Field(default="", max_length=1000)
