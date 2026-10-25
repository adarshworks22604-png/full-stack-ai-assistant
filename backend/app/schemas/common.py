from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Rejects unknown fields so the contract stays explicit."""

    model_config = ConfigDict(extra="forbid")
