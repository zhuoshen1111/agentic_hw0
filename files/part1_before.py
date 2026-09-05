"""
EE 599 -- HW 0, Part 1: Checking Data By Hand  (about 10 minutes)

THE SITUATION

Taco Bot 3000 is an AI model connected to the campus taqueria's ordering
system. A customer types a request in plain English, the model turns it into
JSON, and a program reads that JSON and places the order.

The model is not malicious and it has not been hacked. It is simply a program
that produces plausible-looking text, and sometimes plausible-looking text is
wrong. Your program is the only thing standing between the model's reply and a
credit card charge.

WHAT THIS FILE DOES

`validate_order_by_hand` reads one reply from the model and decides whether it
is safe to send to the kitchen. It is written the way careful programmers wrote
this kind of code before validation libraries existed: one `if` statement per
rule, checked in order, using only the standard library.

HOW TO RUN IT

    python part1_before.py

WHAT TO DO

1. Run it first, before you change anything, and look at the output. Some
   replies are marked ESCAPED. Those are bad orders that got through and were
   cooked and charged.
2. Read `validate_order_by_hand` from top to bottom. It is about thirty lines
   long, and most of it is checking shapes rather than expressing rules.
3. Then do TODO 1 and TODO 2 below.
4. Run it again. The ESCAPED lines should be gone.

Answer questions Q1 and Q2 in ANSWERS.md while this part is still fresh.
"""

from __future__ import annotations

import json

from taqueria import (
    MENU,
    count_code_lines,
    RAW_MODEL_REPLIES,
    SPICE_LEVELS,
    accepted,
    banner,
    escaped,
    rejected,
    reset_ledger,
    send_to_kitchen,
    total_charged,
)

# The four fields an order is supposed to have.
REQUIRED_KEYS = ("item", "quantity", "spice", "notes")


def validate_order_by_hand(raw: str) -> tuple[dict | None, str | None]:
    """Decide whether one model reply is an acceptable order.

    Arguments:
        raw: the exact text the model sent back. It is a string, not a dict.
             Nothing has parsed it yet.

    Returns a pair of values, and exactly one of them is always None:
        (order, None)   the reply is acceptable; `order` is a clean dict
        (None, reason)  the reply was refused; `reason` says why, in English

    Returning a reason instead of raising an exception is a deliberate choice.
    Later in this assignment the reason gets sent back to the AI model so it can
    correct itself, so it has to be an ordinary value your code can pass around.
    """

    # Step 1. Is the text even JSON?
    # The model might have written an explanation, an apology, or a code fence
    # around the JSON. Any of those makes this fail.
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"not valid JSON: {exc.msg}"

    # Step 2. Is it a JSON object (which becomes a Python dict)?
    # Valid JSON can also be a list, a number, or the word null. We need a dict.
    if not isinstance(data, dict):
        return None, f"expected an object, got {type(data).__name__}"

    # Step 3. Are all four fields present?
    # Reaching for a missing key later would raise KeyError somewhere much less
    # convenient, so check for all of them here, at the entrance.
    for key in REQUIRED_KEYS:
        if key not in data:
            return None, f"missing required field {key!r}"

    # Step 4. Is `item` a string, and is it something we actually sell?
    # Two separate questions. The first is about type, the second is about our
    # business. Notice that we have to write both checks by hand, and that the
    # code does not make the difference between them obvious.
    item = data["item"]
    if not isinstance(item, str):
        return None, "item must be a string"
    if item not in MENU:
        return None, f"{item!r} is not on the menu"

    # Step 5. Is `quantity` a whole number?
    # We are being generous here: int("3") succeeds, so the string "3" is
    # accepted and silently turned into the number 3. That seemed friendly when
    # this code was written. Part 2 asks you whether it was a good idea.
    try:
        quantity = int(data["quantity"])
    except (TypeError, ValueError):
        return None, "quantity must be a whole number"

    # Step 6. Is `spice` one of the three levels the kitchen can make?
    if not isinstance(spice := data["spice"], str) or spice not in SPICE_LEVELS:
        return None, f"spice must be one of {', '.join(SPICE_LEVELS)}"

    # Step 7. Is `notes` a string, and is it a reasonable length?
    # The length limit exists because this text eventually gets printed on a
    # ticket. Unbounded text from a model is a bad idea in almost every system.
    notes = data["notes"]
    if not isinstance(notes, str):
        return None, "notes must be a string"
    if len(notes) > 200:
        return None, "notes is too long"

    # TODO 1: Add a range check on `quantity`.
    #
    # The taqueria will not cook fewer than 1 or more than 20 of anything.
    # Right now nothing enforces that, which is why two replies below are
    # currently marked ESCAPED.
    #
    if quantity < 1:
        return None, "quantity must be at least 1"
    if quantity > 20:
        return None, "quantity must be at most 20"
    # Add checks that return (None, reason) when `quantity` is below 1 or above
    # 20. Write reasons that state the limit, so that a person -- or an AI model
    # trying again -- can tell what went wrong.

    # TODO 2: Reject fields we never asked for.
    #
    # One of the replies contains a "price_override" field. Nothing in this
    # function reads it, so today it is harmless. But if any code anywhere in
    # the system later looked for that field, the order would cost nothing --
    # and this function would never have warned anybody.
    #
    # A field you did not ask for is a signal that something is wrong, not a
    # harmless extra. Compare the keys in `data` against REQUIRED_KEYS. If there
    # are any others, return (None, reason) and name them in the reason.
    extra_keys = set(data) - set(REQUIRED_KEYS)
    if extra_keys:
        return None, f"unexpected fields: {', '.join(sorted(extra_keys))}"
    # Hint: `set(data)` gives you the keys of a dict as a set.

    # Every check passed. Build a clean dict from the values we verified, rather
    # than passing `data` along, so that nothing unchecked travels any further.
    return {"item": item, "quantity": quantity, "spice": spice, "notes": notes}, None


def is_actually_dangerous(order: dict) -> str | None:
    """Say whether an accepted order was actually a bad one.

    This function exists only so the demo below can colour its output. It is a
    stand-in for a person looking at the receipt afterward and noticing the
    problem. A rule you never wrote cannot catch anything, which is exactly the
    point Part 1 is making.
    """
    if order["quantity"] < 1 or order["quantity"] > 20:
        return f"quantity {order['quantity']} is outside 1-20"
    return None


def main() -> None:
    """Run all eight model replies through the hand-written checks."""
    reset_ledger()
    banner("PART 1 -- hand-written validation, one lunch rush")

    survived = 0
    for label, raw in RAW_MODEL_REPLIES:
        order, reason = validate_order_by_hand(raw)

        if order is None:
            # Refused before the kitchen ever saw it. Nothing was charged.
            rejected(label, reason or "")
            continue

        # Accepted, so the tool runs and the card is charged. Whether that was
        # the right call is a separate question, which is what we check next.
        danger = is_actually_dangerous(order)
        receipt = send_to_kitchen(**order)
        if danger:
            survived += 1
            escaped(label, receipt)
        else:
            accepted(label, receipt)

    print()
    print(f"  lines of validation code   : {count_code_lines(validate_order_by_hand)}")
    print(f"  bad orders that got through: {survived}")
    print(f"  total charged to the card  : ${total_charged():,.2f}")
    print()
    print("  Two things to notice before you move on:")
    print("   1. Most of those lines check shapes, not business rules.")
    print("   2. Before you write TODO 2, one of the ACCEPTED lines above is")
    print("      also wrong and nothing flagged it. Finding it is Q1 in")
    print("      ANSWERS.md, so look now.")
    print()
    print("  Now open part2_after.py.")


if __name__ == "__main__":
    main()
