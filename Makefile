run-parallel:
	echo "Starting benchmark..."
	harbor run -d "terminal-bench@2.0" --agent-import-path agent:MicrocodeInstalledAgent --env "modal" --n-concurrent 89

run:
	harbor run -d "terminal-bench@2.0" --agent-import-path agent:MicrocodeInstalledAgent

sample:
	harbor run -d "terminal-bench@2.0" --agent-import-path agent:MicrocodeInstalledAgent --env "modal" --n-concurrent 1

clear-jobs:
	rm -rf jobs/*

ls-cj:
	./find_completed_jobs.sh
