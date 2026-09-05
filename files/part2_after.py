"""
EE 599 -- HW 0, Part 2: The Same Job, Using Pydantic  (about 15 minutes)

WHAT PYDANTIC IS

Pydantic is a Python library for describing what data is allowed to look like.
You write a class, list the fields and their types, and Pydantic generates the
checking code for you. When data arrives, you hand it to the class and Pydantic
either gives you back an object you can trust, or raises an error explaining
exactly which field was wrong and why.

You are about to replace the thirty-odd lines you read in Part 1 with about a
dozen, and the new version will catch more problems, not fewer.

THREE SEPARATE IDEAS

Students often collapse all of these into the single word "validation". They are
different, they are configured differently, and each one catches things the
other two do not:

    strict=True         Controls conversion. Is the text "3" allowed to become
                        the number 3, or is that a mistake worth reporting? 控制类型转换

    Field(ge=1, le=20)  Controls the range of allowed values. 0 is a perfectly
                        good integer, but it is not a quantity we will cook.  控制数值范围

    extra="forbid"      Controls which field names are allowed at all. Without
                        it, Pydantic ignores fields you did not ask for.  控制字段名称

HOW TO RUN IT

    python part2_after.py

The eight replies are the same eight from Part 1, so you can compare directly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from taqueria import (
    RAW_MODEL_REPLIES,
    accepted,
    banner,
    count_code_lines,
    rejected,
    reset_ledger,
    send_to_kitchen,
    total_charged,
)


# TODO 3: Write the contract.
#
# A Pydantic model is a class that inherits from BaseModel. Each line in the
# class body names a field and gives its type. Read the finished class as a
# sentence in English: "an order has an item, which is one of three things; a
# quantity, which is a whole number from 1 through 20; and so on."
#
# `BurritoOrder` must accept exactly the orders the taqueria can actually cook:
#
#   item      one of "burrito", "taco", "bowl"
#             Use typing.Literal, which restricts a field to a fixed set of
#             values:  item: Literal["burrito", "taco", "bowl"]
#
#   quantity  a whole number from 1 through 20
#             Use Field with the `ge` (greater than or equal) and `le` (less
#             than or equal) options:  quantity: int = Field(ge=1, le=20)
#
#   spice     one of "mild", "medium", "hot"        -- Literal again
#
#   notes     a string of at most 200 characters, which may be left out
#             entirely. A field with a default value is optional:
#             notes: str = Field(default="", max_length=200)
#
# Then configure the model itself by assigning to `model_config` inside the
# class body:
#
#   model_config = ConfigDict(extra="forbid", strict=True)
#
#   extra="forbid" makes an unexpected field an error. Pydantic ignores extra
#   fields by default, so you have to ask for this. It is the fix for the
#   "price_override" reply you found in Part 1.
#
#   strict=True stops Pydantic from converting values between types, so the
#   text "3" will no longer be quietly accepted as the number 3.
class BurritoOrder(BaseModel):
    ...  # <-- your code here (TODO 3)
    item: Literal["burrito", "taco", "bowl"]
    quantity: int = Field(ge=1, le=20)
    spice: Literal["mild", "medium", "hot"]
    notes: str = Field(default="", max_length=200)
    model_config = ConfigDict(extra="forbid", strict=True)


def parse_order(raw: str) -> tuple[BurritoOrder | None, str | None]:
    """Decide whether one model reply is an acceptable order.

    This has the same arguments and the same return type as
    `validate_order_by_hand` in Part 1, so you can compare the two honestly.

    Arguments:
        raw: the exact text the model sent back, not a dict.

    Returns (order, None) if the reply is acceptable, otherwise (None, reason).
    """
    # TODO 4: Validate `raw` and return the result.
    #
    # Pydantic gives you two different methods, and mixing them up is the most
    # common Pydantic mistake in this course:
    #
    #   BurritoOrder.model_validate(obj)        obj is a Python object, usually
    #                                           a dict you already parsed
    #   BurritoOrder.model_validate_json(text)  text is raw JSON, as a string
    #                                           or bytes, not yet parsed
    #
    # `raw` here is unparsed JSON text straight off the network, so use the
    # second one. If you use the first one by mistake you will get a confusing
    # error saying "Input should be a valid dictionary", and you will be tempted
    # to blame the model rather than the call.
    #
    # When the data does not fit, Pydantic raises pydantic.ValidationError.
    # Catch it and return the reason as a string instead of letting the
    # exception travel further up. `first_error` below turns a ValidationError
    # into one short line for you.r
    # #raise NotImplementedError("TODO 4 -- see the comment above")
    try:
        order = BurritoOrder.model_validate_json(raw)
        return order, None
    except ValidationError as exc:
        return None, first_error(exc)


def first_error(exc: ValidationError) -> str:
    """Describe the first thing Pydantic objected to, in one short line.

    The important part is not this function, it is `exc.errors()`. A
    ValidationError is not just a block of text: `errors()` returns a list of
    dictionaries, one per problem found, each with

        "loc"   where the problem is, as a tuple, for example ("quantity",)
        "msg"   what is wrong, in English
        "type"  a stable machine-readable name for the kind of problem

    That means a failure is data your program can inspect and make decisions
    about, not just something to print. Part 3 depends on this.
    """
    err = exc.errors()[0]
    where = ".".join(str(part) for part in err["loc"]) or "<body>"
    return f"{where}: {err['msg']}"


def main() -> None:
    """Run the same eight replies from Part 1 through the Pydantic model."""
    reset_ledger()
    banner("PART 2 -- the same lunch rush, validated by Pydantic")

    for label, raw in RAW_MODEL_REPLIES:
        order, reason = parse_order(raw)
        if order is None:
            rejected(label, reason or "")
        else:
            # `model_dump()` converts the validated object back into a plain
            # dict, which is what `send_to_kitchen` expects.
            accepted(label, send_to_kitchen(**order.model_dump()))

    print()
    print(f"  lines of validation code : {count_code_lines(BurritoOrder, parse_order)}")
    print(f"  total charged to the card: ${total_charged():,.2f}")
    print()
    print("  Compare those two numbers with Part 1. Fewer lines, and it caught")
    print("  more, including two problems Part 1 never noticed.")

    banner("The same class is also a schema")
    schema = BurritoOrder.model_json_schema()
    print("  BurritoOrder.model_json_schema() produces:")
    print(f"    required fields     : {schema.get('required')}")
    print(f"    quantity            : {schema['properties']['quantity']}")
    print(f"    additionalProperties: {schema.get('additionalProperties')}")
    print()
    print("  A JSON Schema is a standard, language-independent description of")
    print("  what a piece of JSON is allowed to contain. You wrote your rules")
    print("  once, as a Python class, and got two things from it: code that")
    print("  checks data at runtime, and a description you can hand to another")
    print("  system. Part 5 hands this exact schema to an AI model and asks it")
    print("  to reply in that shape.")
    print()
    print("  That combination is most of the reason agent frameworks are built")
    print("  on Pydantic. The OpenAI Agents SDK, LangGraph, and MCP all describe")
    print("  their tools this way.")


if __name__ == "__main__":
    main()
