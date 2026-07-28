from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages


Intent = Literal["twin_analyst", "scenario_explainer", "general"]


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    factory_id: str
    rewritten_query: str
    intent: Intent
    retrieved_context: str
    conversation_summary: str
    turn_count: int