import argparse
import os
import json
from tqdm.auto import tqdm
import copy
import openai
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import time
from datasets import load_dataset
from dotenv import load_dotenv
import os

load_dotenv()  # Loads variables from .env file into environment

# Setting API parameters
# openai.api_base = "https://api.aiohub.org/v1"
openai.api_key = os.getenv("OPENAI_API_KEY")

dataset = load_dataset("openai_humaneval", split="test")
dataset = [entry for entry in dataset]

prompt_path = "../prompts/humaneval_prompt_update.txt"
with open(prompt_path, "r") as f:
    construct_few_shot_prompt = f.read()


def preprocess_data(completion_string):
    if f"```python" in completion_string:
        completion_string = completion_string[completion_string.find(f"```python")+len(f"```python"):]
        completion_string = completion_string[:completion_string.find("```")]
    else:
        # print(completion_string)
        print("Error: No code block found")
    return completion_string


# Function to fetch completion
def fetch_completion(data_entry, model, lg, times=5):
    global construct_few_shot_prompt
    if "need_reproduce" in data_entry.keys() and data_entry["need_reproduce"]==False:
        return data_entry
    prompt = data_entry["prompt"]
    text = f"""
{construct_few_shot_prompt}

**Input Code Snippet**:
```python
{prompt}
```
## Completion 3:
"""
    try:
        with open(f"../dataset/generated_tests_{data_entry.get('task_id', 'unknown')}.json", "r") as f:
            generated_tests = json.load(f)
            # Add tests to the prompt
            test_cases = "\nYour code should pass these additional tests:\n```python"
            for test in generated_tests["test_case_list"]:
                test_cases += "\n" + test
            test_cases += "\n```"
            text += test_cases
            text += "\nTest Analysis:\n" + generated_tests["test_feedback"]
    except FileNotFoundError:
        pass
    completions_code = []
    for i in range(times):
        while True:
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
                completion = completions.choices[0]["message"]["content"]
                # print(completion)
                completion = preprocess_data(completion)

            except Exception as e:
                print(e)
                time.sleep(10)
                completion = ""
            if completion!="":
                break
        completions_code.append(completion)
    data_entry["completion_list"] = completions_code
    return data_entry


def call_fetch_completion_helper(dataset, model, lg):
    print("Fixing bug...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_entry = {executor.submit(fetch_completion, copy.deepcopy(entry), model, lg): entry for entry in tqdm(dataset)}
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
    model_list = ["gpt-3.5-turbo-1106"]
    language = ["python"]
    for model in model_list:
        for lg in language:
            from datasets import load_dataset
            dataset = load_dataset("openai_humaneval",split="test")
            dataset = [entry for entry in dataset]
            dataset = dataset[:10]
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_entry = {executor.submit(fetch_completion, copy.deepcopy(entry), model, lg): entry for entry in tqdm(dataset)}
                for future in tqdm(concurrent.futures.as_completed(future_to_entry), total=len(future_to_entry)):
                    entry = future_to_entry[future]
                    try:
                        updated_entry = future.result()
                        idx = dataset.index(entry)
                        dataset[idx] = updated_entry
                    except Exception as e:
                        print(repr(e))
            with open(f"../dataset/{model}_{lg}.json", "w") as f:
                json.dump(dataset, f, indent=4)


# import argparse
# import os
# import json
# from tqdm.auto import tqdm
# import copy
# import openai
# from concurrent.futures import ThreadPoolExecutor
# import concurrent.futures
# import time
# from datasets import load_dataset
# from dotenv import load_dotenv
# import os

# load_dotenv()  # Loads variables from .env file into environment

# # Setting API parameters
# # openai.api_base = "https://api.aiohub.org/v1"
# openai.api_key = os.getenv("OPENAI_API_KEY")

# def preprocess_data(data,lg):
#     if f"```{lg}" in data["completion"]:
#         data["completion"] = data["completion"][data["completion"].find(f"```{lg}")+len(f"```{lg}"):]
#         data["completion"] = data["completion"][:data["completion"].find("```")]
#     else:
#         print(data["task_id"])
#     return data

# # Function to fetch completion
# def fetch_completion(data_entry, model,lg):
#     prompt = data_entry["prompt"]
#     text = f"""
# **Role**: You are a software programmer.

# **Task**: As a programmer, you are required to complete the function. Use a Chain-of-Thought approach to break down the problem, create pseudocode, and then write the code in Python language. Ensure that your code is efficient, readable, and well-commented.

# **Input Code Snippet**:
# ```python
# {prompt}
# ```

# **Instructions**:
# 1. **Understand and Clarify**: Make sure you understand the task. 
# 2. **Algorithm/Method Selection**: Decide on the most efficient way.
# 3. **Pseudocode Creation**: Write down the steps you will follow in pseudocode. 
# 4. **Code Generation**: Translate your pseudocode into executable Python code. 
# """
#     try:
#         completions = openai.ChatCompletion.create(
#             model=model,
#             stream=False,
#             messages=[
#         {"role": "system", "content": "You are a software programmer."},
#         {"role": "user", "content":text},
#             ],
#             request_timeout=100,
#         )
#         data_entry["completion"] = completions.choices[0]["message"]["content"]
#         data_entry = preprocess_data(data_entry,lg)
#         return data_entry
#     except Exception as e:
#         print(e)
#         data_entry["completion"] = ""
#         return data_entry

# def fix_bug(data_entry, model,lg,preprocess_data = preprocess_data):
#     if data_entry["passed"] == True:
#         return data_entry
#     else:
#         gpt_prompt = (
#             "Please re-completion the code to fix the error message. "+
#             f"\nHere is the previous version:\n```{lg}\n" + 
#             data_entry['completion'] + f"\n```\nWhen we use this test cases: ```{lg}\n"+data_entry["test_case"]+f"\n``` to evaluate the code. It raise the error:\n```{lg}\n" + data_entry["result"] +
#             f"\n```\nPlease fix the bug by follow the error information and only return {lg} code. You do not need return the test cases" + 
#             f"The re-completion code should in triple backticks format(i.e., in ```{lg} ```)."
#         )
#         try:
#             completions = openai.ChatCompletion.create(
#                 model=model,
#                 stream=False,
#                 messages=[
#             {"role": "system", "content": "You are a code developer assistant."},
#             {"role": "user", "content":gpt_prompt},
#                 ],
#                 request_timeout=100,
#             )
#             data_entry["completion"] = completions.choices[0]["message"]["content"]
#             data_entry = preprocess_data(data_entry,lg)
#         except Exception as e:
#             print(repr(e))
#     return data_entry

# def call_fix_bug(dataset, model,lg):
#     print("Fixing bug...")
#     with ThreadPoolExecutor() as executor:
#         future_to_entry = {executor.submit(fix_bug, copy.deepcopy(entry), model, lg): entry for entry in tqdm(dataset)}
#         for future in tqdm(concurrent.futures.as_completed(future_to_entry)):
#             entry = future_to_entry[future]
#             try:
#                 updated_entry = future.result()
#                 idx = dataset.index(entry)
#                 dataset[idx] = updated_entry
#             except Exception as e:
#                 print(repr(e))
#     return dataset

# if __name__ == "__main__":
#     model_list = ["gpt-3.5-turbo"]
#     language = ["python"]
#     for model in model_list:
#         for lg in language:
#             from datasets import load_dataset
#             dataset = load_dataset("openai_humaneval",split="test")
#             dataset = [entry for entry in dataset]
#             with ThreadPoolExecutor() as executor:
#                 future_to_entry = {executor.submit(fetch_completion, copy.deepcopy(entry), model, lg): entry for entry in tqdm(dataset)}
#                 for future in tqdm(concurrent.futures.as_completed(future_to_entry)):
#                     entry = future_to_entry[future]
#                     try:
#                         updated_entry = future.result()
#                         idx = dataset.index(entry)
#                         dataset[idx] = updated_entry
#                     except Exception as e:
#                         print(repr(e))
#             with open(f"../dataset/{model}_{lg}.json", "w") as f:
#                 json.dump(dataset, f, indent=4)