# Technical Report — Computer-Use Automation

## 1. Executive Summary

This project implements a prototype computer-use automation architecture that separates **LLM-driven workflow discovery** from **deterministic capability replay**.

The central design principle is:

> Use the model to discover how to perform a workflow, then convert the successful interaction into a typed reusable artifact that can be executed later without model reasoning.

A local mock banking portal serves as the live computer-use surface. The implemented vertical slice supports the capability:

> Look up a member and return their current savings balance.

The prototype demonstrates the complete lifecycle:

```text
Natural-language goal
        ↓
LLM-driven discovery
        ↓
Live browser interaction
        ↓
Successful discovery trace
        ↓
Artifact generation
        ↓
Typed + parameterized capability
        ↓
Deterministic replay
        ↓
Structured output
```

A genuine Groq-driven discovery was performed using member `10001`, returning a savings balance of `$4520.75`.

That discovery trace was converted into a reusable artifact. The generated artifact was subsequently replayed **without an LLM** using member `10002`, returning `$9875.20`.

The system additionally implements typed artifacts, checkpoints, business outcomes, bounded recovery, deterministic safety enforcement, failure evidence, and structured human handoff.

---

## 2. Problem Interpretation

The main engineering challenge is not simply controlling a browser with an LLM.

A model can often reason successfully about a user interface, but repeatedly invoking a model for a workflow that has already been discovered introduces several undesirable properties:

- additional latency,
- additional cost,
- nondeterministic execution,
- repeated reasoning over an already-known workflow,
- more opportunities for unsafe or inconsistent actions,
- difficulty validating production behavior.

The architecture therefore separates two responsibilities.

### Discovery

Discovery is adaptive.

The system observes the current UI, asks an LLM for one structured next action, executes the authorized action, observes again, and repeats until the goal is complete or escalation is required.

### Replay

Replay is deterministic.

Once discovery has produced a successful workflow, the useful interaction information is normalized into a typed artifact.

Future invocations execute that artifact directly.

No LLM is required in the replay path.

This separation allows model reasoning to be used where it provides the most value—understanding an unfamiliar interface—while deterministic software handles repeated execution.

---

## 3. System Architecture

The implementation consists of the following primary layers:

```text
User Goal
   ↓
DiscoveryAgent
   ↓
LLMClient / GroqLLMClient
   ↓
SafetyPolicy
   ↓
ComputerSurface
   ↓
PlaywrightSurface
   ↓
Mock Banking Application
```

Successful discovery produces:

```text
DiscoveryResult
      ↓
ArtifactBuilder
      ↓
CapabilityArtifact
```

Future execution uses:

```text
CapabilityArtifact
        +
Invocation Inputs
        ↓
ReplayEngine
        ↓
SafetyPolicy
        ↓
ComputerSurface
        ↓
Structured ReplayResult
```

When automation should not proceed:

```text
Unsafe / uncertain condition
        ↓
HandoffManager
        ↓
HandoffPackage
        ↓
Human review
```

### Major modules

`src/discovery/`

Contains the adaptive LLM-driven discovery path.

`src/artifacts/`

Contains the typed artifact schema, loader, and discovery-to-artifact builder.

`src/replay/`

Contains deterministic artifact execution and structured replay results.

`src/surfaces/`

Defines the computer-surface abstraction and Playwright implementation.

`src/safety/`

Contains deterministic central authorization policy.

`src/handoff/`

Creates structured context when human intervention is required.

`src/mock_bank/`

Contains the local FastAPI/Jinja mock banking application.

---

## 4. Computer-Use Surface

Browser interaction is abstracted through `ComputerSurface`.

The interface exposes operations such as:

```text
navigate
fill
click
extract_text
get_url
get_visible_text
screenshot
```

`PlaywrightSurface` implements this abstraction using Chromium and Playwright.

This design prevents discovery and replay from depending directly on Playwright APIs.

It also provides a natural extension point for other computer-use implementations.

### Locator strategy

The implementation prefers:

1. accessibility role + accessible name,
2. visible text,
3. CSS fallback.

This became relevant during the savings-account workflow.

The Accounts page contains two links with the same accessible name:

```text
Savings     View Account
Checking    View Account
```

A locator based only on:

```text
role = link
name = View Account
```

is ambiguous.

During genuine discovery, the model selected a contextual CSS locator:

```css
tr:has-text('Savings') a
```

This allowed the system to identify the correct account while preserving the surrounding row context.

---

## 5. LLM-Driven Discovery

Discovery uses an observe-decide-act loop.

```text
Observe UI
    ↓
Send goal + observation + history to LLM
    ↓
Receive typed AgentDecision
    ↓
Authorize proposed action
    ↓
Execute action
    ↓
Observe resulting UI
```

The LLM returns exactly one structured decision at a time.

Supported discovery action labels include:

```text
fill
click
navigate
read
complete
escalate
```

The model does not directly invoke browser tools.

Instead, it returns a typed proposal such as:

```json
{
  "action": "fill",
  "target": {
    "role": "textbox",
    "name": "Member ID",
    "text": null,
    "css": null
  },
  "value": "10001",
  "outputs": {
    "balance": null
  },
  "reason": "Fill the Member ID textbox with the target member ID."
}
```

The `DiscoveryAgent` interprets that decision and routes the proposed action through deterministic safety checks before reaching the browser surface.

### Genuine discovery run

A genuine Groq-backed discovery was performed with the goal:

```text
Look up member 10001 and return their current savings balance.
```

The model discovered the following workflow:

```text
1. Fill Member ID with 10001
2. Click Search Member
3. Click View Accounts
4. Select the Savings account contextually
5. Observe Current Balance
6. Complete with balance = 4520.75
```

The complete discovery trace is preserved at:

```text
evidence/discovery_success_10001.json
```

This evidence includes observations, model decisions, targets, action results, and the final structured output.

---

## 6. Structured LLM Output

The discovery integration uses Pydantic models to define the expected LLM response.

Important models include:

```text
DiscoveryAction
DiscoveryTarget
DiscoveryOutputs
AgentDecision
Observation
DiscoveryStep
DiscoveryResult
```

Strict structured output prevents arbitrary free-form model responses from becoming executable browser commands.

The model's responsibility is therefore constrained to producing a decision that conforms to a known schema.

The application remains responsible for:

- validation,
- authorization,
- execution,
- recovery,
- escalation.

---

## 7. Capability Artifact Design

The reusable capability is represented by a typed `CapabilityArtifact`.

The artifact includes:

- schema version,
- capability name,
- capability version,
- description,
- typed inputs,
- typed outputs,
- entrypoint,
- ordered steps,
- locators,
- parameterized values,
- checkpoints,
- success condition,
- expected business outcomes,
- failure conditions,
- policy metadata.

The generated capability is stored at:

```text
artifacts/generated_lookup_savings_balance.v1.json
```

### Artifact vs. model transcript

The raw LLM transcript is not treated as the production capability.

Instead, discovery information is normalized into an executable contract.

For example, discovery performed:

```text
Fill Member ID with "10001"
```

The artifact stores:

```text
Fill Member ID with "{{ member_id }}"
```

Similarly:

```text
/members/10001/accounts
```

is generalized to:

```text
/members/{{ member_id }}/accounts
```

This is what allows a single successful discovery to become reusable.

---

## 8. Artifact Generation

`ArtifactBuilder` converts a successful `DiscoveryResult` into a deterministic `CapabilityArtifact`.

The builder:

- verifies discovery succeeded,
- verifies the expected output exists,
- keeps successfully executed UI actions,
- removes discovery-only `COMPLETE` and `READ` actions,
- rejects escalated discovery,
- converts discovery targets into artifact locators,
- parameterizes the discovered member ID,
- derives URL checkpoints,
- parameterizes member-specific checkpoints,
- adds deterministic balance extraction,
- attaches business outcomes and failure conditions,
- attaches read-only policy metadata.

This process intentionally discards model reasoning as an execution dependency.

The resulting artifact is independently validated using the Pydantic artifact schema.

---

## 9. Deterministic Replay

`ReplayEngine` executes a saved artifact without consulting an LLM.

The replay lifecycle is:

```text
Validate invocation inputs
        ↓
Validate artifact safety
        ↓
Start computer surface
        ↓
Navigate to entrypoint
        ↓
Execute ordered steps
        ↓
Verify checkpoints
        ↓
Detect business/failure states
        ↓
Extract typed output
        ↓
Verify success condition
        ↓
Return ReplayResult
```

### Different-input replay

The strongest demonstration of artifact reuse is:

```text
Discovery:
member_id = 10001
balance   = 4520.75
```

followed by:

```text
Deterministic replay:
member_id = 10002
balance   = 9875.20
```

The second execution uses the generated artifact and performs no LLM call.

Evidence:

```text
evidence/replay/success_10002.json
```

---

## 10. Checkpoints

Replay does not assume that an action succeeded simply because the browser API returned successfully.

Artifact steps may define checkpoints.

For example:

```text
/members/{{ member_id }}/accounts
```

During invocation with:

```text
member_id = 10002
```

the replay engine resolves this to:

```text
/members/10002/accounts
```

and verifies that the current browser URL contains the expected state.

Checkpoint failure produces a structured:

```text
CHECKPOINT_FAILED
```

result rather than allowing execution to continue blindly.

---

## 11. Output Extraction

The artifact declares:

```text
balance → number
```

The replay engine extracts the value associated with:

```text
Current Balance
```

The mock banking application may expose the label/value pair as either:

```text
Current Balance    $4520.75
```

or consecutive visible-text lines.

The extraction layer handles both representations.

The raw monetary string is then normalized and converted to a numeric output.

Example:

```text
"$4520.75"
```

becomes:

```json
4520.75
```

---

## 12. Business Outcomes and Failures

The implementation deliberately distinguishes expected business outcomes from system failures.

### Successful execution

```text
status = success
```

### Member not found

Member:

```text
99999
```

produces:

```text
status = business_outcome
code   = MEMBER_NOT_FOUND
```

This is not treated as a system crash because the application behaved correctly—the requested member simply does not exist.

Evidence:

```text
evidence/replay/member_not_found_99999.json
```

### Permission denied

Member:

```text
10003
```

is intentionally restricted.

Replay produces:

```text
status = failure
code   = PERMISSION_DENIED
```

Evidence:

```text
evidence/replay/permission_denied_10003.json
```

Failure screenshots are also captured when appropriate.

---

## 13. Bounded Recovery

Transient UI failures are handled using deterministic bounded retries.

The default configuration is:

```text
max_retries = 2
```

which means:

```text
initial attempt
retry 1
retry 2
```

for a maximum of three attempts.

The retry mechanism does not invoke an LLM.

Automated tests demonstrate both:

### Recoverable transient failure

```text
First click fails
    ↓
Replay retries
    ↓
Second click succeeds
    ↓
Workflow completes successfully
```

### Permanent failure

```text
Attempt 1 fails
Attempt 2 fails
Attempt 3 fails
    ↓
STEP_EXECUTION_FAILED
```

The retry budget prevents uncontrolled execution loops.

---

## 14. Safety Model

Safety is enforced by `SafetyPolicy`.

The model is not the security boundary.

The artifact is also not the security boundary.

Both can propose actions, but deterministic policy determines whether execution is allowed.

### Policy controls

The current policy restricts:

- allowed origins,
- allowed action types,
- allowed risk levels,
- navigation destinations.

The mock application is limited to local approved origins such as:

```text
http://127.0.0.1:8000
```

External navigation is blocked.

### Artifact authorization

An artifact cannot grant itself broader permission merely by changing its own policy metadata.

Central policy independently validates the artifact.

### Runtime authorization

Actions are validated again immediately before execution.

Navigation destinations are also checked after parameter resolution.

This provides defense in depth.

### Safety failures are not retried

A `SafetyViolation` immediately stops execution.

The system does not:

- retry the unsafe action,
- ask the model to bypass policy,
- reinterpret the violation as a transient browser error.

---

## 15. Safety During Discovery

The same central safety model is used during LLM discovery.

The discovery path is:

```text
LLM proposes action
        ↓
DiscoveryAgent
        ↓
SafetyPolicy
        ↓
ALLOW / DENY
```

A fake deterministic test client was used to verify the safety boundary by proposing:

```text
navigate → https://example.com/
```

The central policy blocked the external navigation before execution.

This test is intentionally separate from the genuine Groq discovery evidence.

---

## 16. Human Escalation and Handoff

When discovery cannot safely continue, the system creates a structured `HandoffPackage`.

The package may contain:

- reason code,
- reason,
- goal,
- current URL,
- last observation,
- failed step,
- attempted actions,
- evidence path,
- suggested human action.

For example, an unsafe external navigation produces:

```text
SAFETY_VIOLATION
```

and a durable handoff record:

```text
evidence/handoffs/discovery_safety_violation.json
```

This allows automation to stop at a clear boundary while preserving enough context for a human operator to understand what happened.

The prototype intentionally does not automatically resume after human escalation.

---

## 17. Evidence Strategy

The repository contains several forms of evidence.

### Genuine LLM discovery

```text
evidence/discovery_success_10001.json
```

This is the primary evidence that an actual model participated in discovery.

### Deterministic replay

```text
evidence/replay/success_10001.json
evidence/replay/success_10002.json
```

### Expected business outcome

```text
evidence/replay/member_not_found_99999.json
```

### Hard failure

```text
evidence/replay/permission_denied_10003.json
```

### Safety and handoff

```text
evidence/handoffs/discovery_safety_violation.json
```

### Visual evidence

The evidence directory also contains screenshots captured from the browser and failure paths.

The safety/handoff demonstration uses a deterministic test double and should not be confused with the genuine Groq discovery evidence.

---

## 18. Testing and Validation

The final automated suite contains:

```text
21 passing tests
```

The tests cover:

- artifact schema validation,
- invalid artifact rejection,
- artifact generation,
- input parameterization,
- checkpoint parameterization,
- preservation of discovered locators,
- Playwright surface behavior,
- discovery observe-decide-act behavior,
- deterministic replay,
- replay with a different input,
- expected business outcomes,
- permission failures,
- transient recovery,
- exhausted retry budgets,
- allowed safety behavior,
- blocked origins,
- blocked actions,
- blocked risk levels,
- unsafe replay rejection,
- structured handoff persistence,
- unsafe discovery-action blocking,
- complete discovery → artifact → new-input replay.

### End-to-end test

`tests/test_end_to_end.py` performs the core architectural proof:

```text
Load genuine discovery evidence
        ↓
Validate discovery output = 4520.75
        ↓
Build capability artifact
        ↓
Verify member ID parameterization
        ↓
Replay with member 10002
        ↓
Verify output = 9875.20
```

This demonstrates that the discovery result is not merely a recording of one invocation.

It becomes a reusable capability.

---

## 19. Key Design Decisions

### 19.1 Use the LLM only where adaptation is required

An LLM is useful when the workflow is unknown.

Once the workflow has been discovered and validated, deterministic replay is more appropriate.

### 19.2 Keep the execution contract separate from reasoning

The artifact stores what is required for execution.

It does not depend on the raw model conversation.

### 19.3 Prefer semantic locators

Accessibility roles and names are preferred over coordinates.

CSS is used when contextual disambiguation is necessary.

### 19.4 Verify state after actions

Checkpoints reduce the risk of silently continuing after an unexpected UI transition.

### 19.5 Treat safety as code

Prompt instructions can guide model behavior but are not considered sufficient authorization.

### 19.6 Bound recovery

Retries are explicit and finite.

### 19.7 Distinguish business outcomes from technical failures

A missing member and a broken automation workflow represent different conditions and should produce different results.

### 19.8 Preserve context when stopping

Structured handoff is preferable to either blindly continuing or returning an opaque failure.

---

## 20. Tradeoffs

### Capability-specific artifact generation

The current `ArtifactBuilder` knows that the capability uses:

```text
member_id
balance
Savings
```

This makes the vertical slice clear and reliable but is not yet a fully generic artifact compiler.

A production implementation would infer or receive a richer capability specification and normalize arbitrary discovered workflows.

### DOM-assisted computer use

The prototype uses Playwright locators and visible text rather than raw screen coordinates.

This improves reliability and testability but represents one type of computer-use surface rather than every possible desktop application.

### Local deterministic application

A local mock banking system makes behavior reproducible and safe.

It does not reproduce every source of instability found in real enterprise applications.

### Read-only safety scope

The demonstrated capability is intentionally read-only.

The prototype therefore blocks higher-risk capabilities rather than implementing a full human approval workflow for irreversible financial actions.

---

## 21. Limitations

Current limitations include:

1. One primary capability is implemented: savings-balance lookup.
2. Artifact synthesis contains capability-specific normalization.
3. Output extraction is optimized for the mock banking UI.
4. Significant DOM changes could invalidate saved locators.
5. Checkpoint support is intentionally small.
6. The safety configuration is designed around a local read-only application.
7. Handoff is persisted as JSON rather than presented through an operator dashboard.
8. A new live discovery requires a locally configured Groq API key.
9. The prototype does not implement artifact signing or provenance verification.
10. The prototype does not maintain a multi-capability registry.

These limitations are deliberate scope choices for the vertical slice rather than hidden assumptions.

---

## 22. Future Improvements

Potential next steps include:

### Generic artifact synthesis

Generate capability artifacts from arbitrary successful discovery traces rather than capability-specific builder logic.

### Artifact registry

Store, version, search, and invoke multiple discovered capabilities.

### Compatibility detection

Detect when an application's UI has drifted beyond the artifact's compatibility assumptions.

### Locator healing

Support bounded deterministic fallback locators before requiring rediscovery.

### Artifact provenance

Associate artifacts with discovery evidence, application version, validation status, and cryptographic signatures.

### Richer safety policy

Add field-level restrictions, action-specific authorization, environment configuration, and explicit human approval for irreversible actions.

### Interactive handoff

Expose escalation context through an operator UI and optionally resume from an approved checkpoint.

### Observability

Capture execution duration, retry counts, checkpoint failures, artifact success rates, and drift indicators.

### Additional surfaces

Implement desktop or remote-computer surfaces behind the same `ComputerSurface` interface.

---

## 23. Conclusion

The prototype demonstrates that LLM-based computer use does not need to imply LLM-based execution forever.

A model can be used to understand and discover an unfamiliar workflow:

```text
goal
 ↓
observe
 ↓
reason
 ↓
act
 ↓
successful trace
```

The useful result can then be converted into a typed reusable artifact:

```text
successful trace
 ↓
normalize
 ↓
parameterize
 ↓
validate
 ↓
capability artifact
```

Future invocations execute that capability deterministically:

```text
artifact + input
       ↓
safety validation
       ↓
known browser actions
       ↓
checkpoints
       ↓
typed output
```

The completed vertical slice demonstrates this lifecycle with a genuine LLM discovery for member `10001` and a subsequent no-LLM replay for member `10002`.

It additionally demonstrates bounded recovery, explicit business outcomes, deterministic safety enforcement, failure evidence, and structured human escalation.

The result is a small but complete example of how adaptive model reasoning can be transformed into reusable, inspectable, and deterministic computer-use automation.