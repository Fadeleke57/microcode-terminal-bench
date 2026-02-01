# nanocode

Minimal Claude Code alternative using DSPy RLM! Single Python file, ~305 lines.

Built using Claude Code, then used to build itself.

![screenshot](https://d1pz4mbco29rws.cloudfront.net/public/nanocode.png)

## Features

- Full agentic loop with tool use via [DSPy RLM](https://dspy.ai/)
- Tools: `read`, `write`, `edit`, `glob`, `grep`, `bash`
- Conversation history with context
- Colored terminal output
- **Modaic Integration**: Push, version, and share as a [Modaic](https://modaic.dev) autoprogram

---

## Prerequisites

Before using nanocode (or any DSPy RLM-based program), you need to install the Deno code interpreter:

```bash
brew install deno
```

This is required for the RLM's code execution capabilities.

---

## Quick Start

### Option 1: Use as a Modaic AutoProgram

Load and run nanocode directly from the Modaic Hub without cloning:

```python
from modaic import AutoProgram

# Load the precompiled nanocode agent from Modaic Hub
agent = AutoProgram.from_precompiled(
    "farouk1/nanocode",
    config={
        "lm": "openrouter/openai/gpt-5.2-codex",
        "max_iters": 50
    }
)

# Run a coding task
result = agent(task="What Python files are in this directory?")
print(result.answer)
```

### Option 2: Run Locally (Interactive CLI)

```bash
export OPENROUTER_API_KEY="your-key"
python nanocode.py
```

To use a specific model:

```bash
export OPENROUTER_API_KEY="your-key"
export MODEL="openai/gpt-4"
python nanocode.py
```

---

## Configuration

When using as a Modaic AutoProgram, you can configure these options:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lm` | str | `openrouter/openai/gpt-5.2-codex` | Primary language model |
| `sub_lm` | str | `openrouter/openai/gpt-5-mini` | Sub-LM for reasoning steps |
| `max_iters` | int | `50` | Maximum agent iterations |
| `api_base` | str | `https://openrouter.ai/api/v1` | API base URL |
| `max_tokens` | int | `50000` | Maximum tokens per request |
| `max_output_chars` | int | `100000` | Maximum output character limit |
| `verbose` | bool | `False` | Enable verbose logging |
| `track_usage` | bool | `True` | Track token usage |

Example with custom configuration:

```python
from modaic import AutoProgram

agent = AutoProgram.from_precompiled(
    "farouk1/nanocode",
    config={
        "lm": "openrouter/anthropic/claude-sonnet-4",
        "sub_lm": "openrouter/openai/gpt-4.1-mini",
        "max_iters": 30,
        "max_tokens": 8000,
        "verbose": True,
        "track_usage": False
    }
)
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `/c` | Clear conversation history |
| `/q` or `exit` | Quit the application |

---

## Tools

The agent has access to the following tools:

| Tool | Description |
|------|-------------|
| `read_file(path, offset, limit)` | Read file contents with line numbers |
| `write_file(path, content)` | Write content to a file |
| `edit_file(path, old, new, replace_all)` | Replace text in a file (old must be unique unless `replace_all=True`) |
| `glob_files(pattern, path)` | Find files matching a glob pattern, sorted by modification time |
| `grep_files(pattern, path)` | Search files for a regex pattern |
| `run_bash(cmd)` | Run a shell command and return output |

---

## Example Usage

### Interactive CLI

```
────────────────────────────────────────
❯ what files are here?
────────────────────────────────────────

⏺ Thinking...
  ⏺ globfiles(pattern='**/*', path='.')

⏺ I found the following files:
  - nanocode.py
  - README.md
  - modaic/SKILL.md
```

### Programmatic Usage

```python
from modaic import AutoProgram

agent = AutoProgram.from_precompiled("farouk1/nanocode")

# Read a file
result = agent(task="Read the first 10 lines of nanocode.py")
print(result.answer)

# Search for patterns
result = agent(task="Find all functions that contain 'file' in their name")
print(result.answer)

# Make edits
result = agent(task="Add a comment at the top of README.md")
print(result.answer)
```

---

## Architecture

### Overview

```
nanocode.py
├── File Operations
│   ├── read_file()    - Read with line numbers
│   ├── write_file()   - Write content
│   └── edit_file()    - Find & replace
├── Search Operations
│   ├── glob_files()   - Pattern matching
│   └── grep_files()   - Regex search
├── Shell Operations
│   └── run_bash()     - Execute commands
├── DSPy Components
│   ├── CodingAssistant (Signature)
│   ├── RLMCodingProgram (PrecompiledProgram)
│   │   ├── forward()     - Run agent on task
│   │   ├── get_tools()   - Get available tools
│   │   ├── set_tool()    - Add/replace a tool
│   │   ├── remove_tool() - Remove a tool
│   │   ├── reload_lms()  - Recreate LMs from config
│   │   └── load_state()  - Load state with LM fix
│   └── RLMReasoningCallback
└── Modaic Integration
    └── RLMCodingConfig (PrecompiledConfig)
```

### Key Classes

#### `RLMCodingConfig`
Configuration class extending `PrecompiledConfig` for experiment-specific parameters.

```python
class RLMCodingConfig(PrecompiledConfig):
    max_iters: int = 50
    lm: str = "openrouter/openai/gpt-5.2-codex"
    sub_lm: str = "openrouter/openai/gpt-5-mini"
    api_base: str = "https://openrouter.ai/api/v1"
    max_tokens: int = 50000
    max_output_chars: int = 100000
    verbose: bool = False
    track_usage: bool = True
```

#### `RLMCodingProgram`
Main program class extending `PrecompiledProgram`. Wraps a DSPy RLM agent with coding tools.

```python
class RLMCodingProgram(PrecompiledProgram):
    config: RLMCodingConfig

    def forward(self, task: str) -> dspy.Prediction:
        # Returns prediction with .answer
        return self.agent(task=task)

    def get_tools(self) -> dict:
        # Returns dict of available tools

    def set_tool(self, name: str, tool: callable):
        # Add or replace a tool

    def remove_tool(self, name: str):
        # Remove a tool by name

    def reload_lms(self):
        # Recreate LM objects from current config
```

#### `CodingAssistant`
DSPy Signature defining the agent's input/output schema.

```python
class CodingAssistant(dspy.Signature):
    """You are a concise coding assistant with access to sub agents."""

    task: str = dspy.InputField(desc="The user's coding task or question")
    answer: str = dspy.OutputField(desc="Your response to the user after completing the task")
```

---

## Publishing Your Own Version

If you modify nanocode and want to publish your own version to Modaic Hub:

```python
from nanocode import RLMCodingProgram, RLMCodingConfig

# Create and optionally optimize your program
program = RLMCodingProgram(RLMCodingConfig())

# Push to your Modaic Hub repo
program.push_to_hub(
    "your-username/my-nanocode",
    commit_message="My customized nanocode",
    with_code=True  # Include source code for AutoProgram loading
)
```

---

## Dependencies

- [DSPy](https://dspy.ai/) - Framework for programming language models
- [Modaic](https://modaic.dev/) - Hub for sharing and versioning DSPy programs
- OpenRouter API key (for accessing language models)

Install dependencies:

```bash
pip install dspy modaic
# or with uv
uv add dspy modaic
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | Your OpenRouter API key |
| `MODEL` | No | Override the default model selection |
| `MODAIC_TOKEN` | For Hub | Required for pushing/loading from Modaic Hub |

---

## License

MIT
