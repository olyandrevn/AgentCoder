import argparse
import os
import json
from tqdm import tqdm
import copy
import openai
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from process_mx_agent3_generation import preprocess_data

# Setting API parameters
openai.api_base = "https://api.aiohub.org/v1"
openai.api_key = 'API'



# Function to fetch completion
def fetch_completion(data_entry, model,lg):
    prompt = data_entry["prompt"]
    text = f"""
**Role**: You are a software programmer.

**Task**: As a programmer, you are required to complete the function. Use a Chain-of-Thought approach to break down the problem, create pseudocode, and then write the code in Python language. Ensure that your code is efficient, readable, and well-commented.

For example:

**Input Code Snippet**:
```python
{prompt}
```

**Instructions**:
1. **Understand and Clarify**: Make sure you understand the task. 
2. **Algorithm/Method Selection**: Decide on the most efficient way.
3. **Pseudocode Creation**: Write down the steps you will follow in pseudocode. 
4. **Code Generation**: Translate your pseudocode into executable Python code. 
"""
    try:
        completions = openai.ChatCompletion.create(
            model=model,
            stream=False,
            messages=[
        {"role": "system", "content": "You are a software programmer."},
        {"role": "user", "content":text},
            ],
            request_timeout=100,
        )
        data_entry["completion"] = completions.choices[0]["message"]["content"]
        data_entry = preprocess_data(data_entry,lg)
        return data_entry
    except Exception as e:
        print(e)
        data_entry["completion"] = ""
        return data_entry

def fix_bug(data_entry, model,lg,preprocess_data = preprocess_data):
    if data_entry["passed"] == True:
        return data_entry
    else:
        gpt_prompt = (
            "Please re-completion the code to fix the error message. "+
            f"\nHere is the previous version:\n```{lg}\n" + 
            data_entry['completion'] + f"\n```\nWhen we use this test cases: ```{lg}\n"+data_entry["test_case"]+f"\n``` to evaluate the code. It raise the error:\n```{lg}\n" + data_entry["result"] +
            f"\n```\nPlease fix the bug by follow the error information and only return {lg} code. You do not need return the test cases" + 
            f"The re-completion code should in triple backticks format(i.e., in ```{lg} ```)."
        )
        try:
            completions = openai.ChatCompletion.create(
                model=model,
                stream=False,
                messages=[
            {"role": "system", "content": "You are a code developer assistant."},
            {"role": "user", "content":gpt_prompt},
                ],
                request_timeout=100,
            )
            data_entry["completion"] = completions.choices[0]["message"]["content"]
            data_entry = preprocess_data(data_entry,lg)
        except Exception as e:
            print(repr(e))
    return data_entry

def call_fix_bug(dataset, model,lg):
    print("Fixing bug...")
    with ThreadPoolExecutor() as executor:
        future_to_entry = {executor.submit(fix_bug, copy.deepcopy(entry), model, lg): entry for entry in tqdm(dataset)}
        for future in tqdm(concurrent.futures.as_completed(future_to_entry)):
            entry = future_to_entry[future]
            try:
                updated_entry = future.result()
                idx = dataset.index(entry)
                dataset[idx] = updated_entry
            except Exception as e:
                print(repr(e))
    return dataset

if __name__ == "__main__":
    model_list = ["gpt-3.5-turbo"]
    language = ["python"]
    for model in model_list:
        for lg in language:
            from datasets import load_dataset
            dataset = load_dataset("openai_humaneval",split="test")
            dataset = [entry for entry in dataset]
            with ThreadPoolExecutor() as executor:
                future_to_entry = {executor.submit(fetch_completion, copy.deepcopy(entry), model, lg): entry for entry in tqdm(dataset)}
                for future in tqdm(concurrent.futures.as_completed(future_to_entry)):
                    entry = future_to_entry[future]
                    try:
                        updated_entry = future.result()
                        idx = dataset.index(entry)
                        dataset[idx] = updated_entry
                    except Exception as e:
                        print(repr(e))
            with open(f"./dataset/{model}_{lg}.json", "w") as f:
                json.dump(dataset, f, indent=4)