from abc import ABC
from typing import Literal, Annotated, Union

from pydantic import BaseModel, Field as PydanticField


class ComplexAnswerABC(BaseModel, ABC):
    kind: Literal[None]


class ComplexAnswerFileUpload(ComplexAnswerABC):
    kind: Literal["file_upload"] = "file_upload"
    filename: str
    encrypted: bool


ComplexAnswerUnion = Annotated[
    Union[  # noqa: UP007
        ComplexAnswerFileUpload
    ],
    PydanticField(discriminator="kind"),
]
