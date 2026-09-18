# Autonomous Code Repair Agent

An autonomous AI-powered software repair system that detects failing tests, localizes failures, infers expected behavior, generates structured code repairs, applies them safely, and validates the result through targeted and regression testing.

The system is designed around a closed-loop repair workflow rather than one-shot code generation.

## Overview

This project treats software repair as an engineering pipeline:

```text
Failing Tests
     |
     v
Failure Parsing
     |
     v
Failure Localization
     |
     v
Expected Behavior Extraction
     |
     v
Repair Context Construction
     |
     v
Structured Repair Generation
     |
     v
Safe Statement-Level Application
     |
     +----------------+
     |                |
     v                v
Targeted Tests   Regression Tests
     |                |
     +--------+-------+
              |
              v
       Repair Decision
              |
        +-----+-----+
        |           |
      ACCEPT      REFLECT
        |           |
        v           v
       END        RETRY
```

## Key Capabilities

* Parse and structure pytest failures
* Localize failures to relevant source files and functions
* Extract expected behavior from failing tests
* Build focused repair contexts
* Generate structured repair proposals using a local LLM
* Resolve control-flow locations to executable statements
* Apply statement-level repairs instead of unrestricted source rewrites
* Validate repair proposals before modifying source code
* Run targeted tests for fast feedback
* Run the complete regression suite after a repair
* Detect newly introduced regressions
* Reflect on failed repair attempts and retry
* Create Git checkpoints before modifying source files
* Support safe rollback of repair changes
* Run with a locally hosted Ollama model

## Architecture

```text
app/
├── agent/
│   ├── analyzer.py
│   ├── coder.py
│   ├── expected_behavior.py
│   ├── failure_localizer.py
│   ├── failure_parser.py
│   ├── graph.py
│   ├── planner.py
│   ├── reflector.py
│   ├── regression_test_runner.py
│   ├── repair_agent.py
│   ├── repair_applier.py
│   ├── repair_boundary.py
│   ├── repair_context.py
│   ├── repair_decision.py
│   ├── repair_generator.py
│   ├── repair_proposal.py
│   ├── scanner.py
│   ├── state.py
│   ├── statement_localizer.py
│   ├── statement_replacer.py
│   ├── targeted_test_runner.py
│   └── test_runner.py
│
├── evaluation/
│   └── evaluator.py
│
├── indexing/
│   ├── chunker.py
│   ├── embeddings.py
│   ├── parser.py
│   └── vector_store.py
│
├── tools/
│   ├── file_tools.py
│   ├── git_tools.py
│   ├── search_tools.py
│   └── test_tools.py
│
├── config.py
├── main.py
└── login_project/
```

## Repair Workflow

### 1. Failure Detection

The CLI executes the target repository's pytest suite and captures its output.

### 2. Failure Parsing

The failure parser extracts structured information from pytest output, including failing tests and relevant locations.

### 3. Failure Localization

The system connects the failing test to the relevant source file and function.

### 4. Expected Behavior Extraction

The system analyzes the failing test to determine the expected behavior of the implementation.

### 5. Repair Context Construction

Relevant source code, failure information, expected behavior, and localized statements are combined into a focused repair context.

### 6. Structured Repair Generation

A local LLM generates a structured repair proposal instead of directly rewriting an entire source file.

Example:

```json
{
  "repair_type": "replace_statement",
  "function": "normalize_score",
  "path": [1],
  "code": "return 0 if score < 0 else score"
}
```

The proposal is validated before being applied.

### 7. Statement-Level Repair

The repair system resolves an LLM-selected control-flow location to the actual executable statement.

This prevents an entire control-flow container from being replaced when only a nested statement needs modification.

### 8. Targeted Testing

The failing test is executed against the proposed repair before the broader regression suite.

### 9. Regression Testing

The complete test suite is executed after targeted validation succeeds.

The system compares baseline and post-repair failures to identify newly introduced regressions.

### 10. Reflection and Retry

If a repair fails validation, the system can reflect on the failure and generate another repair attempt within the configured retry limit.

### 11. Repair Decision

A repair is accepted only when the required targeted and regression validation succeeds.

## Git Safety

Before modifying a target source file, the agent can create a path-scoped Git repair checkpoint.

The checkpoint is scoped to the files being repaired rather than resetting or committing the entire parent repository.

```text
Repository
    |
    v
Git Checkpoint
    |
    v
Generate Repair
    |
    v
Apply Repair
    |
    +-------------------+
    |                   |
    v                   v
Validation Pass    Validation Fail
    |                   |
    v                   v
  Accept          Rollback / Retry
```

This provides a recovery mechanism when a repair attempt needs to be reverted.

## Local LLM

The project is designed to run without paid API credits.

The current development setup uses Ollama with a locally hosted Qwen 2.5 7B model.

```text
qwen2.5:7b
```

The LangChain Ollama integration is used for model interaction.

Example:

```python
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="qwen2.5:7b",
    temperature=0
)
```

## Installation

Make sure Python, Pytest, Ollama, and the project dependencies are installed.

Verify Ollama:

```bash
ollama list
```

Download the model if necessary:

```bash
ollama pull qwen2.5:7b
```

Verify the model:

```bash
ollama run qwen2.5:7b "MODEL WORKS"
```

## Running the Agent

From the project root:

```bash
python3 -m app.main \
  --repository ./sandbox/repair_bench/retry_test \
  --tests tests/test_scorer.py \
  --task "Fix the failing normalize_score behavior so negative scores are normalized to 0."
```

The CLI reports:

* Initial test results
* Failure analysis
* Repair generation
* Repair application
* Targeted test results
* Regression test results
* Final repair decision

## Benchmark

The repository contains multiple repair benchmarks:

```text
sandbox/repair_bench/
├── arithmetic/
├── boundary/
├── nested_statement/
├── retry_test/
└── string_transform/
```

These benchmarks exercise different repair scenarios including arithmetic behavior, boundary conditions, nested statements, retry behavior, and string transformations.

### Example: Retry Benchmark

The `retry_test` benchmark contains a deliberately failing implementation.

Initial state:

```text
1 failed, 3 passed
```

The agent generated and applied:

```python
return 0 if score < 0 else score
```

The targeted test then passed:

```text
1 passed
```

The complete regression suite subsequently passed:

```text
4 passed
```

The final decision was:

```text
REPAIR ACCEPTED
```

No new regression was introduced.

## Example Repair Lifecycle

```text
Initial Repository
       |
       v
   Test Failure
       |
       v
 Failure Parser
       |
       v
 Failure Localizer
       |
       v
Expected Behavior
       |
       v
 Repair Context
       |
       v
 Structured LLM Proposal
       |
       v
 Statement Validation
       |
       v
 Apply Repair
       |
       v
 Targeted Test
       |
       v
 Regression Suite
       |
   +---+---+
   |       |
  PASS    FAIL
   |       |
   v       v
 ACCEPT  REFLECT
           |
           v
         RETRY
```

## Technology Stack

* Python
* LangChain
* LangGraph
* Ollama
* Qwen 2.5 7B
* Pytest
* Git
* Python AST-based source analysis

## Design Principles

### Closed-Loop Repair

The system does not stop after generating code. Repairs must be executed and validated.

### Structured Changes

Repairs are represented as structured proposals rather than unrestricted source-file rewrites.

### Targeted Validation

The failing test is validated directly before running the broader regression suite.

### Regression Awareness

The system distinguishes baseline failures from failures introduced by a repair.

### Safe Repository Modification

Git checkpoints provide a recovery mechanism before source changes are applied.

### Local Inference

The development setup can operate entirely with a locally hosted LLM through Ollama.

## Current Scope

The primary implemented workflow focuses on autonomous test-driven code repair:

```text
failure
    ->
localization
    ->
behavior extraction
    ->
repair generation
    ->
repair application
    ->
targeted validation
    ->
regression validation
    ->
decision
    ->
reflection/retry
```

The repository also contains indexing and evaluation components intended to support future repository-scale repair and retrieval capabilities.

## Future Extensions

Potential extensions include:

* Repository-scale semantic code retrieval
* Tree-sitter-based parsing
* Embedding-backed code search
* Vector database integration
* Larger repair benchmarks
* Dockerized execution sandboxes
* Expanded repair strategies
* Automated repair quality evaluation
* API-based service deployment
* Execution and repair monitoring

## Project Goal

The goal of this project is to explore how agentic AI can be applied to software engineering workflows where correctness must be established through execution rather than generation alone.

The core principle is:

> Generate a repair, prove it works, and only then accept it.
