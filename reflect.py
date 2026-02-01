#!/usr/bin/env python3
"""
Continuous monitoring script for failed benchmark jobs with self-improving feedback loop.

This script:
1. Continuously monitors jobs/{job_id}/{task_id} for failed jobs (reward.txt == 0)
2. Tracks test-case-result + trajectory for failed jobs
3. Copies artifacts to failed-jobs/{job_id}/{task_id}/
4. Runs microcode locally to analyze failures and generate FEEDBACK.md
5. Uses microcode to iterate on the CodingAssistant signature based on feedback
6. Pushes the updated nanocode to hub for automatic propagation
"""

import asyncio
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Set

# Configuration
JOBS_DIR = Path("jobs")
FAILED_DIR = Path("failed-jobs")
POLL_INTERVAL = 10  # seconds between scans
PROCESSED_FILE = Path(".processed_failed_jobs.json")


@dataclass
class FailedTask:
    """Represents a failed task with its artifacts."""

    job_id: str
    task_id: str
    job_path: Path
    trajectory_path: Path
    test_result_path: Path | None
    reward: int


def load_processed_jobs() -> Set[str]:
    """Load the set of already processed job IDs."""
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE) as f:
            data = json.load(f)
            return set(data.get("processed_jobs", []))
    return set()


def save_processed_jobs(processed: Set[str]) -> None:
    """Save the set of processed job IDs."""
    with open(PROCESSED_FILE, "w") as f:
        json.dump({"processed_jobs": list(processed)}, f, indent=2)


def find_failed_tasks() -> list[FailedTask]:
    """Scan jobs directory for failed tasks (reward.txt == 0)."""
    failed_tasks = []

    if not JOBS_DIR.exists():
        return failed_tasks

    for job_dir in JOBS_DIR.iterdir():
        if not job_dir.is_dir():
            continue

        job_id = job_dir.name

        for task_dir in job_dir.iterdir():
            if not task_dir.is_dir():
                continue

            task_id = task_dir.name
            reward_file = task_dir / "verifier" / "reward.txt"
            trajectory_file = task_dir / "agent" / "command-0" / "stdout.txt"
            test_stdout_file = task_dir / "verifier" / "test-stdout.txt"

            if not reward_file.exists():
                continue

            try:
                reward = int(reward_file.read_text().strip())
            except (ValueError, IOError):
                continue

            # reward == 0 means failed tests
            if reward == 0 and trajectory_file.exists():
                failed_tasks.append(
                    FailedTask(
                        job_id=job_id,
                        task_id=task_id,
                        job_path=task_dir,
                        trajectory_path=trajectory_file,
                        test_result_path=test_stdout_file
                        if test_stdout_file.exists()
                        else None,
                        reward=reward,
                    )
                )

    return failed_tasks


def copy_failed_artifacts(tasks: list[FailedTask]) -> dict[str, list[str]]:
    """Copy failed task artifacts to failed-jobs directory.

    Returns a dict mapping job_id to list of task_ids that were copied.
    """
    jobs_with_new_failures: dict[str, list[str]] = {}

    for task in tasks:
        failed_task_dir = FAILED_DIR / task.job_id / task.task_id
        failed_task_dir.mkdir(parents=True, exist_ok=True)

        # Copy trajectory
        dest_trajectory = failed_task_dir / "trajectory.txt"
        if not dest_trajectory.exists():
            shutil.copy(task.trajectory_path, dest_trajectory)

            if task.job_id not in jobs_with_new_failures:
                jobs_with_new_failures[task.job_id] = []
            jobs_with_new_failures[task.job_id].append(task.task_id)

        # Copy test results if available
        if task.test_result_path:
            dest_test = failed_task_dir / "test-case-result.txt"
            if not dest_test.exists():
                shutil.copy(task.test_result_path, dest_test)

    return jobs_with_new_failures


def run_reflection_analysis(job_id: str) -> str:
    """Run reflection analysis locally using microcode."""
    failed_job_dir = FAILED_DIR / job_id
    feedback_path = failed_job_dir / "FEEDBACK.md"

    prompt = f"""Explore the trajectories in the directory failed-jobs/{job_id}. Each task within this directory contains the test results of that task and the agent's trajectories. In one file, FEEDBACK.md, formulate comprehensive feedback and common failure modes that the agent runs into."""

    api_key = os.environ.get("OPENROUTER_API_KEY", "")

    cmd = [
        "microcode",
        "task",
        prompt,
        "--lm",
        "openai/gpt-5.2",
        "--sub-lm",
        "qwen/qwen3-coder",
        "--max-iterations",
        "30",
        "--max-tokens",
        "30000",
        "--verbose",
    ]

    if api_key:
        cmd.extend(["--api-key", api_key])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1500,
        )

        print(f"Microcode stdout:\n{result.stdout}")
        if result.stderr:
            print(f"Microcode stderr:\n{result.stderr}")

    except subprocess.TimeoutExpired:
        print("Microcode timed out")
    except Exception as e:
        print(f"Error running microcode: {e}")

    if feedback_path.exists():
        return feedback_path.read_text()

    return ""


def run_signature_iteration(feedback_path: Path) -> bool:
    """Run microcode to iterate on the CodingAssistant signature based on feedback.

    Returns True if the signature was successfully updated.
    """
    signature_file = Path("nanocode/nanocode.py")

    if not signature_file.exists():
        print(f"Error: {signature_file} not found")
        return False

    prompt = f"""Read the feedback in {feedback_path} which contains analysis of failed agent trajectories and common failure modes.

Then read the CodingAssistant signature in nanocode/nanocode.py. This is a dspy.Signature class that defines the agent's behavior.

Based on the feedback, iterate on the CodingAssistant signature to help the agent avoid these failure modes. You can update:
1. The class docstring (the main system prompt)
2. The task field description
3. The answer field description

Make targeted improvements based on the specific failure patterns identified. Do NOT change the class name, field names, or the overall structure - only update the docstrings/descriptions.

After making your changes, confirm what you updated."""

    api_key = os.environ.get("OPENROUTER_API_KEY", "")

    cmd = [
        "microcode",
        "task",
        prompt,
        "--lm",
        "openai/gpt-5.2",
        "--sub-lm",
        "qwen/qwen3-coder",
        "--max-iterations",
        "30",
        "--max-tokens",
        "30000",
        "--verbose",
    ]

    if api_key:
        cmd.extend(["--api-key", api_key])

    try:
        print(f"\n>>> Running signature iteration based on {feedback_path}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1500,
        )

        print(f"Signature iteration stdout:\n{result.stdout}")
        if result.stderr:
            print(f"Signature iteration stderr:\n{result.stderr}")

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print("Signature iteration timed out")
        return False
    except Exception as e:
        print(f"Error running signature iteration: {e}")
        return False


def push_nanocode_to_hub() -> bool:
    """Push the updated nanocode to hub.

    Returns True if push was successful.
    """
    try:
        print("\n>>> Pushing updated nanocode to hub")
        result = subprocess.run(
            ["uv", "run", "nanocode.py"],
            cwd="nanocode",
            capture_output=True,
            text=True,
            timeout=300,
        )

        print(f"Push stdout:\n{result.stdout}")
        if result.stderr:
            print(f"Push stderr:\n{result.stderr}")

        if result.returncode == 0:
            print("✓ Successfully pushed nanocode to hub")
            return True
        else:
            print(f"✗ Push failed with return code {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        print("Push timed out")
        return False
    except Exception as e:
        print(f"Error pushing to hub: {e}")
        return False


def print_status(failed_tasks: list[FailedTask], processed_jobs: Set[str]) -> None:
    """Print current status."""
    jobs_summary: dict[str, int] = {}
    for task in failed_tasks:
        jobs_summary[task.job_id] = jobs_summary.get(task.job_id, 0) + 1

    print("\n" + "=" * 60)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Status Update")
    print("=" * 60)
    print(f"Total failed tasks found: {len(failed_tasks)}")
    print(f"Jobs with failures: {len(jobs_summary)}")
    print(f"Already processed jobs: {len(processed_jobs)}")

    for job_id, count in sorted(jobs_summary.items()):
        status = "✓ processed" if job_id in processed_jobs else "⏳ pending"
        print(f"  {job_id}: {count} failed tasks [{status}]")
    print("=" * 60 + "\n")


async def monitor_loop(one_shot: bool = False) -> None:
    """Main monitoring loop."""
    processed_jobs = load_processed_jobs()
    last_analyzed_count: dict[str, int] = {}  # Track last count when we ran analysis

    print("Starting reflection monitor")
    print(f"Watching: {JOBS_DIR.absolute()}")
    print(f"Output: {FAILED_DIR.absolute()}")
    print(f"Poll interval: {POLL_INTERVAL}s")
    print("Analysis triggers every 10 failed tasks per job")
    print()

    while True:
        try:
            # Find all failed tasks
            failed_tasks = find_failed_tasks()

            if failed_tasks:
                # Copy artifacts
                copy_failed_artifacts(failed_tasks)

                # Print status
                print_status(failed_tasks, processed_jobs)

                # Group failed tasks by job_id
                tasks_by_job: dict[str, int] = {}
                for task in failed_tasks:
                    tasks_by_job[task.job_id] = tasks_by_job.get(task.job_id, 0) + 1

                # Run reflection analysis when failed count is a multiple of 10
                for job_id, count in tasks_by_job.items():
                    last_count = last_analyzed_count.get(job_id, 0)
                    # Check if we've crossed a new multiple of 10
                    if count >= 10 and (count // 10) > (last_count // 10):
                        print(
                            f"\n>>> Running reflection analysis for job: {job_id} (failed count: {count})"
                        )

                        try:
                            feedback = run_reflection_analysis(job_id)

                            if feedback:
                                print(f"✓ Generated FEEDBACK.md for {job_id}")
                                last_analyzed_count[job_id] = count

                                # Run signature iteration based on feedback
                                feedback_path = FAILED_DIR / job_id / "FEEDBACK.md"
                                if run_signature_iteration(feedback_path):
                                    print(f"✓ Updated CodingAssistant signature for {job_id}")
                                    # Push updated nanocode to hub
                                    if push_nanocode_to_hub():
                                        print(f"✓ Pushed new revision to hub for {job_id}")
                                    else:
                                        print(f"✗ Failed to push to hub for {job_id}")
                                else:
                                    print(f"✗ Failed to update signature for {job_id}")
                            else:
                                print(f"✗ No feedback generated for {job_id}")

                        except Exception as e:
                            print(f"✗ Error processing {job_id}: {e}")
                    elif count < 10:
                        print(f"[{job_id}] {count} failed tasks (waiting for 10)")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] No failed tasks found")

            if one_shot:
                break

            await asyncio.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopping monitor...")
            break
        except Exception as e:
            print(f"Error in monitor loop: {e}")
            if one_shot:
                break
            await asyncio.sleep(POLL_INTERVAL)


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Monitor and analyze failed benchmark jobs"
    )
    parser.add_argument(
        "--one-shot",
        action="store_true",
        help="Run once and exit instead of continuous monitoring",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds between scans (default: 10)",
    )
    parser.add_argument(
        "--reset-processed",
        action="store_true",
        help="Reset the list of processed jobs",
    )

    args = parser.parse_args()

    global POLL_INTERVAL
    POLL_INTERVAL = args.poll_interval

    if args.reset_processed and PROCESSED_FILE.exists():
        PROCESSED_FILE.unlink()
        print("Reset processed jobs list")

    asyncio.run(monitor_loop(one_shot=args.one_shot))


if __name__ == "__main__":
    main()
