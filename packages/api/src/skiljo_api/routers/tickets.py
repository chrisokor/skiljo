import csv
import io
import json
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from skiljo_api.dependencies import verify_api_key
from skiljo_core.db.models import TicketBatch, TicketRecord
from skiljo_core.db.session import SessionLocal
from skiljo_core.schemas.ticket_schema import Ticket

router = APIRouter(prefix="/tickets", tags=["tickets"], dependencies=[Depends(verify_api_key)])

_REQUIRED_COLUMNS = {"refund_amount", "purchase_days_ago", "ground_truth_decision"}


def _parse_fraud_flags(raw: str) -> list[str]:
    """Parse fraud_flags from a JSON string (e.g. '["flag_a"]') or empty string."""
    raw = raw.strip()
    if not raw or raw in ("[]", "null", ""):
        return []
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError(f"fraud_flags must be a JSON array, got: {raw!r}")
        return [str(item) for item in parsed]
    except json.JSONDecodeError as exc:
        raise ValueError(f"fraud_flags is not valid JSON: {raw!r}") from exc


def _parse_row(row: dict, row_idx: int) -> Ticket:
    """Parse and validate a CSV row into a Ticket. Raises ValueError on bad data."""
    missing = _REQUIRED_COLUMNS - set(row.keys())
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    refund_amount_raw = row.get("refund_amount", "").strip()
    if not refund_amount_raw:
        raise ValueError("refund_amount is empty")
    try:
        refund_amount = float(refund_amount_raw)
    except ValueError:
        raise ValueError(f"refund_amount must be a number, got: {refund_amount_raw!r}")

    purchase_days_raw = row.get("purchase_days_ago", "").strip()
    if not purchase_days_raw:
        raise ValueError("purchase_days_ago is empty")
    try:
        purchase_days_ago = int(purchase_days_raw)
    except ValueError:
        raise ValueError(f"purchase_days_ago must be an integer, got: {purchase_days_raw!r}")

    ground_truth = row.get("ground_truth_decision", "").strip()
    if not ground_truth:
        raise ValueError("ground_truth_decision is empty")

    fraud_flags_raw = row.get("fraud_flags", "[]") or "[]"
    fraud_flags = _parse_fraud_flags(fraud_flags_raw)

    customer_segment = row.get("customer_segment", "").strip() or None
    refund_reason = row.get("refund_reason", "").strip() or None

    # Use customer_id as a seed for a deterministic-ish UUID if present, else random
    customer_id_raw = row.get("customer_id", "").strip()
    if customer_id_raw:
        ticket_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"row-{row_idx}-{customer_id_raw}")
    else:
        ticket_id = uuid.uuid4()

    return Ticket(
        ticket_id=ticket_id,
        refund_amount=refund_amount,
        purchase_days_ago=purchase_days_ago,
        customer_segment=customer_segment,
        fraud_flags=fraud_flags,
        refund_reason=refund_reason,
        ground_truth_decision=ground_truth,
    )


@router.post("/import")
def import_tickets(file: UploadFile = File(...)) -> dict:
    """
    Import tickets from a CSV file.

    Expected columns:
      - customer_id (optional)
      - refund_amount (required, float)
      - purchase_days_ago (required, int)
      - customer_segment (optional)
      - fraud_flags (optional, JSON array string e.g. '["flag"]')
      - refund_reason (optional)
      - ground_truth_decision (required)

    Returns:
      { batch_id, count, errors }

    Returns 400 if the file is not CSV, or if all rows fail validation.
    Partial errors (some rows invalid) are returned in the errors list with 200.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV (filename must end in .csv)",
        )

    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    tickets: list[Ticket] = []
    errors: list[dict] = []

    for row_idx, row in enumerate(reader, start=2):  # row 1 is the header
        try:
            ticket = _parse_row(row, row_idx)
            tickets.append(ticket)
        except (KeyError, ValueError, TypeError) as exc:
            errors.append({"row": row_idx, "error": str(exc), "data": dict(row)})

    if not tickets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "No valid rows found", "errors": errors},
        )

    batch_id = uuid.uuid4()
    with SessionLocal() as session:
        batch = TicketBatch(
            id=batch_id,
            source_filename=filename,
            ticket_count=len(tickets),
        )
        session.add(batch)
        for ticket in tickets:
            session.add(
                TicketRecord(
                    batch_id=batch_id,
                    ticket_id=ticket.ticket_id,
                    ticket_data=ticket.model_dump(mode="json"),
                )
            )
        session.commit()

    return {"batch_id": str(batch_id), "count": len(tickets), "errors": errors}


@router.get("/batches/{batch_id}")
def get_ticket_batch(batch_id: uuid.UUID) -> dict:
    with SessionLocal() as session:
        batch = session.get(TicketBatch, batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="ticket batch not found")
        records = session.query(TicketRecord).filter(TicketRecord.batch_id == batch_id).all()
        return {
            "id": str(batch.id),
            "source_filename": batch.source_filename,
            "ticket_count": batch.ticket_count,
            "tickets": [record.ticket_data for record in records],
        }
