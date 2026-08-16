import io
import csv
import uuid

from fastapi.testclient import TestClient

from skiljo_api.main import app
from skiljo_core.db.models import TicketBatch, TicketRecord
from skiljo_core.db.session import SessionLocal

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


def _clean_ticket_tables() -> None:
    with SessionLocal() as session:
        session.query(TicketRecord).delete()
        session.query(TicketBatch).delete()
        session.commit()


def test_import_persists_ticket_batch_and_records() -> None:
    _clean_ticket_tables()
    csv_data = _make_csv_bytes([VALID_ROW])

    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200
    batch_id = uuid.UUID(response.json()["batch_id"])
    with SessionLocal() as session:
        batch = session.get(TicketBatch, batch_id)
        assert batch is not None
        assert batch.source_filename == "tickets.csv"
        assert batch.ticket_count == 1
        records = session.query(TicketRecord).filter(TicketRecord.batch_id == batch_id).all()
        assert len(records) == 1
        assert records[0].ticket_data["ground_truth_decision"] == "approve_refund"


def test_get_ticket_batch_returns_imported_tickets() -> None:
    _clean_ticket_tables()
    csv_data = _make_csv_bytes([VALID_ROW])
    imported = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    batch_id = imported.json()["batch_id"]

    response = client.get(f"/tickets/batches/{batch_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == batch_id
    assert data["ticket_count"] == 1
    assert data["tickets"][0]["ground_truth_decision"] == "approve_refund"


def test_import_persists_and_retrieves_csv_order() -> None:
    _clean_ticket_tables()
    rows = [
        {**VALID_ROW, "customer_id": "first", "refund_amount": "10.00"},
        {**VALID_ROW, "customer_id": "second", "refund_amount": "20.00"},
        {**VALID_ROW, "customer_id": "third", "refund_amount": "30.00"},
    ]
    imported = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(_make_csv_bytes(rows)), "text/csv")},
    )
    batch_id = uuid.UUID(imported.json()["batch_id"])

    with SessionLocal() as session:
        records = (
            session.query(TicketRecord)
            .filter(TicketRecord.batch_id == batch_id)
            .order_by(TicketRecord.position)
            .all()
        )
        assert [record.position for record in records] == [0, 1, 2]

    response = client.get(f"/tickets/batches/{batch_id}")

    assert response.status_code == 200
    assert [ticket["refund_amount"] for ticket in response.json()["tickets"]] == [
        10.0,
        20.0,
        30.0,
    ]


def test_get_ticket_batch_orders_records_by_position() -> None:
    _clean_ticket_tables()
    batch_id = uuid.uuid4()
    with SessionLocal() as session:
        session.add(TicketBatch(id=batch_id, source_filename="scrambled.csv", ticket_count=3))
        for position in (2, 0, 1):
            ticket_id = uuid.uuid4()
            session.add(
                TicketRecord(
                    batch_id=batch_id,
                    position=position,
                    ticket_id=ticket_id,
                    ticket_data={
                        "ticket_id": str(ticket_id),
                        "refund_amount": float((position + 1) * 10),
                    },
                )
            )
        session.commit()

    response = client.get(f"/tickets/batches/{batch_id}")

    assert response.status_code == 200
    assert [ticket["refund_amount"] for ticket in response.json()["tickets"]] == [
        10.0,
        20.0,
        30.0,
    ]


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
    assert "CSV" in response.json()["error"]["message"]


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
    details = data["error"]["details"]
    assert "errors" in details
    assert len(details["errors"]) == 1
    assert details["errors"][0]["row"] == 2


def test_import_invalid_refund_amount_not_a_number_returns_400_with_row_errors() -> None:
    bad_row = {**VALID_ROW, "refund_amount": "not_a_number"}
    csv_data = _make_csv_bytes([bad_row])
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert response.status_code == 400
    data = response.json()
    details = data["error"]["details"]
    assert "errors" in details
    assert details["errors"][0]["row"] == 2


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
    details = data["error"]["details"]
    assert "errors" in details
    assert len(details["errors"]) == 2


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
