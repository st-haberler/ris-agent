# Logging the agent output

Right now the agent/model output is written to console with the --verbose flag being the only option. 

Goal: simple html/css/js/ts dashboard that shows - more like a report than a log. 

- model name
- time and date of the run
- input prompt ('frage')
- system prompt with toggle to show/hide 
- for each step: display of the full input/context/prompt for that step/model invocation with toggle to show/hide
- a console like timeline that primarily displays the update events with option toggles to show/hide the output in full detail. 
- additional info (with show/hide toggle):
    - number of tokens for each step (estimated or as provided by model)
    - duration for each step and the entire agent request 

I think for now, stand-alone html file with inline css and js should work fine. That would make persisting the reports easier. I would open them with a standard web browser. I think starting a full dashboard web app would be overkill rn. 

IMPORTANT CONSIDERATION: i will change the architecture of the agentic loop, the skill and tool systems a lot, include sub-agents later etc. The logging/report module must easily adapt to such changes. 


