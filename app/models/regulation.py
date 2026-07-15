from pydantic import BaseModel


class Regulation(BaseModel):

    title: str

    publish_date: str | None

    category: str

    impact_level: str

    affected_products: list[str]

    actions_required: list[str]