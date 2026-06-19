# Changes to codebase

## Model choice 
1. Shortcuts: allow for GEMMA4, QWEN35 and QWEN36 shortcuts as cli options that map to the actual models. Check out the correct model names with `ollama list` terminal command. 
2. Anthropic tunneling: implement optional tunneling of the model invocations to a claude code pro cli client. 

## Refactor
1. Re-organize ris_agent codebase: 
1.1. Separate the agent loop (`_run()` function in cli.py) from the app initialisation/arg parse code in `main()` function, same file. 
1.2. New agentic workflow (separate prompt)

## loop
Is there a special reason that the agent.stream() invocation is not passing version="v2" as parameter? If not, change code to latest version. 

## Logger 
logging of agent output: separate prompt

