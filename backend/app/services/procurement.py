import csv
import io
import re
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from app.core.errors import AppError
from app.procurement.types import (
    ProcurementComparison,
    ProcurementPolicy,
    QuoteLine,
    VendorEvaluation,
)

HEADER_ALIASES = {
    "vendor": {"vendor", "supplier", "bidder"},
    "item": {"item", "description", "product", "material"},
    "quantity": {"quantity", "qty"},
    "unit_price": {"unit_price", "unit price", "price", "rate"},
    "currency": {"currency", "ccy"},
    "lead_time_days": {"lead_time_days", "lead time days", "lead_days", "delivery_days"},
    "warranty_months": {"warranty_months", "warranty months", "warranty"},
    "compliant": {"compliant", "compliance", "meets_specification"},
}


def _clean_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold().replace("-", "_")).replace("_", " ")


def _header_map(fieldnames: Sequence[str]) -> dict[str, str]:
    normalized = {_clean_header(field): field for field in fieldnames}
    resolved: dict[str, str] = {}
    for canonical, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            key = _clean_header(alias)
            if key in normalized:
                resolved[canonical] = normalized[key]
                break
    return resolved


def _number(value: str, field: str, source_name: str) -> float:
    cleaned = re.sub(r"[^0-9.\-]", "", value.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError as exc:
        raise AppError(
            "PROCUREMENT_VALUE_INVALID",
            f"{source_name} contains an invalid {field} value: {value!r}.",
            422,
        ) from exc


def _optional_int(value: str | None, field: str, source_name: str) -> int | None:
    if value is None or not value.strip():
        return None
    return int(_number(value, field, source_name))


def _optional_bool(value: str | None) -> bool | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().casefold()
    if normalized in {"yes", "true", "pass", "compliant", "1"}:
        return True
    if normalized in {"no", "false", "fail", "non-compliant", "noncompliant", "0"}:
        return False
    return None


def _csv_lines(evidence: list[dict[str, Any]]) -> list[QuoteLine]:
    lines: list[QuoteLine] = []
    for source in evidence:
        text = str(source.get("text", ""))
        candidates = [line for line in text.splitlines() if not line.startswith("[Page ")]
        if not candidates or "," not in candidates[0]:
            continue
        reader = csv.DictReader(io.StringIO("\n".join(candidates)))
        if not reader.fieldnames:
            continue
        columns = _header_map(reader.fieldnames)
        if not {"vendor", "item", "quantity", "unit_price"}.issubset(columns):
            continue
        source_name = str(source.get("display_name", "Quotation"))
        source_id = str(source.get("source_id", "S?"))
        for index, row in enumerate(reader, start=2):
            if not any(str(value or "").strip() for value in row.values()):
                continue
            vendor = str(row.get(columns["vendor"], "")).strip()
            item = str(row.get(columns["item"], "")).strip()
            if not vendor or not item:
                raise AppError(
                    "PROCUREMENT_ROW_INVALID",
                    f"{source_name} row {index} requires vendor and item values.",
                    422,
                )
            quantity = _number(str(row.get(columns["quantity"], "")), "quantity", source_name)
            unit_price = _number(
                str(row.get(columns["unit_price"], "")), "unit price", source_name
            )
            currency = str(row.get(columns.get("currency", ""), "INR") or "INR").upper()
            if len(currency) != 3:
                raise AppError(
                    "PROCUREMENT_CURRENCY_INVALID",
                    f"{source_name} row {index} must use a three-letter currency code.",
                    422,
                )
            lines.append(
                QuoteLine(
                    vendor=vendor,
                    item=item,
                    quantity=quantity,
                    unit_price=unit_price,
                    currency=currency,
                    lead_time_days=_optional_int(
                        row.get(columns.get("lead_time_days", "")), "lead time", source_name
                    ),
                    warranty_months=_optional_int(
                        row.get(columns.get("warranty_months", "")), "warranty", source_name
                    ),
                    declared_compliant=_optional_bool(
                        row.get(columns.get("compliant", ""))
                    ),
                    source_id=source_id,
                    source_name=source_name,
                    page=int(source.get("page_start", 1)),
                )
            )
    return lines


def _policy(evidence: list[dict[str, Any]]) -> ProcurementPolicy:
    text = "\n".join(str(item.get("text", "")) for item in evidence)
    patterns: dict[str, str] = {
        "maximum_budget": r"(?:maximum|max|approved)\s+budget\D{0,20}([0-9][0-9,]*(?:\.\d+)?)",
        "maximum_lead_days": (
            r"(?:maximum|max)\s+(?:delivery|lead)(?:\s+time)?\D{0,15}(\d+)\s*days?"
        ),
        "minimum_warranty_months": r"(?:minimum|min|required)\s+warranty\D{0,15}(\d+)\s*months?",
    }
    values: dict[str, object] = {}
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            number = float(match.group(1).replace(",", ""))
            values[field] = number if field == "maximum_budget" else int(number)
    currency = re.search(r"(?:required\s+currency|currency)\s*[:=-]\s*([A-Z]{3})\b", text, re.I)
    if currency:
        values["required_currency"] = currency.group(1).upper()
    return ProcurementPolicy.model_validate(values)


def compare_procurement(evidence: list[dict[str, Any]]) -> ProcurementComparison:
    lines = _csv_lines(evidence)
    if not lines:
        raise AppError(
            "PROCUREMENT_QUOTES_REQUIRED",
            "No structured quotation rows were found. Upload CSV files with vendor, item, "
            "quantity, and unit_price columns.",
            422,
        )
    policy = _policy(evidence)
    grouped: dict[tuple[str, str], list[QuoteLine]] = defaultdict(list)
    for line in lines:
        grouped[(line.vendor, line.currency)].append(line)
    vendors: list[VendorEvaluation] = []
    for (vendor, currency), vendor_lines in sorted(grouped.items()):
        total = round(sum(item.line_total for item in vendor_lines), 2)
        leads = [item.lead_time_days for item in vendor_lines if item.lead_time_days is not None]
        warranties = [
            item.warranty_months for item in vendor_lines if item.warranty_months is not None
        ]
        max_lead = max(leads) if leads else None
        min_warranty = min(warranties) if warranties else None
        issues: list[str] = []
        if any(item.declared_compliant is False for item in vendor_lines):
            issues.append("A quotation line is declared non-compliant")
        if policy.maximum_budget is not None and total > policy.maximum_budget:
            issues.append(f"Total exceeds the maximum budget of {policy.maximum_budget:,.2f}")
        if policy.maximum_lead_days is not None and (
            max_lead is None or max_lead > policy.maximum_lead_days
        ):
            issues.append(f"Lead time does not meet the {policy.maximum_lead_days}-day maximum")
        if policy.minimum_warranty_months is not None and (
            min_warranty is None or min_warranty < policy.minimum_warranty_months
        ):
            issues.append(
                f"Warranty does not meet the {policy.minimum_warranty_months}-month minimum"
            )
        if policy.required_currency and currency != policy.required_currency:
            issues.append(f"Currency is not {policy.required_currency}")
        vendors.append(
            VendorEvaluation(
                vendor=vendor,
                currency=currency,
                total=total,
                line_count=len(vendor_lines),
                maximum_lead_days=max_lead,
                minimum_warranty_months=min_warranty,
                compliant=not issues,
                issues=issues,
            )
        )
    eligible = [item for item in vendors if item.compliant]
    currency_groups = {item.currency for item in eligible}
    warnings: list[str] = []
    recommended: str | None = None
    if len(currency_groups) > 1:
        warnings.append("Compliant bids use different currencies and cannot be ranked safely.")
    elif eligible:
        recommended = min(eligible, key=lambda item: (item.total, item.vendor.casefold())).vendor
    if len({item.vendor.casefold() for item in vendors}) < 2:
        warnings.append("Only one vendor was found; competitive comparison is not possible.")
    basis = (
        "Lowest evaluated total among bids that satisfy every extracted policy constraint."
        if recommended
        else "No automatic award recommendation; responsible procurement review is required."
    )
    return ProcurementComparison(
        lines=lines,
        policy=policy,
        vendors=vendors,
        recommended_vendor=recommended,
        recommendation_basis=basis,
        warnings=warnings,
    )


def comparison_markdown(comparison: ProcurementComparison) -> str:
    rows = [
        "| Vendor | Evaluated total | Lead | Warranty | Compliance |",
        "|---|---:|---:|---:|---|",
    ]
    for vendor in comparison.vendors:
        lead = (
            str(vendor.maximum_lead_days)
            if vendor.maximum_lead_days is not None
            else "Unknown"
        )
        warranty = (
            str(vendor.minimum_warranty_months)
            if vendor.minimum_warranty_months is not None
            else "Unknown"
        )
        rows.append(
            f"| {vendor.vendor} | {vendor.currency} {vendor.total:,.2f} | "
            f"{lead} | {warranty} | "
            f"{'Pass' if vendor.compliant else 'Review'} |"
        )
    recommendation = (
        f"Recommend **{comparison.recommended_vendor}** for approval, subject to human review."
        if comparison.recommended_vendor
        else "**No automatic award recommendation.** Human procurement review is required."
    )
    issue_lines = [
        f"- **{vendor.vendor}:** {'; '.join(vendor.issues)}"
        for vendor in comparison.vendors
        if vendor.issues
    ]
    warning_lines = [f"- {warning}" for warning in comparison.warnings]
    return "\n".join(
        [
            "## Procurement comparison",
            "",
            *rows,
            "",
            "## Recommendation",
            "",
            recommendation,
            comparison.recommendation_basis,
            "",
            "## Exceptions and controls",
            "",
            *(issue_lines or ["- No extracted policy exceptions."]),
            *warning_lines,
            "- Validate tax, commercial terms, and source quotations before issuing an order.",
        ]
    )
