from typing import Annotated, TypedDict, List
import operator
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    sender: str
    summary: str
    next_agent: str
    workspace_id: str
    user_id: str