# HW 0 — Answers

Name: Zhuoshen Cheng
USC email: zhuoshen@usc.edu

Six short questions. One or two sentences each is enough; nobody is looking for
an essay. These matter more than they look: the code shows you can use Pydantic,
and this file shows you know why you used it.

---

### Q1 (Part 1)

Run `part1_before.py` **before** you write TODO 1 and TODO 2.

Two replies are marked `ESCAPED`. A third reply is marked `ACCEPTED` even though
it should not have been. Which one is it, and why did the `ESCAPED` counter not
notice it?

The third bad reply was the order with the smuggled-in `price_override` field.
It should have been rejected because `price_override` was not one of the four
requested fields. The ESCAPED counter did not notice it because the current
kitchen and payment code ignores that extra field, so it caused no observable
damage in this run. However, allowing unknown fields is unsafe because future
downstream code might read `price_override` and change the price.

---

### Q2 (Parts 1 and 2)

Part 1 accepted `{"quantity": "3"}` and quietly ordered 3 tacos, because
`int("3")` succeeds. Part 2 rejected the same reply, because of `strict=True`.

Which behaviour do you want in an agent, and why? Either answer is acceptable if
you defend it.

> I prefer strict validation in an agent because silently converting the model's
> output can hide a mistake. Rejecting `"3"` makes the type mismatch visible and
> gives the model a chance to correct it explicitly.

---

### Q3 (Part 2)

Three settings do three different jobs: `strict=True`, `Field(ge=..., le=...)`,
and `extra="forbid"`.

For each reply below, say which one rejects it, and whether either of the other
two would also have caught it.

| reply | rejected by | would the others catch it? |
|---|---|---|
| `{"item":"taco","quantity":"3","spice":"hot"}` | `strict=True` | No. The range constraint would accept 3 after coercion, and `extra="forbid"` only checks field names. |
| `{"item":"taco","quantity":0,"spice":"hot"}` | `Field(ge=1, le=20)` | No. Zero is already an integer, and there are no extra fields. |
| `{"item":"taco","quantity":1,"spice":"hot","price_override":0}` | `extra="forbid"` | No. The declared values have valid types and ranges. |

---

### Q4 (Part 3)

`to_tool_error` builds its message out of the `loc` and `msg` values from
`exc.errors()`, rather than just using `str(exc)`.

Name one concrete thing that could go wrong in a real system if you sent
`str(exc)` back to an AI model instead. Run `part3_errors.py` and compare the
two printed versions if you need a reminder.

> `str(exc)` can echo attacker-controlled or sensitive input and internal details
> such as class names and library-version links back to the model, while also
> growing without a safe length bound.

---

### Q5 (Part 4)

The injected `refund_everything` call was stopped by the allowlist, not by
Pydantic. No schema was involved in that decision.

State the general rule this illustrates: what does validation decide, and what
does it not decide?

> Validation decides whether arguments have the expected fields, types, and
> constraints; it does not decide whether a tool is authorized or safe to call.

---

### Q6 (Part 5, bonus)

Run `python part5_codex.py --live` once and paste the output below.

Your schema says `quantity` may not exceed 20. Look at what the model did with
the request for a hundred burritos. Did it come back with something that was
**valid but wrong** — that is, something that passed every check you wrote and
was still not what the customer asked for?

What check, outside Pydantic, would catch that?

```
  customer: "3 hot tacos please"
  ACCEPTED  validated after 1 attempt(s)       {"item":"burrito","quantity":1,"spice":"medium","notes":"No customer request provided."}

  customer: "gimme like a hundred burritos for the club, mild"
  ACCEPTED  validated after 1 attempt(s)       {"item":"burrito","quantity":1,"spice":"medium","notes":"No customer order details provided"}

  customer: "two medium bowls, no beans"
  ACCEPTED  validated after 1 attempt(s)       {"item":"taco","quantity":1,"spice":"mild","notes":"No customer order details provided"}

 
```

> Yes. For the hundred-burrito request, the model returned one medium burrito,
> which passed every schema check but did not match the customer's request. A
> separate semantic check against the original request, or explicit user
> confirmation before ordering, would catch this mismatch.

---

### Verification and reproducibility note

Three bullets, as required by the course AI policy. You do not need to list
prompts or coding assistants.

1. Model(s) used by the submitted code: The Codex CLI's configured model for the Part 5 live run; offline tests used deterministic canned replies.
2. How you tested this submission: Ran each numbered script, ran `python part5_codex.py --live`, and ran `python -m pytest -q` until all 34 tests passed.
3. One known failure or limitation, or "none found": Schema validation cannot determine whether a structurally valid order matches the customer's actual request.
