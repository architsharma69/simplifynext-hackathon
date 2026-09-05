from typing import Literal

from pydantic import BaseModel


class RephrasedQuery(BaseModel):
    specialist: Literal["hr", "finance", "document"]
    query: str


class RoutingDecision(BaseModel):
    # No default values: OpenAI's strict structured-output mode requires every
    # property to appear in the schema's `required` list, which Pydantic only
    # does for fields without a default. The LLM always fills every field,
    # using [] / null for whichever don't apply to a given route_type.
    #
    # rephrased_queries is a list of {specialist, query}, not a dict, because
    # OpenAI's strict mode doesn't support open-ended dict/object schemas
    # (there's no fixed set of keys to put in `required`).
    route_type: Literal["delegate", "direct", "clarify"]
    specialists: list[Literal["hr", "finance", "document"]]
    rephrased_queries: list[RephrasedQuery]
    direct_answer: str | None
    clarifying_question: str | None
