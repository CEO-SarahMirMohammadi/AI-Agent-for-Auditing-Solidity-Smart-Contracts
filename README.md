A professional, easy-to-use Solidity auditing assistant built in Python.
This project combines static code checks, a lightweight ML anomaly detector,
and a Groq LLM reviewer to help you inspect smart contracts.

## What it does

- Runs fast static pattern checks on Solidity source code for common issues.
- Computes an anomaly score using an IsolationForest model.
- Calls a Groq or OpenAI-compatible LLM to describe flagged snippets and suggest fixes.
- Supports retraining the detector from CSV data and generating calibration reports.

## Key capabilities

### 1. Static analysis

The project uses simple, readable static checks to identify risky Solidity patterns.
It searches for:

- `tx.origin` usage
- low-level calls such as `.call(...)`, `.delegatecall(...)`, `.transfer(...)`, `.send(...)`
- inline `assembly`
- loop statements like `for` and `while`
- balance access using `.balance`
- public function declarations that may require deliberate access control

These findings are reported with line numbers, snippets, and human-friendly details.

### 2. ML anomaly detection

A lightweight `IsolationForest` is used to flag contracts that look unusual.
The detector works from numeric features such as:

- source lines of code (LOC)
- function and modifier counts
- number of low-level calls
- branch statements
- assembly usage
- payable declarations

The model is unsupervised, so it does not require labeled vulnerabilities.
Instead, it learns a baseline from synthetic or CSV data and signals contracts with
outlier feature values.

### 3. Groq / LLM review

When configured with `OPENAI_API_KEY`, the tool sends suspicious snippets to
ChatGPT and asks for concise explanations and remediation advice. It also supports 
`Groq_API_KEY`(Recomended).

This makes the output more actionable by combining machine reasoning with the
code-level findings.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Environment setup

Groq HTTP API configuration (Recomended):

```powershell
setx GROQ_API_KEY "your_groq_api_key"
setx GROQ_MODEL "llama-3.3-70b-versatile"
```

Fallback OpenAI-compatible configuration:

```powershell
setx OPENAI_API_KEY "your_openai_key"
setx OPENAI_MODEL "gpt-4o"
```

Recommended Groq models for the OpenAI-compatible endpoint include `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`. The client now queries your Groq account for available models and validates `GROQ_MODEL` before use.

Optionally copy `.env.example` to `.env` and fill in the same variables for local use.

### Optional diagnostics

```powershell
python test_groq_models.py
python test_groq_connection.py
```

`test_groq_models.py` queries `https://api.groq.com/openai/v1/models`, lists models available to your Groq account, and saves them to `models.json`.

`test_groq_connection.py` checks DNS, OPTIONS connectivity, and authenticated Groq POST behavior.

## Usage guide

### Run a single-contract audit

```powershell
python -m audit_agent.cli path\to\Contract.sol --top 5
```

This will:

- perform static checks
- score the contract with the ML detector
- send the top flagged snippets to the LLM

You can also pass a Groq key directly on the CLI for a single run:

```powershell
python -m audit_agent.cli path\to\Contract.sol --groq-key your_groq_key
```

### Retrain the detector from CSV data

```powershell
python -m audit_agent.cli path\to\Contract.sol --retrain data\synthetic_features.csv --top 5
```

This uses `data/synthetic_features.csv` to fit a new IsolationForest model.
The retrained detector will then score the current contract.

### Generate a calibration plot

```powershell
python -m audit_agent.calibrate --data data\synthetic_features.csv --output calibration.png
```

This script loads the CSV feature data, fits the detector, and saves a visual
plot of the calibration dataset.

### Print a calibration report

```powershell
python -m audit_agent.calibrate --data data\synthetic_features.csv --report
```

This prints summary statistics for the calibration dataset, including:

- number of samples
- mean and standard deviation of anomaly scores
- anomaly count
- sample filenames and labels

## Project structure

- `audit_agent/cli.py` — main command-line interface
- `audit_agent/auditor.py` — static checks, feature extraction, ML scoring
- `audit_agent/llm_client.py` — Groq/OpenAI-compatible review wrapper
- `audit_agent/calibrate.py` — CSV-based calibration and plot generation
- `audit_agent/calibration_report.py` — readable calibration summary
- `data/synthetic_features.csv` — example feature data used for retraining
- `examples/` — Solidity contract examples for smoke testing

## How the logic works

### Static checks

The static analyzer reads Solidity source line by line and applies regular
expressions to detect risky patterns. It is fast and intended to catch
obvious issues that deserve a closer look.

### Feature extraction

The detector converts a contract into a numeric feature vector. Each feature is
chosen to capture contract complexity and risk surface, for example:

- a large number of functions or branches may increase risk
- low-level calls and assembly are often security-sensitive
- payable functions and balance reads are potential attack vectors

### Detection algorithm

`IsolationForest` is an unsupervised anomaly detector. It learns a baseline from
feature vectors and assigns an anomaly score to each new contract.
A lower score means the contract is more unusual compared to the training data.
This is useful for prioritizing review rather than providing a binary verdict.

### LLM review

The agent sends the most suspicious snippets to an LLM and asks for a concise
audit-style explanation. This turns low-level findings into a human-readable
report and helps developers understand the reasoning behind each flag.

## Recommendations

- Use the CLI for quick audits of single Solidity files.
- Use `--retrain` when you want the detector to adapt to new feature distributions.
- Use `calibrate.py` and `--report` to inspect the ML baseline and ensure the model
  fits your dataset.
- Always treat the output as audit support, not a substitute for manual review.
- Notice this project is only for EDUCATIONAL PURPOSES, NOT for commercial use as it may MAKE MISTAKES...

## License

MIT-style: use and adapt at your own risk.
