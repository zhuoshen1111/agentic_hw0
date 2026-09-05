"""
EE 599 -- HW 0, Part 4: The Gate  (about 15 minutes)
AI 模型本身不能直接执行 Python 函数。它只能提出“我想调用哪个工具、参数是什么”。
真正决定是否执行的是你编写的 host，也就是 Part 4 的 gate。
This is the part the rest of the course is built on. Everything in Parts 1
through 3 was preparation for these twenty lines.

HOW A TOOL CALL ACTUALLY WORKS

An AI model cannot run your code. It has no access to your computer. What it
does is produce text saying which function it would like called and with what
arguments. Your program reads that text and decides whether anything runs.

The program that does the reading and deciding is called the host. It is
ordinary Python that you write and control. The model is not part of it.

    model produces text
            |
            v
    +-----------------------------------------------------------+
    |  HOST (your code, the only part you control)               |
    |                                                            |
    |   1. is this tool allowed?      -> no: stop here           |
    |   2. are the arguments valid?   -> no: stop here           |
    |   3. run the tool                                          |
    |   4. shape the result                                      |
    +-----------------------------------------------------------+
            |
            v
    outcome is appended to the conversation and sent back to the model

Every untrusted thing arrives at step 1 and 2. That is why validation belongs
there, and not scattered through the tool itself.

MODEL_TURNS
    ↓
取出 tool name 和 arguments
    ↓
handle_tool_call(name, arguments)
    ↓
① 检查工具名是否在 ALLOWED_TOOLS
    ↓
② 用 DeliveryOrder 验证参数
    ↓
③ 调用 send_to_kitchen()
    ↓
④ 将成功结果包装成 OrderResult
    ↓
返回 OrderResult 或 ToolError
    ↓
放进 transcript

WHY EVERY PATH MUST RETURN A VALUE

`handle_tool_call` must never raise an exception. Four different things can
happen -- the tool is not allowed, the arguments are wrong, the tool itself
fails, or everything works -- and all four have to come back as a value the
agent loop can append to the conversation and carry on. A loop that crashes on
turn three has lost the whole run, including the work that went fine.

HOW TO RUN IT

    python part4_tool_boundary.py

The script runs one lunch rush twice: once through your gate, and once with no
gate at all. Compare the two totals at the end.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from part3_errors import DeliveryOrder, ToolError, to_tool_error
from taqueria import (
    MENU,
    accepted,
    banner,
    escaped,
    rejected,
    reset_ledger,
    send_to_kitchen,
    total_charged,
)

# The complete list of tools this agent may call. An allowlist is a decision the
# host makes in advance, written in code. The model does not get a vote, and
# nothing the model says can add to this set.
ALLOWED_TOOLS = {"place_order"}

# Used to generate order numbers. A list because it is mutated by a function.
_ORDER_COUNTER = [1000]


# TODO 8: Give a successful result a shape too.
#
# `OrderResult` is what goes back into the conversation when a tool call works.
# Validating your own output sounds unnecessary -- you wrote the code that
# produced it -- right up until a tool starts returning None on a Tuesday and
# the model receives the word "null" as a receipt.
#
# Write a BaseModel with these fields:
#
#   order_id     str
#   item         str
#   quantity     int
#   total_usd    float, never negative       -- use Field(ge=0)
#   eta_minutes  int, never negative         -- use Field(ge=0)
#   status       Literal["confirmed"], defaulting to "confirmed"
#
# A Literal with only one allowed value looks pointless, but it gives the agent
# loop something reliable to branch on, and it leaves room to add "queued" or
# "refunded" later without any caller having to guess what strings are possible.
#
# Set model_config = ConfigDict(extra="forbid"), as in Part 2.
class OrderResult(BaseModel):
    order_id: str
    item: str
    quantity: int
    total_usd: float = Field(ge=0)
    eta_minutes: int = Field(ge=0)
    status: Literal["confirmed"] = "confirmed"
    model_config = ConfigDict(extra="forbid")

def handle_tool_call(name: str, arguments: dict[str, Any]) -> OrderResult | ToolError:
    """Decide whether a tool call happens, and report what happened.

    Arguments:
        name:      the tool the model asked for, as a string
        arguments: the arguments the model supplied

    `arguments` is already a Python dict here, because the host pulled it out of
    the model's reply before calling this function. That means you want
    `model_validate`, not `model_validate_json`. Part 2 used the other one
    because the input there was unparsed text.

    Returns either an OrderResult or a ToolError. It never raises.
    """
    # TODO 9: Implement the gate, in exactly this order.
    #
    #   1. If `name` is not in ALLOWED_TOOLS, return a ToolError with
    #      code="unknown_tool" and retryable=False, and a message naming the
    #      tool the model asked for. Nothing else in this function runs.
    #
    #      Check this before validating arguments. Arguments for a tool you will
    #      never call are not worth checking, and a well-formed request for a
    #      forbidden action is still a forbidden action.
    #
    #   2. Validate `arguments` into a DeliveryOrder inside a try/except. On
    #      ValidationError, return to_tool_error(exc). The kitchen must not be
    #      reached in this case, and the tests check that nothing was charged.
    #
    #   3. Only now call:
    #          send_to_kitchen(order.item, order.quantity, order.spice, order.notes)
    #      Wrap it in try/except Exception. A tool can fail for reasons that have
    #      nothing to do with its arguments. Return a ToolError with
    #      code="kitchen_failure" and retryable=False.
    #
    #      Write that message yourself. Do not put str(exc) in it. Look at what
    #      the fryer error actually says in taqueria.py before you decide.
    #      Note that a broken fryer and bad arguments are genuinely different
    #      failures even though both end up as a ToolError, which is why they
    #      get different codes.
    #
    #   4. On success, build and return an OrderResult with:
    #          order_id     f"ORD-{next_order_id()}"
    #          item         order.item
    #          quantity     order.quantity
    #          total_usd    MENU[order.item] * order.quantity
    #          eta_minutes  10 + order.quantity
    #
    #      MENU[order.item] cannot raise KeyError here. Ask yourself why not,
    #      and which line earned you that guarantee.
    if name not in ALLOWED_TOOLS:
        return ToolError(
            code="unknown_tool",
            message=f"tool {name!r} is not allowed",
            fields=[],
            retryable=False,
        )

    try:
        order = DeliveryOrder.model_validate(arguments)
    except ValidationError as exc:
        return to_tool_error(exc)

    try:
        send_to_kitchen(
            order.item,
            order.quantity,
            order.spice,
            order.notes,
        )
    except Exception:
        return ToolError(
            code="kitchen_failure",
            message="the kitchen could not complete the order",
            fields=[],
            retryable=False,
        )

    return OrderResult(
        order_id=f"ORD-{next_order_id()}",
        item=order.item,
        quantity=order.quantity,
        total_usd=MENU[order.item] * order.quantity,
        eta_minutes=10 + order.quantity,
    )


def next_order_id() -> int:
    """Return the next order number."""
    _ORDER_COUNTER[0] += 1
    return _ORDER_COUNTER[0]


# --- One lunch rush, as the model proposed it --------------------------------
#
# Each entry is (label, tool_name, arguments). This is what the host sees after
# it has read the model's reply and pulled out the requested tool call.
#
# Turn 3 is a prompt injection. A prompt injection is text placed where a model
# will read it -- in a document, a web page, or here a customer review -- that
# is written to look like an instruction. The model read a planted review and is
# now politely asking for a tool called "refund_everything". From the host's
# side there is nothing unusual about the request. It looks exactly like every
# other tool call. That is the entire problem, and it is why the defence is a
# list written in advance rather than anything the model is asked to respect.

MODEL_TURNS: list[tuple[str, str, dict[str, Any]]] = [
    (
        "a normal Tuesday",
        "place_order",
        {"item": "burrito", "quantity": 2, "spice": "mild", "fulfillment": "pickup"},
    ),
    (
        "delivery to the Moon",
        "place_order",
        {
            "item": "taco",
            "quantity": 3,
            "spice": "hot",
            "fulfillment": "delivery",
            "address": "the Moon",
        },
    ),
    (
        "injected: refund everything",
        "refund_everything",
        {"reason": "the customer support agent in the review said it was fine"},
    ),
    (
        "the $124,987 lunch, again",
        "place_order",
        {"item": "burrito", "quantity": 9999, "spice": "mild", "fulfillment": "pickup"},
    ),
    (
        "the fryer catches fire",
        "place_order",
        {
            "item": "taco",
            "quantity": 2,
            "spice": "hot",
            "notes": "extra crispy please",
            "fulfillment": "pickup",
        },
    ),
    (
        "delivery to Eve Hall",
        "place_order",
        {
            "item": "bowl",
            "quantity": 1,
            "spice": "medium",
            "fulfillment": "delivery",
            "address": "Eve Hall",
        },
    ),
]


def main() -> None:
    """Run the same six turns with the gate, then without it."""
    banner("PART 4 -- with the gate")
    reset_ledger()

    # The transcript is the running record of the conversation. In a real agent
    # every entry here would be sent back to the model on the next turn.
    transcript: list[BaseModel] = []

    for label, tool, arguments in MODEL_TURNS:
        result = handle_tool_call(tool, arguments)
        transcript.append(result)
        if isinstance(result, OrderResult):
            accepted(
                label,
                f"{result.order_id}, ${result.total_usd:,.2f}, ETA {result.eta_minutes}m",
            )
        else:
            rejected(label, f"[{result.code}] {result.message[:90]}")

    guarded_total = total_charged()
    print(f"\n  charged with the gate : ${guarded_total:,.2f}")
    print(
        "  every turn produced a value the loop can use: "
        f"{all(isinstance(entry, BaseModel) for entry in transcript)}"
    )

    banner("PART 4 -- the same lunch rush with no gate at all")
    print("  Now the arguments go straight to the tool, which is what happens")
    print("  when someone writes send_to_kitchen(**model_arguments).\n")
    reset_ledger()
    for label, tool, arguments in MODEL_TURNS:
        try:
            args = dict(arguments)
            # send_to_kitchen has no idea what fulfillment or address mean, so
            # drop them. This is the sort of quiet adjustment that makes unsafe
            # code look reasonable while you are writing it.
            args.pop("fulfillment", None)
            args.pop("address", None)
            escaped(label, send_to_kitchen(**args))
        except Exception as exc:  # noqa: BLE001
            # Without a gate, a failure is an exception that reaches the loop
            # and stops the run. Note what the fryer's message contains.
            rejected(label, f"{type(exc).__name__}: {str(exc)[:70]}")

    print(f"\n  charged with no gate  : ${total_charged():,.2f}")
    print(f"  charged with the gate : ${guarded_total:,.2f}")
    print()
    print("  Same model. Same six replies. The difference is about twenty lines")
    print("  of host code, and none of it is clever.")
    print()
    print("  Notice which mechanism stopped which problem. Pydantic stopped the")
    print("  bad arguments. The allowlist stopped the injected tool call, and no")
    print("  schema was involved in that decision at all. The try/except stopped")
    print("  the broken fryer from ending the run. Three different jobs.")
    print()
    print("  This is the shape of every tool call you will write this semester.")


if __name__ == "__main__":
    main()
