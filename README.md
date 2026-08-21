# PromptResponse: Optimizing Prompts for LLM Coding Tasks
How do _LLM tuning_ and _prompt formatting_ influence the _task performance_, _efficiency_, and _prompt stability_ in HumanEval-style coding tasks?



## Datasets
This repository includes five variants of the [_HumanEval_ dataset](https://arxiv.org/abs/2107.03374) under ``datasets/HumanEval/``:

| Variant/Format | Description                                                  	| Path                       	|
|----------------|--------------------------------------------------------------	|----------------------------	|
| _Baseline_     | The original HumanEval dataset from [HuggingFace](https://huggingface.co/datasets/openai/openai_humaneval), accessed on July 12, 2025.     	| ``vanilla/``          	|
| _JSON_    	 | Parsed into [JSON format](https://en.wikipedia.org/wiki/JSON) using the provided ``HumanEval_Reformatter.py`` script.     	| ``json/``          	|
| _Markdown_   	 | Parsed into [Markdown format](https://en.wikipedia.org/wiki/Markdown) using the provided ``HumanEval_Reformatter.py`` script.       	| ``markdown/``          	|
| _YAML_    	 | Parsed into [YAML format](https://en.wikipedia.org/wiki/YAML) using the provided ``HumanEval_Reformatter.py`` script.       	| ``yaml/``          	|
| _LLM-tuned_    | With docstrings altered by Mistral AI's _Mistral-7B-Instruct-v0.2_ model using the provided ``LLM-tuned_Dataset_Creation.ipynb`` notebook.       	| ``tuned/``          	|



## Experimental Procedure
The controlled experiment itself is documented in ``Request_and_Evaluate_OpenAI.ipynb`` and can be rerun from there. It includes the following steps:
1. Load all five versions of the _HumanEval_ benchmark described above.
2. Have OpenAI's _gpt-4o-2024-08-06_ implement all 164 problems of all 5 datasets 10 times each (8200 executions in total).
3. Run the test cases on all implemented code fragments.

During steps 2 and 3, the dependent variables <span style="font-variant: small-caps;">PassRate</span>, <span style="font-variant: small-caps;">GenDuration</span>, <span style="font-variant: small-caps;">EvalDuration</span>, <span style="font-variant: small-caps;">PassDuration</span>, <span style="font-variant: small-caps;">ResponseLen</span>, and <span style="font-variant: small-caps;">Rouge-L</span> are being measured/calculated.