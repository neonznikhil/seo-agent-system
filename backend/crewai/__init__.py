from pydantic import BaseModel, Field
from typing import Any, List, Optional, Callable, Dict


class Agent(BaseModel):
    role: str = ""
    goal: str = ""
    backstory: str = ""
    verbose: bool = True
    allow_delegation: bool = False
    tools: List[Any] = Field(default_factory=list)
    llm: Any = None


class Task(BaseModel):
    description: str = ""
    expected_output: str = ""
    agent: Optional[Agent] = None
    context: Optional[List[Any]] = None


class Process:
    sequential = "sequential"
    hierarchical = "hierarchical"


class Crew(BaseModel):
    agents: List[Agent] = Field(default_factory=list)
    tasks: List[Task] = Field(default_factory=list)
    process: Any = Process.sequential
    verbose: bool = True

    def kickoff(self, inputs: Optional[dict] = None) -> Any:
        return "Autonomous crew planning completed."
