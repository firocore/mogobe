from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

Username = Annotated[str, Field(min_length=4, max_length=15, pattern=r"^[A-Za-zА-Яа-яЁё0-9_]+$")]


class Credentials(BaseModel):
    username: Username
    password: SecretStr = Field(min_length=1, max_length=128)
    remember_me: bool = False


class RegistrationStart(Credentials):
    password: SecretStr = Field(min_length=4, max_length=10)
    color_id: int = Field(ge=1, le=12)


class RegistrationFinish(BaseModel):
    age: int = Field(ge=1, le=100, strict=True)
    chat_mode: Literal["open", "closed"]
    accepted_terms: bool = False
    newsletter: bool = False
    parent_email: EmailStr | None = Field(default=None, max_length=254)


class AccountPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    color_id: int
    age: int
    chat_mode: str


class ResumeSession(BaseModel):
    username: Username
