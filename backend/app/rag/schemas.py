import uuid

from pydantic import BaseModel, Field, field_validator


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        if len(value := value.strip()) < 2:
            raise ValueError("question must contain at least 2 characters")
        return value


class CitationOut(BaseModel):
    label: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    original_name: str
    page_number: int | None
    position: int
    content: str
    score: float


class AnswerOut(BaseModel):
    answer: str
    citations: list[CitationOut]
