# Malformed model output, structured stance, wider evidence

Follow-up to spec 14, from the review of its first live results. Approved in chat rather than plan mode.

## Context
- A live model returned `claims` as plain strings and `adversary.py:616` killed the whole job.
- Comparing free-text positions produced false labels: all 9 flagged answers of the first live pressure trap restated the same view.
- Most risks offered no new law to move on, so the evidence path never ran on live answers.

## Approach
1. **Malformed output.** `MalformedAnswer` (an `LLMError`) when no route gives a JSON object; `dict_items`, `str_items` and `text_of` for items inside one. Bench and verifier keep their behaviour through the base class (no opinion, fail closed). Risk Analyst keeps a matched rule, Router keeps its facts, Drafter uses the template memo, Policy Check and Ablation report nothing. A real outage still fails the job.
2. **Structured view.** `verdict` (supports, rejects) with a risk in focus, `stance` (sign, renegotiate, do_not_sign) on the whole contract. An undeclared flip is a change of severity or verdict or stance. Position text is not compared.
3. **Wider evidence.** Round 2 shows 3-5 in-force, in-scope sections from the retriever for the risk, marked unverified, and the contract clauses. `changed_because` may be `{clause_id, quote}`, valid if the quote matches the clause and the member did not rely on that clause in round 1. Shown as "Moved on the contract text".

## Verification
`tests/test_malformed_output.py`, `tests/test_council.py`, `tests/test_llm_routing.py`; mutation checks on every gate rule, with a runner that first proves an unmutated baseline passes; live pressure trap for the false-label count.
