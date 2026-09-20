"""In-memory CloudDesk systems. These become MCP tools on Day 3."""

from copy import deepcopy

CUSTOMERS = [
    {
        "id": "cus_acme_001",
        "name": "ACME Inc",
        "plan": "enterprise",
        "status": "active",
        "primary_contact": "finance@acme.example",
    }
]

INVOICES = [
    {
        "id": "inv_3021",
        "customer_id": "cus_acme_001",
        "amount": 120.0,
        "currency": "USD",
        "status": "paid",
        "period": "2026-09",
    }
]

PAYMENTS = [
    {
        "id": "pay_88192",
        "customer_id": "cus_acme_001",
        "invoice_id": "inv_3021",
        "amount": 120.0,
        "currency": "USD",
        "status": "succeeded",
        "created_at": "2026-09-17T09:11:00Z",
    },
    {
        "id": "pay_88207",
        "customer_id": "cus_acme_001",
        "invoice_id": "inv_3021",
        "amount": 120.0,
        "currency": "USD",
        "status": "succeeded",
        "created_at": "2026-09-17T09:13:00Z",
    },
]

LOGS = [
    {
        "id": "log_713",
        "customer_id": "cus_acme_001",
        "service": "invoice-export-worker",
        "level": "error",
        "message": "Export job timed out after 30s while rendering 12,443 line items",
        "timestamp": "2026-09-19T07:10:05Z",
    },
    {
        "id": "log_719",
        "customer_id": "cus_acme_001",
        "service": "invoice-export-worker",
        "level": "error",
        "message": "Export job timed out after 30s while rendering 12,443 line items",
        "timestamp": "2026-09-19T07:25:41Z",
    },
]


class MockCloudDeskService:
    """Read-only adapter for Day 1. Side-effecting methods arrive after approval support."""

    def find_customer_by_name(self, name: str | None) -> dict[str, object]:
        if not name:
            return {}
        normalized = name.casefold().replace("inc.", "").replace("inc", "").strip()
        for customer in CUSTOMERS:
            candidate = (
                str(customer["name"]).casefold().replace("inc.", "").replace("inc", "").strip()
            )
            if normalized in candidate or candidate in normalized:
                return deepcopy(customer)
        return {}

    def get_recent_invoices(self, customer_id: str) -> list[dict[str, object]]:
        return deepcopy([row for row in INVOICES if row["customer_id"] == customer_id])

    def get_payment_history(self, customer_id: str) -> list[dict[str, object]]:
        return deepcopy([row for row in PAYMENTS if row["customer_id"] == customer_id])

    def search_logs(self, customer_id: str) -> list[dict[str, object]]:
        return deepcopy([row for row in LOGS if row["customer_id"] == customer_id])
