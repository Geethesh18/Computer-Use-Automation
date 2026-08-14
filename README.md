# Computer-Use Automation System

A take-home engineering project implementing an LLM-assisted computer-use automation system.

The system allows an LLM to discover how to complete a task against a live user interface, records the successful workflow as a structured capability artifact, and later replays that capability deterministically without requiring the LLM to make decisions.

## Core Idea

```text
Natural-Language Goal
        ↓
LLM Discovery Agent
        ↓
Live UI Interaction
        ↓
Successful Discovery
        ↓
Capability Artifact
        ↓
Deterministic Replay
        ↓
Structured Result
```

Safety guardrails, observability, error handling, and human escalation operate across the system.

## Technology Stack

| Component          | Technology                            |
| ------------------ | ------------------------------------- |
| Language           | Python 3.12                           |
| Target Application | Local mock legacy banking application |
| Web Framework      | FastAPI + Jinja2                      |
| Browser Automation | Playwright                            |
| Artifact Format    | JSON                                  |
| Schema Validation  | Pydantic                              |
| Testing            | pytest                                |
| Logging            | Structured JSON                       |
| Configuration      | Environment variables                 |

## Target Application

The project uses a local mock banking application to demonstrate a realistic multi-step workflow without interacting with real financial systems or sensitive information.

Primary demonstration flow:

```text
Member Search
      ↓
Enter Member ID
      ↓
Member Details
      ↓
Savings Account
      ↓
Retrieve Balance
```

The mock application will also support controlled exceptional states such as:

* Member not found
* Invalid member ID
* Permission denied
* Slow response
* Unexpected dialogs
* Session expiration

## Architecture

The system separates discovery from production execution.

### Discovery

```text
Goal
 ↓
Discovery Agent
 ↓
Observe UI
 ↓
LLM Decision
 ↓
Safety Policy
 ↓
Execute Action
 ↓
Observe New State
 ↓
Repeat Until Goal Is Complete
```

The LLM is used during discovery to determine how to accomplish a goal.

### Capability Artifact

After a successful discovery run, the workflow is converted into a typed and versioned JSON capability artifact.

The artifact contains:

* Capability metadata and version
* Typed input parameters
* Ordered actions
* Element/control locators
* Typed outputs
* Checkpoints and success conditions
* Error/outcome definitions
* Relevant policy metadata

The artifact is independent of the raw LLM conversation.

### Deterministic Replay

```text
Capability Artifact
        +
Input Parameters
        ↓
Replay Engine
        ↓
Safety Policy
        ↓
Computer Surface
        ↓
Application
        ↓
Checkpoint Verification
        ↓
Output Extraction
        ↓
Structured Result
```

The replay engine executes saved capabilities without using an LLM to decide the next action.

## Surface Abstraction

UI interaction is isolated behind a `ComputerSurface` abstraction.

The initial implementation uses Playwright:

```text
ComputerSurface
       ↑
PlaywrightSurface
```

This allows future implementations to support other environments such as legacy web applications, accessibility-based automation, or desktop applications without redesigning the capability model.

## Result Model

Replay distinguishes between:

```text
SUCCESS
BUSINESS_OUTCOME
FAILURE
```

For example, a member not existing is treated as a legitimate business outcome rather than a software crash.

Recoverable runtime conditions can use bounded retries, while hard failures stop execution and return debugging information.

## Safety

Every proposed action passes through a centralized safety policy before execution.

The safety layer will enforce:

* Allowed domains and routes
* Allowed action types
* Restrictions on risky or irreversible actions
* Sensitive-data redaction
* Prevention of credentials and secrets from entering artifacts or logs

## Human Escalation

The system supports pausing automation and transferring control of the same live session to a human operator.

```text
Automation
    ↓
Problem Detected
    ↓
Pause
    ↓
Human Control
    ↓
Manual Action
    ↓
Resume
    ↓
Automation
```

The reason for escalation and human actions will be recorded as evidence.

## Observability

Discovery and replay generate structured evidence including:

* Run IDs
* Step numbers
* Observations
* Decisions
* Actions
* Results
* Errors/outcomes
* Timestamps
* Screenshots or traces on failure

## Project Structure

The planned project structure is:

```text
computer-use-automation/
├── README.md
├── REPORT.md
├── docs/
│   └── architecture.md
├── src/
│   ├── agent/
│   ├── artifacts/
│   ├── replay/
│   ├── surfaces/
│   ├── safety/
│   ├── escalation/
│   └── observability/
├── artifacts/
├── evidence/
└── tests/
```

## Setup

Setup instructions will be added as implementation progresses.

## Running Discovery

The command for running an LLM-driven discovery will be added after the discovery agent is implemented.

## Running Replay

The command for deterministic replay will be added after the replay engine is implemented.

## Project Status

* [x] Step 1 — Architecture and technology decisions
* [x] Step 2 — Project setup and mock banking application
* [x] Step 3 — Capability artifact schema
* [x] Step 4 — Computer surface abstraction
* [ ] Step 5 — Deterministic replay engine
* [ ] Step 6 — LLM discovery agent
* [ ] Step 7 — Artifact generation
* [ ] Step 8 — Error handling
* [ ] Step 9 — Safety guardrails
* [ ] Step 10 — Human escalation
* [ ] Step 11 — Evidence and testing
* [ ] Step 12 — Final README and design report
