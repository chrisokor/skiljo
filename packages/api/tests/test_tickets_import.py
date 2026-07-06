import io
import csv

from fastapi.testclient import TestClient

from skiljo_api.main import app

client = TestClient(app)


def _make_csv_bytes(rows: list[dict]) -> bytes:
    """Helper to create CSV bytes from a list of dicts."""
    if not rows:
        return b""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


VALID_ROW = {
    "customer_id": "cust_001",
    "refund_amount": "150.00",
    "purchase_days_ago": "10",
    "customer_segment": "standard",
    "fraud_flags": "[]",
    "refund_reason": "defective",
    "ground_truth_decision": "approve_refund",
}


def test_import_valid_single_row_returns_200_with_batch_id() -> None:
    csv_data = _make_csv_bytes([VALID_ROW])
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert "batch_id" in data
    assert data["errors"] == []


def test_import_multiple_valid_rows_returns_correct_count() -> None:
    rows = [
        {**VALID_ROW, "customer_id": f"cust_{i}", "refund_amount": str(50.0 + i)}
        for i in range(5)
    ]
    csv_data = _make_csv_bytes(rows)
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 5
    assert data["errors"] == []


def test_import_non_csv_extension_returns_400() -> None:
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.json", io.BytesIO(b"{}"), "application/json")},
    )
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_import_missing_required_column_refund_amount_returns_400_with_row_errors() -> None:
    bad_row = {
        "customer_id": "cust_1",
        # refund_amount missing
        "purchase_days_ago": "5",
        "customer_segment": "standard",
        "fraud_flags": "[]",
        "refund_reason": "late",
        "ground_truth_decision": "deny_refund",
    }
    csv_data = _make_csv_bytes([bad_row])
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert response.status_code == 400
    data = response.json()
    detail = data["detail"]
    assert "errors" in detail
    assert len(detail["errors"]) == 1
    assert detail["errors"][0]["row"] == 2


def test_import_invalid_refund_amount_not_a_number_returns_400_with_row_errors() -> None:
    bad_row = {**VALID_ROW, "refund_amount": "not_a_number"}
    csv_data = _make_csv_bytes([bad_row])
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert response.status_code == 400
    data = response.json()
    detail = data["detail"]
    assert "errors" in detail
    assert detail["errors"][0]["row"] == 2


def test_import_partial_errors_returns_count_of_valid_rows() -> None:
    """Rows with errors are skipped; valid rows are counted and returned."""
    rows = [
        VALID_ROW,
        {**VALID_ROW, "refund_amount": "bad"},  # row 3 — invalid
        {**VALID_ROW, "customer_id": "cust_3"},  # row 4 — valid
    ]
    csv_data = _make_csv_bytes(rows)
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 3


def test_import_all_rows_invalid_returns_400() -> None:
    rows = [
        {**VALID_ROW, "refund_amount": "bad"},
        {**VALID_ROW, "purchase_days_ago": "also_bad"},
    ]
    csv_data = _make_csv_bytes(rows)
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert response.status_code == 400
    data = response.json()
    detail = data["detail"]
    assert "errors" in detail
    assert len(detail["errors"]) == 2


def test_import_fraud_flags_parsed_as_json_list() -> None:
    row = {**VALID_ROW, "fraud_flags": '["flag_a", "flag_b"]'}
    csv_data = _make_csv_bytes([row])
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_import_missing_ground_truth_decision_returns_400() -> None:
    bad_row = {
        "customer_id": "cust_1",
        "refund_amount": "100.00",
        "purchase_days_ago": "5",
        "customer_segment": "standard",
        "fraud_flags": "[]",
        "refund_reason": "late",
        # ground_truth_decision missing
    }
    csv_data = _make_csv_bytes([bad_row])
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert response.status_code == 400


def test_import_batch_id_is_unique_per_request() -> None:
    csv_data = _make_csv_bytes([VALID_ROW])
    r1 = client.post("/tickets/import", files={"file": ("t.csv", io.BytesIO(csv_data), "text/csv")})
    r2 = client.post("/tickets/import", files={"file": ("t.csv", io.BytesIO(csv_data), "text/csv")})
    assert r1.json()["batch_id"] != r2.json()["batch_id"]
