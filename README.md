Run Instructions

1. Set your OpenRouter API key:
```bash
export OPENROUTER_API_KEY="your-key-here"
```

2. Run Harbor with the microcode agent:
```bash
harbor run -d "aider-polyglot@1.0" \
--agent-import-path agent:MicrocodeInstalledAgent
```

**Tip** Run parallel containers in a cloud environment (I use Modal)
```bash
harbor run -d "aider-polyglot@1.0" \
--agent-import-path agent:MicrocodeInstalledAgent \
--env "modal" \
--n-concurrent 5
```

The agent is configured with:
- Model: openai/gpt-5.2
- Sub-model: openai/gpt-5.2
- Max iterations: 50
- Max tokens: 50,000
- Timeout: 600 seconds

To customize these defaults, you can modify the __init__ parameters in agent.py or extend the class.

