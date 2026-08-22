from pydantic import BaseModel, Field
from typing import Any, Optional, Type, Dict


class BaseTool(BaseModel):
    name: str = ""
    description: str = ""
    args_schema: Optional[Type[BaseModel]] = None

    def run(self, *args, **kwargs) -> Any:
        return self._run(*args, **kwargs)

    def _run(self, *args, **kwargs) -> Any:
        raise NotImplementedError
