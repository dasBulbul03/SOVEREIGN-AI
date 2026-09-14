from pydantic import BaseModel, ConfigDict, Field


class QuoteLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: str = Field(min_length=1, max_length=160)
    item: str = Field(min_length=1, max_length=240)
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    lead_time_days: int | None = Field(default=None, ge=0)
    warranty_months: int | None = Field(default=None, ge=0)
    declared_compliant: bool | None = None
    source_id: str = Field(min_length=1, max_length=20)
    source_name: str = Field(min_length=1, max_length=255)
    page: int = Field(default=1, ge=1)

    @property
    def line_total(self) -> float:
        return round(self.quantity * self.unit_price, 2)


class ProcurementPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maximum_budget: float | None = Field(default=None, ge=0)
    maximum_lead_days: int | None = Field(default=None, ge=0)
    minimum_warranty_months: int | None = Field(default=None, ge=0)
    required_currency: str | None = Field(default=None, min_length=3, max_length=3)


class VendorEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: str
    currency: str
    total: float
    line_count: int
    maximum_lead_days: int | None
    minimum_warranty_months: int | None
    compliant: bool
    issues: list[str] = Field(default_factory=list)


class ProcurementComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[QuoteLine]
    policy: ProcurementPolicy
    vendors: list[VendorEvaluation]
    recommended_vendor: str | None
    recommendation_basis: str
    warnings: list[str] = Field(default_factory=list)
