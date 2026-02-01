"""Harbor installed agent for microcode CLI."""

import os
import shlex
from pathlib import Path

from pydantic import BaseModel
from harbor.agents.installed.base import BaseInstalledAgent
from harbor import AgentContext


class ExecInput(BaseModel):
    command: str
    cwd: str | None = None
    env: dict[str, str] | None = None
    timeout_sec: int | None = None


class MicrocodeInstalledAgent(BaseInstalledAgent):
    """
    Harbor installed agent wrapper for the microcode CLI tool.

    Microcode is an AI coding agent that runs via OpenRouter.
    It must be installed via `uv tool install microcode` and requires Deno.
    """

    def __init__(
        self,
        lm: str = "anthropic/claude-opus-4.5",
        sub_lm: str = "qwen/qwen3-coder",
        max_iterations: int = 50,
        max_tokens: int = 50000,
        timeout_sec: int = 1200,
        verbose: bool = True,
        api_key: str | None = None,  # openrouter key
        track_trace: bool = True,
        wandb_project: str | None = None,
        wandb_key: str | None = None,
        env: str | None = "dev",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.lm = lm
        self.sub_lm = sub_lm
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.timeout_sec = timeout_sec
        self.verbose = verbose
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.wandb_project = wandb_project or os.getenv("WANDB_PROJECT", "")
        self.wandb_key = wandb_key or os.getenv("WANDB_API_KEY", "")
        self.env = env
        self.track_trace = track_trace

    @staticmethod
    def name() -> str:
        return "microcode"

    def version(self) -> str | None:
        return "0.2.1"

    @property
    def _install_agent_template_path(self) -> Path:
        """Path to the jinja template script for installing the agent in the container."""
        return Path(__file__).parent / "templates" / "install_microcode.sh.j2"

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """
        Create the commands to run microcode in headless/non-interactive mode.

        Uses `microcode task "<instruction>"` which runs once and exits.
        """
        args = [
            "microcode",
            "task",
            instruction,
            "--lm",
            self.lm,
            "--sub-lm",
            self.sub_lm,
            "--max-iterations",
            str(self.max_iterations),
            "--max-tokens",
            str(self.max_tokens),
        ]
        if self.api_key:
            args.extend(["--api-key", self.api_key])
        if self.verbose:
            args.append("--verbose")
        if getattr(self, "track_trace", False):
            args.append("--track-trace")
        if self.wandb_project:
            args.extend(["--wandb-project", self.wandb_project])
        if self.wandb_key:
            args.extend(["--wandb-key", self.wandb_key])
        if self.env:
            args.extend(["--env", self.env])

        command = " ".join(shlex.quote(arg) for arg in args)

        env = {}
        openrouter_key = os.getenv(
            "OPENROUTER_API_KEY",
        )
        wandb_key = os.getenv(
            "WANDB_API_KEY",
        )
        wandb_project = os.getenv(
            "WANDB_PROJECT",
        )
        if openrouter_key:
            env["OPENROUTER_API_KEY"] = openrouter_key
        if wandb_key:
            env["WANDB_API_KEY"] = wandb_key
        if wandb_project:
            env["WANDB_PROJECT"] = wandb_project

        return [
            ExecInput(
                command=command,
                env=env if env else None,
                timeout_sec=self.timeout_sec,
            )
        ]

    def populate_context_post_run(self, context: AgentContext) -> None:
        """
        Populate the context with the results of the agent execution. Assumes the run()
        method has already been called. Typically involves parsing a trajectory file.
        """
