#!/bin/bash

# Find jobs whose tasks have completed with failed tests (return code 0)
# Usage: ./find_completed_jobs.sh [output_file]

OUTPUT_FILE="${1:-completed_jobs.txt}"
JOBS_DIR="jobs"
FAILED_DIR="failed-jobs"

# Clear output file
> "$OUTPUT_FILE"

echo "Scanning for completed tasks with failed tests (return code 0)..."
echo "Results will be written to: $OUTPUT_FILE"
echo ""
echo "Failed test outputs will be copied into: $FAILED_DIR/"

completed=0
incomplete=0
total=0

# Iterate through job date directories
for job_dir in "$JOBS_DIR"/*/; do
    [ -d "$job_dir" ] || continue
    job_name=$(basename "$job_dir")

    # Iterate through task directories
    for task_dir in "$job_dir"*/; do
        [ -d "$task_dir" ] || continue
        task_name=$(basename "$task_dir")
        return_code_file="$task_dir/verifier/reward.txt"
        test_stdout_file="$task_dir/verifier/test-stdout.txt"
        trajectory_file="$task_dir/agent/command-0/stdout.txt"

        ((total++))

        if [ -f "$return_code_file" ]; then
            code=$(cat "$return_code_file" | tr -d '[:space:]')
            if [ "$code" = "0" ]; then
                ((completed++))
                echo "jobs/$job_name/$task_name: return_code=$code" >> "$OUTPUT_FILE"
                # Copy failed test artifacts for quick inspection (only if trajectory exists)
                if [ -f "$trajectory_file" ]; then
                    failed_task_dir="$FAILED_DIR/$job_name/$task_name"
                    mkdir -p "$failed_task_dir"
                    cp "$trajectory_file" "$failed_task_dir/trajectory.txt"
                    if [ -f "$test_stdout_file" ]; then
                        cp "$test_stdout_file" "$failed_task_dir/test-case-result.txt"
                    fi
                fi
            else
                ((incomplete++))
            fi
        else
            ((incomplete++))
        fi
    done
done

# Summary (completed == return code 0 / failed tests)
echo "----------------------------------------" >> "$OUTPUT_FILE"
echo "Summary: $completed completed, $incomplete incomplete, $total total" >> "$OUTPUT_FILE"

echo "Done!"
echo "Completed (return code 0 / failed tests): $completed"
echo "Incomplete: $incomplete"
echo "Total: $total"
