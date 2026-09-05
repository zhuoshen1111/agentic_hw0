"""
EE 599 -- HW 0, Part 3: Rules Types Cannot Express, and Failure as Data
(about 15 minutes)

TWO THINGS TYPES ALONE WILL NOT DO

First, some rules are about meaning rather than shape. "Eve Hall" and "the Moon"
are both strings of text. Only one of them is a place this taqueria delivers to.
No type annotation can tell them apart, so you write a small function and attach
it to the field. Pydantic calls these validators.
类型注解 str 无法表达“这个字符串必须是某个真实配送地点”，
因此需要 validator。

Second, something has to happen after a rejection. In an ordinary program you
might raise an exception and let it crash. In an agent that is usually wrong,
because the run has not failed: the AI model made a bad suggestion, your program
refused it, and the sensible next step is to tell the model what was wrong so it
can try again.

That means the failure itself gets sent back to the model. So the failure needs
a predictable shape your code can branch on, and its text has to be safe to
show. It must not carry your file paths, stack traces, library versions, or
database errors along with it.

HOW TO RUN IT

    python part3_errors.py

The script ends by printing the safe version of a failure next to the unsafe
version, so you can see the difference.
"""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)

from part2_after import BurritoOrder
from taqueria import DELIVERY_ZONE, accepted, banner, rejected


class DeliveryOrder(BurritoOrder): #AI 希望执行的订单参数
    """A BurritoOrder that also has to get somewhere.

    This class inherits from the model you wrote in Part 2, so every rule you
    already wrote still applies here: the menu, the quantity range, strict
    types, and extra="forbid". You are extending a contract, not rewriting one.
    That is how tool schemas usually grow in a real project.

    Two new fields:
        fulfillment  "pickup" or "delivery"
        address      where to deliver, or None for a pickup order
    """

    fulfillment: Literal["pickup", "delivery"]
    address: str | None = None

    # TODO 5: Write a validator for the `address` field.
    #
    # A field validator is a classmethod that Pydantic calls with the value of
    # one field, after that field's type has been checked. It either returns a
    # value (possibly a cleaned-up one) or raises ValueError to reject it.
    #
    # The shape is always this:
    #
    #     @field_validator("address")
    #     @classmethod
    #     def some_descriptive_name(cls, value: str | None) -> str | None:
    #         ...
    #         return value
    #
    # Both decorators are required, and @field_validator must be the outer one.
    #
    # Your validator must:
    #   1. return None unchanged, because a pickup order has no address and
    #      that is perfectly legal
    #   2. remove leading and trailing whitespace with .strip()
    #      它会去掉字符串开头和结尾的空格
    #   3. raise ValueError if the lowercased address is not in DELIVERY_ZONE.
    #      Include the words "delivery zone" in the message; a later function
    #      looks for that phrase.
    #   4. otherwise return the stripped address
    #
    # Raise plain ValueError, not ValidationError. Pydantic catches your
    # ValueError and reports it in the same list as everything else it found,
    # so one bad request produces one complete report rather than a series of
    # one-problem-at-a-time failures.
    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str | None) -> str | None:
        if value is None:
            return None

        stripped = value.strip()

        if stripped.lower() not in DELIVERY_ZONE:
            raise ValueError("address is outside the delivery zone")

        return stripped  # <-- your code here (TODO 5)

    # TODO 6: Write a validator for a rule that involves two fields at once.
    #
    # A field validator only ever sees one field, so it cannot express "a
    # delivery order needs an address". That rule compares `fulfillment` and
    # `address` together, so it goes in a model validator instead.
    #
    # `mode="after"` means Pydantic runs your method once the whole object has
    # been built and every individual field has already been checked. It is an
    # ordinary method, not a classmethod, it reads fields off `self`, and it
    # must return `self` when everything is fine:
    #
    #     @model_validator(mode="after")
    #     def some_descriptive_name(self) -> "DeliveryOrder":
    #         ...
    #         return self
    #
    # Reject these two combinations by raising ValueError:
    #   - fulfillment is "delivery" but address is None
    #   - fulfillment is "pickup" but an address was given anyway
    #
    # The second one matters as much as the first. An address on a pickup order
    # means the model misunderstood the request, and a system that silently
    # ignores the extra information will deliver nothing and explain nothing.
    @model_validator(mode="after")
    def validate_fulfillment_and_address(self) -> "DeliveryOrder":
        if self.fulfillment == "delivery" and self.address is None:
            raise ValueError("a delivery order requires an address")

        if self.fulfillment == "pickup" and self.address is not None:
            raise ValueError("a pickup order must not include an address")

        return self  # <-- your code here (TODO 6)


# --- Giving failure a shape --------------------------------------------------


class ToolError(BaseModel): #程序拒绝工具调用后，准备反馈给 AI 的错误
    """What the program produces when a tool call does not happen.

    An agent loop is the cycle of: send the conversation to the model, read what
    the model wants to do, do it, append the outcome to the conversation, repeat.
    Everything appended to that conversation is eventually sent back to the
    model, including failures. So a failure has to be a value, not an exception,
    and it has to be a value with a predictable shape.

    Fields:
        code       A short, fixed identifier. Your program branches on this.
                   Using Literal means only these four values are possible, so
                   a typo in a comparison elsewhere becomes visible.
        message    The only part an AI model should ever be shown. Keep it
                   short, keep it about the request, and never build it out of
                   an exception's own text.
        fields     Which fields were rejected, so the model knows what to fix.
        retryable  Whether trying again could plausibly help. Bad arguments are
                   worth another attempt; a tool that does not exist is not.
    """

    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "invalid_arguments",
        "outside_delivery_zone",
        "unknown_tool",
        "kitchen_failure",
    ]
    message: str
    fields: list[str] = []
    retryable: bool = True


def to_tool_error(exc: ValidationError) -> ToolError:
    """Convert a ValidationError into something safe to send back to the model."""

    # TODO 7: Build and return the ToolError.
    #
    # `exc.errors()` returns a list of dictionaries, one per problem, each with
    # "loc" (a tuple saying where), "msg" (what is wrong) and "type". Build the
    # ToolError only out of "loc" and "msg". Do not use str(exc). Run this file
    # after you finish and the last section will show you why.
    #
    #   fields     The first element of each error's "loc", de-duplicated and
    #              sorted. Skip errors whose "loc" is empty; a JSON syntax error
    #              is not about any particular field.
    #
    #   code       "outside_delivery_zone" if any message contains the phrase
    #              "delivery zone", otherwise "invalid_arguments". This is a
    #              simplification: real code usually branches on the stable
    #              "type" value rather than searching English text.
    #
    #   message    One line the model can act on, for example:
    #                "2 field(s) rejected: address: ...; quantity: ..."
    #              Cut it off at 200 characters. A bound matters because this
    #              text goes into the conversation on every retry, and an
    #              unbounded error message is an unbounded bill.
    #
    #   retryable  True. A model can usually correct its own arguments.
    #
    errors = exc.errors()

    fields = sorted(
        {
            str(error["loc"][0])
            for error in errors
            if error["loc"]
        }
    )

    code = (
        "outside_delivery_zone"
        if any("delivery zone" in error["msg"] for error in errors)
        else "invalid_arguments"
    )

    details = []
    for error in errors:
        location = ".".join(str(part) for part in error["loc"]) or "<body>"
        details.append(f"{location}: {error['msg']}")

    message = (
        f"{len(fields)} field(s) rejected: {'; '.join(details)}"
    )[:200]

    return ToolError(
        code=code,
        message=message,
        fields=fields,
        retryable=True,
    )


# --- Six more replies, this time about delivery ------------------------------

DELIVERY_REPLIES: list[tuple[str, str]] = [
    (
        "pickup, all good",
        '{"item":"taco","quantity":3,"spice":"hot","fulfillment":"pickup"}',
    ),
    (
        "delivery to Leavey",
        '{"item":"bowl","quantity":1,"spice":"mild","fulfillment":"delivery",'
        '"address":"Leavey Library"}',
    ),
    (
        # Caught by TODO 5: correct type, impossible destination.
        "delivery to the Moon",
        '{"item":"burrito","quantity":1,"spice":"hot","fulfillment":"delivery",'
        '"address":"the Moon"}',
    ),
    (
        # Caught by TODO 6: every field is individually fine, the combination
        # is not.
        "delivery, no address",
        '{"item":"burrito","quantity":2,"spice":"mild","fulfillment":"delivery"}',
    ),
    (
        # Also caught by TODO 6, in the other direction.
        "pickup, but an address anyway",
        '{"item":"taco","quantity":1,"spice":"mild","fulfillment":"pickup",'
        '"address":"Olin Hall"}',
    ),
    (
        # Five problems at once. Pydantic reports all of them together, which is
        # what makes a single retry likely to succeed.
        "everything wrong at once",
        '{"item":"sushi","quantity":500,"spice":"nuclear","fulfillment":"delivery",'
        '"address":"the Moon","price_override":0}',
    ),
]


def main() -> None:
    """Run the delivery replies, then compare a safe failure with an unsafe one."""
    banner("PART 3 -- domain rules and structured failure")

    worst: ValidationError | None = None
    for label, raw in DELIVERY_REPLIES:
        try:
            order = DeliveryOrder.model_validate_json(raw)
        except ValidationError as exc:
            err = to_tool_error(exc)
            rejected(label, f"[{err.code}] {err.message}")
            worst = exc
        else:
            accepted(label, f"{order.quantity} x {order.item}, {order.fulfillment}")

    if worst is None:
        print("\n  Nothing was rejected, so TODO 5 and TODO 6 are not finished yet.")
        print("  Finish them and run this again to see the rest of the output.")
        return

    banner("What the model should see, and what it should not")
    print("  SAFE. A ToolError, built only from 'loc' and 'msg':\n")
    print(f"    {to_tool_error(worst).model_dump_json()}\n")
    print("  UNSAFE. str(exc), which Pydantic writes for a developer reading")
    print("  a log file, not for anything outside your program:\n")
    leaky = str(worst)
    for line in leaky.splitlines()[:8]:
        print(f"    {line}")
    print(f"    ... ({len(leaky)} characters in total)")
    print()
    print("  Nothing here is a security disaster on its own. But the unsafe")
    print("  version names your classes, echoes back the input values, links to")
    print("  your exact library version, and grows without limit as the number")
    print("  of problems grows. In a real system that text would be joined by")
    print("  file paths and database errors.")
    print()
    print("  The habit worth building is not 'Pydantic errors are dangerous'.")
    print("  It is: decide deliberately what crosses back to the model, every")
    print("  time, instead of forwarding whatever exception you happened to get.")


if __name__ == "__main__":
    main()
