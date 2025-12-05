import decimal
from typing import Dict
from sqlalchemy.orm import Session

from models import GroupMember, Transaction, Split

CENT = decimal.Decimal("0.01")


def _to_decimal(value: object) -> decimal.Decimal:
    return decimal.Decimal(str(value)).quantize(CENT)


def compute_group_balances(db: Session, group_id: int) -> Dict[int, decimal.Decimal]:
    members = (
        db.query(GroupMember.user_id)
        .filter(GroupMember.group_id == group_id)
        .all()
    )
    member_ids = {row.user_id for row in members}
    balances: Dict[int, decimal.Decimal] = {
        uid: decimal.Decimal("0.00") for uid in member_ids
    }

    transactions = (
        db.query(Transaction)
        .filter(Transaction.group_id == group_id)
        .all()
    )
    for txn in transactions:
        payer = txn.payer_user_id
        if payer is None:
            continue
        amount = _to_decimal(txn.amount)
        balances.setdefault(payer, decimal.Decimal("0.00"))
        balances[payer] += amount

    splits = (
        db.query(Split)
        .join(Transaction, Split.transaction_id == Transaction.id)
        .filter(Transaction.group_id == group_id)
        .all()
    )
    for split in splits:
        share = _to_decimal(split.share_amount)
        balances.setdefault(split.user_id, decimal.Decimal("0.00"))
        balances[split.user_id] -= share

    total_balance = sum(balances.values())
    if total_balance != decimal.Decimal("0.00") and abs(total_balance) <= CENT and balances:
        first_key = next(iter(balances))
        balances[first_key] = (balances[first_key] - total_balance).quantize(CENT)

    return balances


def compute_member_balance(db: Session, group_id: int, member_id: int) -> decimal.Decimal:
    balances = compute_group_balances(db, group_id)
    return balances.get(member_id, decimal.Decimal("0.00")).quantize(CENT)
