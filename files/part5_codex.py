"""
EE 599 -- HW 0, Part 5: A Real Model on the Other End  (bonus, about 10 minutes)

Every reply so far was written by us. Now the replies come from an actual AI
model, and your Pydantic class does two jobs at once.

    BurritoOrder.model_json_schema()   describes the shape you want, and gets
                                       sent to the model to constrain its reply

    BurritoOrder.model_validate_json   checks what actually came back

Both halves matter. The schema makes a well-formed reply likely. Validation is
what keeps your program correct on the occasions when the reply is not.

WHAT `codex exec` IS

Codex is a command-line program that sends a prompt to an AI model and prints
the answer. `codex exec` runs it once, without an interactive session, which
makes it easy to call from Python with `subprocess`. The `--output-schema`
option takes a file containing a JSON Schema and constrains the model's final
answer to that shape.

We use Codex here because it is already part of the course toolchain. The same
idea appears under different names elsewhere: "structured output" in the OpenAI
API, `output_type` in the OpenAI Agents SDK, and tool input schemas in MCP. All
of them are the same move -- send a schema, get back JSON, then validate it.

HOW TO RUN IT

    python part5_codex.py           offline, with canned replies.
                                    No network, no cost, and the results never
                                    change. The tests use this mode.

    python part5_codex.py --live    real calls through the codex CLI.
                                    Slower, costs a small amount, and the
                                    replies will differ from the ones below.

Run --live at least once and paste the output into Q6 in ANSWERS.md.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from pydantic import ValidationError

from part2_after import BurritoOrder
from part3_errors import ToolError, to_tool_error
from taqueria import DIM, OFF, accepted, banner, rejected

SYSTEM_RULES = (
    "You convert a customer's request into a single taqueria order. "
    "Reply with the order data only. Do not invent items that are not allowed "
    "by the schema."
)


# --- Talking to the model ----------------------------------------------------


def strict_output_schema() -> dict:
    """Return BurritoOrder's JSON Schema, adjusted for a structured-output API.

    This function is a small lesson on its own, so read it rather than skipping
    past it.

    Pydantic leaves a field out of the schema's "required" list when the field
    has a default value, because Pydantic knows how to fill it in if it is
    missing. OpenAI's strict structured-output mode refuses a schema like that:
    it requires every property to be listed in "required". So `notes`, which is
    optional in your Python class, has to be listed as required in the schema
    you send.

    Same schema, two consumers, one disagreement. The lesson is that the schema
    you show to a model is not always identical to the schema you validate with.
    Agent frameworks handle this adjustment for you and you never see it. Here
    you can see the seam.
    """
    schema = BurritoOrder.model_json_schema()
    schema["required"] = list(schema["properties"])
    return schema


def ask_codex_live(request: str, previous_error: str | None = None) -> str:
    """Send one request to the real model and return its raw JSON reply.

    Arguments:
        request:        what the customer said, in plain English
        previous_error: if this is a second attempt, the reason the first reply
                        was rejected. Including it lets the model correct
                        itself instead of guessing again.
    """
    # A temporary directory holds the two files codex needs: the schema we send
    # in, and the file it writes its answer to. Both are deleted afterward.
    with tempfile.TemporaryDirectory() as tmp:
        schema_path = Path(tmp) / "schema.json"
        out_path = Path(tmp) / "reply.json"
        schema_path.write_text(json.dumps(strict_output_schema()))

        prompt = f"{SYSTEM_RULES}\n\nCustomer request: {request}"
        if previous_error:
            prompt += (
                f"\n\nYour previous reply was rejected by the order system: "
                f"{previous_error}\nProduce a corrected order."
            )

        completed = subprocess.run(
            [
                "codex.cmd", "exec",
                # Do not require the current folder to be a git repository.
                "--skip-git-repo-check",
                # Do not save a session file for this run.
                "--ephemeral",
                # The model may not modify anything on this machine.
                "-s", "read-only",
                # Constrain the reply to our Pydantic-derived schema.
                "--output-schema", str(schema_path),
                # Write the final answer here instead of parsing it from stdout.
                "-o", str(out_path),
                prompt,
            ],
            capture_output=True,
            text=True,
            # Without this, codex waits for input that will never arrive.
            stdin=subprocess.DEVNULL,
            timeout=300,
        )
        if completed.returncode != 0 or not out_path.exists():
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-6:]
            raise RuntimeError("codex exec failed:\n  " + "\n  ".join(tail))
        return out_path.read_text().strip()


# Canned replies for the offline mode, so that this part works with no network,
# no cost, and the same result every time. Each request maps to a list: the
# first reply, and the reply the model would give after being told what was
# wrong. Two of these first replies are the mistakes real models make most
# often -- a value outside the allowed range, and a number written as text.
CANNED: dict[str, list[str]] = {
    "3 hot tacos please": [
        '{"item":"taco","quantity":3,"spice":"hot","notes":""}',
    ],
    "gimme like a hundred burritos for the club, mild": [
        '{"item":"burrito","quantity":100,"spice":"mild","notes":"for the club"}',
        '{"item":"burrito","quantity":20,"spice":"mild","notes":"for the club (max 20)"}',
    ],
    "two medium bowls, no beans": [
        '{"item":"bowl","quantity":"2","spice":"medium","notes":"no beans"}',
        '{"item":"bowl","quantity":2,"spice":"medium","notes":"no beans"}',
    ],
}


def ask_codex_offline(request: str, previous_error: str | None = None) -> str:
    """Return a canned reply. Same arguments as `ask_codex_live`."""
    replies = CANNED[request]
    return replies[1] if previous_error and len(replies) > 1 else replies[0]


# --- Ask, validate, and give the model one chance to fix it ------------------


def structured_request(
    request: str, ask
) -> tuple[BurritoOrder | None, ToolError | None, int]:
    """Turn a plain-English request into a validated order.

    Arguments:
        request: what the customer said
        ask:     the function used to reach the model. Either `ask_codex_live`
                 or `ask_codex_offline`. Passing it in as an argument is what
                 lets the tests run this loop without any network access.

    Returns (order, error, attempts). Exactly one of order and error is None.
    """
    # TODO 10: Implement the ask-validate-repair loop.
    #
    #   1. raw = ask(request)
    #
    #   2. Validate `raw` with BurritoOrder.model_validate_json inside a
    #      try/except ValidationError. On success, return (order, None, 1).
    #
    #   3. On failure, build err = to_tool_error(exc) and ask a second time:
    #          raw = ask(request, err.message)
    #      Passing the message back is the whole point. The model cannot see
    #      your schema or your exception; the only thing it knows about the
    #      rejection is what you choose to tell it. This is why Part 3 insisted
    #      that message be short, specific and safe -- it was always going to be
    #      sent to a model.
    #
    #   4. Validate the second reply. On success return (order, None, 2). If it
    #      fails again, return (None, to_tool_error(exc), 2).
    #
    # Stop after the second attempt. Do not loop until it works. Every attempt
    # costs money and time, and a model that is wrong twice in the same way is
    # usually not one attempt away from being right. Real agents set a retry
    # limit for exactly this reason.
    raw = ask(request)

    try:
        order = BurritoOrder.model_validate_json(raw)
        return order, None, 1
    except ValidationError as exc:
        err = to_tool_error(exc)

    raw = ask(request, err.message)

    try:
        order = BurritoOrder.model_validate_json(raw)
        return order, None, 2
    except ValidationError as exc:
        return None, to_tool_error(exc), 2


def main() -> None:
    """Send three customer requests through the loop."""
    live = "--live" in sys.argv
    ask = ask_codex_live if live else ask_codex_offline

    banner(f"PART 5 -- {'live codex exec' if live else 'offline canned replies'}")
    if not live:
        print(f"  {DIM}(run it again with --live to see a real model do this){OFF}\n")

    for request in CANNED:
        print(f'  customer: "{request}"')
        order, err, attempts = structured_request(request, ask)
        if order is not None:
            accepted(f"validated after {attempts} attempt(s)", order.model_dump_json())
        elif err is not None:
            rejected(f"gave up after {attempts} attempt(s)", err.message[:90])
        else:
            print("    (TODO 10 is not finished yet)")
        print()

    print("  The schema shaped the reply. Validation decided whether to trust it.")
    print()
    print("  Now notice what neither of them did: check whether the order is what")
    print("  the customer actually wanted. When you run --live, look closely at")
    print("  the hundred-burrito request. A reply can satisfy every rule you")
    print("  wrote and still be the wrong order.")
    print()
    print("  Pydantic answers exactly one question: does this data fit the shape")
    print("  I described? It has nothing to say about whether the data is true or")
    print("  useful. Knowing that boundary is most of what separates an agent")
    print("  that works from one that merely runs.")


if __name__ == "__main__":
    main()
