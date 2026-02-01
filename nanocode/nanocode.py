import os
from modaic import PrecompiledProgram, PrecompiledConfig
import dspy
import weave
import subprocess
from dspy.utils.callback import BaseCallback

MODAIC_REPO_PATH = "farouk1/nanocode"

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"

# --- File operations ---


def read_file(path: str, offset: int = 0, limit: int = None) -> str:
    """[EXTERNAL FILESYSTEM] Read file contents from disk with line numbers.

    Args:
        path: Path to the file to read
        offset: Line number to start from (0-indexed)
        limit: Maximum number of lines to read

    Returns:
        File contents with line numbers
    """
    lines = open(path).readlines()
    if limit is None:
        limit = len(lines)
    selected = lines[offset : offset + limit]
    content = "".join(
        f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected)
    )
    tokens = len(content) // 4  # ~4 chars per token estimate
    print(f"{MAGENTA}⏺ Reading file({path}) (~{tokens:,} tokens){RESET}")
    return content


def write_file(path: str, content: str) -> str:
    """[EXTERNAL FILESYSTEM] Write content to a file on disk (creates or overwrites).

    Args:
        path: Path to the file to write
        content: Content to write to the file

    Returns:
        Status message with file stats
    """
    is_new = not os.path.exists(path)
    action = "Creating" if is_new else "Overwriting"

    # Auto-create parent directories
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(path, "w") as f:
        f.write(content)

    lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    tokens = len(content) // 4
    print(
        f"{MAGENTA}⏺ {action} file({path}) ({lines} lines, ~{tokens:,} tokens){RESET}"
    )
    return f"ok: wrote {lines} lines ({tokens:,} tokens) to {path}"


def edit_file(path: str, old: str, new: str, replace_all: bool = False) -> str:
    """[EXTERNAL FILESYSTEM] Replace text in a file on disk.

    Args:
        path: Path to the file to edit
        old: Text to find and replace
        new: Replacement text
        replace_all: If True, replace all occurrences; otherwise old must be unique

    Returns:
        'ok' on success, error message on failure
    """
    print(f"{MAGENTA}⏺ Edit({path}){RESET}")

    text = open(path).read()
    if old not in text:
        return "error: old_string not found"
    count = text.count(old)
    if not replace_all and count > 1:
        return f"error: old_string appears {count} times, must be unique (use replace_all=True)"
    replacement = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    with open(path, "w") as f:
        f.write(replacement)
    return "ok"


def glob_files(pattern: str, path: str = ".") -> str:
    """[EXTERNAL FILESYSTEM] Do not use for simple file listing, run bash instead. Find files on disk matching a glob pattern.

    Respects .gitignore files automatically via ripgrep. Sorted by modification time.

    Args:
        pattern: Glob pattern to match (e.g., '**/*.py')
        path: Base directory to search in

    Returns:
        Newline-separated list of matching files
    """
    print(f"{MAGENTA}⏺ Glob({pattern}): {path}{RESET}")

    cmd = ["rg", "--files", "--no-require-git", "-g", pattern, path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        files = sorted(
            files,
            key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
            reverse=True,
        )
        return "\n".join(files) or "no files found"
    except FileNotFoundError:
        return "error: ripgrep (rg) not installed - install with 'brew install ripgrep'"
    except subprocess.TimeoutExpired:
        return "error: search timed out after 30s"


def grep_files(
    pattern: str, path: str = ".", glob: str = None, max_results: int = 50
) -> str:
    """[EXTERNAL FILESYSTEM] Search files on disk for a regex pattern using ripgrep.

    Args:
        pattern: Regular expression pattern to search for
        path: Base directory to search in
        glob: Optional glob pattern to filter files (e.g., '*.py')
        max_results: Maximum number of results to return

    Returns:
        Matching lines in format 'filepath:line_num:content'
    """
    print(f"{MAGENTA}⏺ Grep: {pattern}{RESET}")

    cmd = ["rg", "-n", "--no-heading", "--color=never", f"-m{max_results}"]
    if glob:
        cmd.extend(["-g", glob])
    cmd.extend([pattern, path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()
        return output if output else "no matches found"
    except FileNotFoundError:
        return "error: ripgrep (rg) not installed - install with 'brew install ripgrep'"
    except subprocess.TimeoutExpired:
        return "error: search timed out after 30s"


# --- Shell operations ---


def run_bash(cmd: str) -> str:
    """[EXTERNAL SYSTEM] Run a shell command on the host machine.

    Args:
        cmd: Shell command to execute

    Returns:
        Command output (stdout and stderr combined)
    """
    print(f"{MAGENTA}⏺ Bash: {cmd}{RESET}")

    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    output_lines = []
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\n(timed out after 30s)")
    return "".join(output_lines).strip() or "(empty output)"


class RLMReasoningCallback(BaseCallback):
    def on_module_end(self, call_id, outputs, exception):
        if outputs and hasattr(outputs, "reasoning") and hasattr(outputs, "code"):
            has_backticks = "```" in outputs.code
            print(f"{DIM}⏺ [REASONING STEP]\n{outputs.reasoning}\n{RESET}")
            if has_backticks:
                print(f"{DIM}⏺ [CODE]\n{outputs.code}\n{RESET}")
            else:
                print(f"{DIM}⏺ [CODE]\n```\n{outputs.code}\n```\n{RESET}")


# -- Program ---


class CodingAssistant(dspy.Signature):
    """You are a concise coding assistant.

    CRITICAL - Two execution environments exist:

    1. INTERNAL REPL (sandbox): Standard Python code you write executes in an isolated sandbox. Variables persist between iterations. Use for data processing, string manipulation, logic, loops, etc.

    2. EXTERNAL TOOLS (real system): Functions like read_file(), write_file(), run_bash(), glob_files(), grep_files() execute OUTSIDE the sandbox on the real filesystem and host machine. These have real, persistent side effects.

    When you need to:
    - Process data, do math, manipulate strings, iterate → write Python code directly in the REPL
    - Read/write actual files on disk → call read_file(), write_file(), edit_file()
    - Run shell commands on the host → call run_bash()
    - Search the codebase → call glob_files(), grep_files()

    Do NOT confuse REPL variables with external files. Reading a file into a variable does not mean the variable updates if the file changes - you must call read_file() again."""

    task: str = dspy.InputField(desc="The user's coding task or question")
    answer: str = dspy.OutputField(
        desc="Your response to the user after completing the task"
    )


class RLMCodingConfig(PrecompiledConfig):
    max_iters: int = 50
    lm: str = "openrouter/anthropic/claude-opus-4.5"
    sub_lm: str = "openrouter/qwen/qwen-coder"
    api_base: str = "https://openrouter.ai/api/v1"
    max_tokens: int = 50000
    max_output_chars: int = 100000
    verbose: bool = True
    track_usage: bool = True
    track_trace: bool = False


class RLMCodingProgram(PrecompiledProgram):
    config: RLMCodingConfig

    def ensure_config(self, config):
        """Override to fix Python 3.14 compatibility issue with __annotations__ access."""
        ConfigClass = self.__class__.__annotations__.get("config", PrecompiledConfig)
        if config is None:
            config = ConfigClass()
        elif isinstance(config, dict):
            config = ConfigClass(**config)
        elif type(config) is not ConfigClass:
            raise ValueError(
                f"config must be an instance of {self.__class__.__name__}.config, got {type(config)}"
            )
        return config

    def __init__(self, config: RLMCodingConfig, **kwargs):
        super().__init__(config, **kwargs)

        if config.track_trace:
            project = kwargs.get("project", os.getenv("WANDB_PROJECT"))
            if project is None:
                raise ValueError("project is required when track_trace is True")

            wandb_key = kwargs.get("wandb_key", os.getenv("WANDB_API_KEY"))
            if wandb_key is None:
                raise ValueError("wandb_key is required when track_trace is True")

            os.environ["WANDB_PROJECT"] = project
            os.environ["WANDB_API_KEY"] = wandb_key
            weave.init(project_name=project)

        self.config = config
        self.tools = {
            "read_file": read_file,
            "write_file": write_file,
            "edit_file": edit_file,
            "glob_files": glob_files,
            "grep_files": grep_files,
            "run_bash": run_bash,
        }

        self.lm = dspy.LM(
            model=self.config.lm,
            api_base=self.config.api_base,
            max_tokens=self.config.max_tokens,
            track_usage=self.config.track_usage,
        )
        self.sub_lm = dspy.LM(
            model=self.config.sub_lm,
            api_base=self.config.api_base,
            max_tokens=self.config.max_tokens,
            track_usage=self.config.track_usage,
        )
        self.agent = dspy.RLM(
            CodingAssistant,
            sub_lm=self.sub_lm,
            tools=self.tools,
            max_output_chars=self.config.max_output_chars,
            max_iterations=self.config.max_iters,
            verbose=False,  # We add our own verbose logging
        )
        self.agent.set_lm(self.lm)

        if self.config.verbose:
            self.add_logging_callbacks()

    def add_logging_callbacks(self):
        """Add logging callbacks to the agent."""

        self.agent.generate_action.callbacks.append(RLMReasoningCallback())
        self._patch_llm_tools()

    def _patch_llm_tools(self):
        """Monkey-patch the RLM's _make_llm_tools to add structured verbose logging."""

        orig_factory = (
            self.agent._make_llm_tools
        )  # capture the original bound method directly

        def verbose_factory(max_workers=8):
            tools = orig_factory(
                max_workers=max_workers
            )  # call the original bound method

            orig_q = tools["llm_query"]
            orig_b = tools["llm_query_batched"]

            def wrapped_q(prompt):  # wrap query
                print(
                    f"{DIM}⏺ [LLM QUERY]:\n{prompt[:100]}...{RESET}\n"
                    if len(prompt) > 100
                    else f"{DIM}⏺ [LLM QUERY]:\n{prompt}{RESET}\n"
                )
                res = orig_q(prompt)
                print(
                    f"{DIM}⏺ [LLM QUERY RESULT]:\n{str(res)[:200]}...{RESET}\n"
                    if len(str(res)) > 200
                    else f"{DIM}⏺ [LLM QUERY RESULT]:\n{res}{RESET}\n"
                )
                return res

            def wrapped_b(prompts):  # wrap batched query
                print(f"{DIM}⏺ [LLM QUERY BATCHED]:\n{len(prompts)} prompts{RESET}\n")
                res = orig_b(prompts)
                print(f"{DIM}⏺ [LLM QUERY BATCHED]:\n{len(res)} results{RESET}\n")
                return res

            tools["llm_query"] = wrapped_q
            tools["llm_query_batched"] = wrapped_b
            return tools

        self.agent._make_llm_tools = verbose_factory

    def forward(self, task: str) -> str:
        """Forward pass for the agent."""
        if not task:
            return dspy.Prediction(answer="No Task Given.")

        return self.agent(task=task)

    def get_tools(self):
        """Get the tools for the agent."""
        return self.tools

    def set_tool(self, name: str, tool: callable):
        """Set a tool for the agent."""
        self.tools[name] = tool
        self.reload_repl()

    def remove_tool(self, name: str):
        """Remove a tool from the agent."""
        if name in self.tools:
            del self.tools[name]
            self.reload_repl()

    def reload_repl(
        self,
    ):  # We need to create a new instance for tool mutations to be passed back into the REPL
        """Reload the REPL with the current tools."""

        new_instance = dspy.RLM(
            CodingAssistant,
            sub_lm=self.sub_lm,
            tools=self.tools,
            max_output_chars=self.config.max_output_chars,
            max_iterations=self.config.max_iters,
            verbose=False,  # We add our own verbose logging
        )
        new_instance.set_lm(self.lm)
        self.agent = new_instance
        if self.config.verbose:
            self.add_logging_callbacks()

    def reload_lms(self):
        """Recreate LM objects from current config. Call this after changing config.lm or config.sub_lm."""

        self.lm = dspy.LM(
            model=self.config.lm,
            api_base=self.config.api_base,
            max_tokens=self.config.max_tokens,
            track_usage=self.config.track_usage,
        )
        self.sub_lm = dspy.LM(
            model=self.config.sub_lm,
            api_base=self.config.api_base,
            max_tokens=self.config.max_tokens,
            track_usage=self.config.track_usage,
        )
        self.reload_repl()
        if os.getenv("MODAIC_ENV") == "dev":
            print(f"{BLUE}LMs RELOADED: {self.lm.model}, {self.sub_lm.model}{RESET}")

    def load_state(self, state):
        """Override to recreate LMs from config after loading state.

        PrecompiledProgram.from_precompiled() calls load_state() AFTER __init__,
        which overwrites our LMs with saved state. We fix this by recreating
        the LMs from self.config after the parent load_state runs. Modaic will
        fix this in a later patch for future devs.
        """
        super().load_state(state)
        self.reload_lms()  # Recreate LMs from config (not from saved state)


if __name__ == "__main__":
    agent = RLMCodingProgram(RLMCodingConfig())

    # agent(task="what's 1 + 1?")

    branches = ["prod"]
    for branch in branches:
        agent.push_to_hub(
            MODAIC_REPO_PATH,
            commit_message="run reflection",
            branch=branch,
        )
