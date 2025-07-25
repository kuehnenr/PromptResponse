import os
from datasets import load_dataset, load_from_disk, Dataset
import re
import copy
import json, yaml

import sys
sys.stdout.reconfigure(encoding='utf-8') # So piping cmd output doesn't crash upon '➞'

if os.path.exists("./datasets/HumanEval/vanilla") == False:
    # Load the dataset (HumanEval only contains "test")
    dataset = load_dataset("openai_humaneval", split="test")
    # Save to disk
    dataset.save_to_disk("./datasets/HumanEval/vanilla")

    print("Downloaded & saved the 'HumanEval' dataset!")
else:
    dataset = load_from_disk("./datasets/HumanEval/vanilla")
    print("Reloaded the local copy of the 'HumanEval' dataset!")

print(dataset)

#print(dataset[0])
#print(dataset[:5]['prompt'])

def extract_note(lines: str, i : int):
    note = ""
    if not i >= len(lines) and "Note" in lines[i]:
        linebroken = True
        listed = False
        while True:
            i += 1
            line = lines[i].strip()
            if i >= len(lines) or line == "\"\"\"" or line == "\'\'\'":
                break

            if linebroken:
                note += line
                linebroken = False
            elif line == "":
                note += "\n\n"
                linebroken = True
            else:
                if lines[i][4] in ['\'', ' ', '-']: # cf. various listicals (107, 120)
                    note += "\n" + line
                    listed = True
                elif listed:
                    note += "\n" + line
                    listed = True
                else:
                    note += " " + line
    return note.strip(), i

def parse_prompt(prompt: str):
    lines = prompt.splitlines()
    i = 0

    # Extract 'import' (if it even exists)
    imports = ""
    if len(lines[0]) > 0:
        imports = lines[0]
        i += 1

    while lines[i] == "":
        i += 1

    # Extract Helper Function (if it even exists)
    helper_function = ""
    if prompt.count("def ") == 2:
        helper_function = re.search(r"(?s)^.*?(def .+?\n(?: {4}.+\n)+)def", prompt).group(1).rstrip()
        while lines[i] != "":
            i += 1

    while lines[i] == "":
        i += 1
    
    # Extract Signature
    #signature = lines[i]
    signature = lines[i].strip()[4:-1]
    i += 1

    # Extract Function Name from Signature
    #print(f"{signature} includes name?")
    try:
        #name = re.search('def (.+?)\\(', signature).group(1)
        name = re.search('(.+?)\\(', signature).group(1)
    except:
        name = "404"

    # Extract Description & sometimes Note (Variables & Constraints are hardcoded)
    line = lines[i].strip()
    #print(line)
    if line == "\"\"\"" or line == "\'\'\'" or line == "\"\"\"Task" or line == "\'\'\'Task":
        i += 1
        desc = lines[i].strip()
    else:
        desc = line[3:]
    linebroken = False
    listed = False
    while True:
        i += 1
        #if i >= len(lines) or name in lines[i]:
        if i >= len(lines) or ">>>" in lines[i] or "=>" in lines[i]:
            break
        line = lines[i].strip()
        if "Examples" in line or ("Example" in line and not "Example," in line) or "example:" in line or "[input/output] samples" in line or "For example:" in line or "for examble:" in line or line == "\"\"\"" or line == "\'\'\'":
            i += 1
            break

        if linebroken:
            desc += line
            linebroken = False
        elif line == "":
            desc += "\n\n"
            linebroken = True
        else:
            if lines[i][4] in ['\'', ' ', '-'] or line[:len(name)] == name or line[-2:] == " )": # cf. various listicals / fib4(n: int) / do_algebra(operator, operand)
                desc += "\n" + line
                listed = True
            elif listed:
                desc += "\n" + line
                listed = True
            else:
                desc += " " + line
    if desc[0] == "\"": # cf. sum_squares(lst) which has 4 times " instead of the usual 3 times
        desc = desc[1:]
    desc = desc.strip() # Remove trailing line breaks
    # Seperate 'Note' if it follows directly after 'Description'
    if "Note:" in desc:
        note = re.search(r'Note:\s*(.*)', desc).group(1).strip()
        desc = re.sub(r'Note:\s*.*', '', desc).strip()
    else:
        note = ""

    if i >= len(lines):
        return {
            "function": name,
            "imports": imports,
            "helper_function": helper_function,
            "signature": signature,
            "description": desc,
            "note": note,
            "examples": [],
            "variables": "",
            "constraints": ""
        }
    
    # Extract Examples
    examples = []
    while True:
        comment = ""
        # Extract Input by counting the opening & closing brackets
        #print(f"Does {lines[i]} of length {len(lines[i])} contain '{name}'?")
        if len(lines[i]) <= 4 or lines[i] == "    \"\"\"" or lines[i] == "    \'\'\'":
            i += 1
            if i+1 >= len(lines) or "Note" in lines[i] or "Variables" in lines[i] or "Constrain" in lines[i]:
                break
            continue
        #if lines[i][4] == '#':
        if name not in lines[i]:
            comment = re.search('    (# )?(.+?)', lines[i]).group(1)
            #comment += lines[i][6:]
            i += 1
            continue
        input_start = lines[i].index(name) + len(name)
        #print("alive")
        #print(f"{i}.{input_start} = {lines[i][input_start]}")
        brackets = 1
        input_end = input_start
        multirow = False
        input = ""
        while brackets > 0:
            #print(f"{i}.{input_end} = {lines[i][input_end]}/{len(lines[i])} for {lines[i]} --> {input}")
            input_end += 1
            if input_end >= len(lines[i]):
                if not multirow:
                    input = lines[i][input_start+1:]
                    multirow = True
                else:
                    input += lines[i][4:]
                i += 1
                input_end = 4
                continue
            if lines[i][input_end] == '(':
                brackets += 1
            elif lines[i][input_end] == ')':
                brackets -= 1
        if not multirow:
            input = lines[i][input_start+1:input_end]
        else:
            input += lines[i][4:input_end]              # cf. get_row(lst, x)
        #print(f"{i}.{input_end} = {lines[i][input_end]} of total line length {len(lines[i])}")

        # Extract Output
        if input_end+1 == len(lines[i]):
            i += 1
            output = lines[i][4:]
        else:
            patterns = [r'=>\s*(.+)', r'->\s*(.+)', r'[=]?=\s*(.+)', r'➞\s*(.+)', r'return[s]?\s*(.+)'] # cf. digitSum(s); fruit_distribution(s,n); search(lst) / choose_num(x, y); will_it_fly(q,w); decimal_to_binary(decimal), anti_shuffle(s) / check_dict_case(dict)
            for pattern in patterns:
                match = re.search(pattern, lines[i])
                if match:
                    output = match.group(1).strip()
                    break
            else:
                output = "404"
        if len(output) > 0 and output[-1] == ".":       # cf. check_dict_case(dict)
            output = output[:-1]
        examples.append({"input": input, "output": output, "comment": comment})

        i += 1
        #print(f"{i} of lines {len(lines)}")
        if i+1 >= len(lines):
            break

    # Extract Note (if existent)
    if note == "":
        note, i = extract_note(lines, i)


    return {
        "function": name,
        "imports": imports,
        "helper_function": helper_function,
        "signature": signature,
        "description": desc,
        "note": note,
        "examples": examples,
        "variables": "",
        "constraints": ""
    }

def print_parsed():
    print(">>> PARSED >>>")
    print("Function:", parsed["function"])
    if parsed["imports"] != "":
        print("Imports:", parsed["imports"])
    if parsed["helper_function"] != "":
        print("Helper Function:\n", parsed["helper_function"])
    print("Signature:", parsed["signature"])
    print("Description:\n", parsed["description"])
    if parsed["note"] != "":
        print("Note:\n", parsed["note"])
    #if parsed["examples"] != []:
    print("Examples:", parsed["examples"])
    if parsed["variables"] != "":
        print("Variables:", parsed["variables"])
    if parsed["constraints"] != "":
        print("Constraints:", parsed["constraints"])

parsed_tasks = []
for i, task in enumerate(dataset):
    # Isolate components
    # Fully Special Cases:
    if task['task_id'] == "HumanEval/61": # Contains broken brackets as input
        parsed_tasks.append({'function': 'correct_bracketing',
                             'imports': '',
                             'helper_function': '',
                             'signature': 'correct_bracketing(brackets: str)',
                             'description': 'Check if in given list of numbers, are any two numbers closer to each other than given threshold.',
                             'note': '',
                             'examples': [{'input': '"("', 'output': 'False', 'comment': ''},
                                          {'input': '"()"', 'output': 'True', 'comment': ''},
                                          {'input': '"(()())"', 'output': 'True', 'comment': ''},
                                          {'input': '")(()"', 'output': 'False', 'comment': ''}],
                             'variables': '',
                             'constraints': ''})
        print_parsed()
        continue
    if task['task_id'] == "HumanEval/64": # Includes 'FIX' before 'def'
        parsed_tasks.append({'function': 'vowels_count',
                             'imports': '',
                             'helper_function': '',
                             'signature': 'vowels_count(s)',
                             'description': 'Write a function vowels_count which takes a string representing a word as input and returns the number of vowels in the string. Vowels in this case are ''a'', ''e'', ''i'', ''o'', ''u''. Here, ''y'' is also a vowel, but only when it is at the end of the given word.',
                             'note': '',
                             'examples': [{'input': '"abcde"', 'output': '2', 'comment': ''},
                                          {'input': '"ACEDY"', 'output': '3', 'comment': ''}],
                             'variables': '',
                             'constraints': ''})
        print_parsed()
        continue
    # if i in [10, 32, 38, 50]: # include two 'def's (helper_function)
    #     continue
    # if i in [68]: # Input/Output
    #     continue
    # if i in [84]: # Text Examples
    #     continue

    parsed = parse_prompt(task["prompt"])

    # Partially Special Cases:
    if task['task_id'] == "HumanEval/32": # Nested examples + weird comment
        parsed['examples'] = [{'input': '[1, 2]', 'output': '-0.5', 'comment': 'round(find_zero([1, 2]), 2) # f(x) = 1 + 2x'},
                              {'input': '[-6, 11, -6, 1]', 'output': '1.0', 'comment': 'round(find_zero([-6, 11, -6, 1]), 2) # (x - 1) * (x - 2) * (x - 3) = -6 + 11x - 6x^2 + x^3'}]
    if task['task_id'] == "HumanEval/68": # Input/Output examples
        parsed['examples'] = [{'input': '[4,2,3]', 'output': '[2, 1]', 'comment': '2 has the smallest even value, and 2 has the smallest index.'},
                              {'input': '[1,2,3]', 'output': '[2, 1]', 'comment': '2 has the smallest even value, and 2 has the smallest index.'},
                              {'input': '[]', 'output': '[]', 'comment': ''},
                              {'input': '[5, 0, 3, 0, 4, 2]', 'output': '[0, 1]', 'comment': '0 is the smallest value, but  there are two zeros, so we will choose the first zero, which has the smallest index.'}]
        parsed['constraints'] = ['1 <= nodes.length <= 10000', '0 <= node.value']
    if task['task_id'] == "HumanEval/78": # Textual examples
        parsed['examples'] = [{'input': '"AB"', 'output': '1', 'comment': ''},
                              {'input': '"1077E"', 'output': '2', 'comment': ''},
                              {'input': '"ABED1A33"', 'output': '4', 'comment': ''},
                              {'input': '"123456789ABCDEF0"', 'output': '6', 'comment': ''},
                              {'input': '"2020"', 'output': '2', 'comment': ''}]
    if task['task_id'] == "HumanEval/81": # Lists 'grade_equation' instead of 'numerical_letter_grade' in examples
        parsed['examples'] = [{'input': '[4.0, 3, 1.7, 2, 3.5]', 'output': '[''A+'', ''B'', ''C-'', ''C'', ''A-'']', 'comment': ''}]
    if task['task_id'] == "HumanEval/84": # Textual examples
        parsed['examples'] = [{'input': '1000', 'output': '1', 'comment': 'For N = 1000, the sum of digits will be 1 the output should be "1".'},
                              {'input': '150', 'output': '110', 'comment': 'For N = 150, the sum of digits will be 6 the output should be "110".'},
                              {'input': '147', 'output': '1100', 'comment': 'For N = 147, the sum of digits will be 12 the output should be "1100".'}]
        parsed['variables'] = [{'identifier': 'N', 'type': 'integer', 'description': ''}]
        parsed['constraints'] = ['0 ≤ N ≤ 10000']
    if task['task_id'] == "HumanEval/90": # No cue for examples
        parsed['description'] = 'You are given a list of integers. Write a function next_smallest() that returns the 2nd smallest element of the list. Return None if there is no such element.'
        parsed['examples'] = [{'input': '[1, 2, 3, 4, 5]', 'output': '2', 'comment': ''},
                              {'input': '[5, 1, 4, 3, 2]', 'output': '2', 'comment': ''},
                              {'input': '[]', 'output': 'None', 'comment': ''},
                              {'input': '[1, 1]', 'output': 'None', 'comment': ''}]
    if task['task_id'] == "HumanEval/94": # Semi-textual examples
        parsed['examples'] = [{'input': '[0,3,2,1,3,5,7,4,5,5,5,2,181,32,4,32,3,2,32,324,4,3]', 'output': '10', 'comment': ''},
                              {'input': '[1,0,1,8,2,4597,2,1,3,40,1,2,1,2,4,2,5,1]', 'output': '25', 'comment': ''},
                              {'input': '[1,3,1,32,5107,34,83278,109,163,23,2323,32,30,1,9,3]', 'output': '13', 'comment': ''},
                              {'input': '[0,724,32,71,99,32,6,0,5,91,83,0,5,6]', 'output': '11', 'comment': ''},
                              {'input': '[0,81,12,3,1,21]', 'output': '3', 'comment': ''},
                              {'input': '[0,8,1,2,1,7]', 'output': '7', 'comment': ''}]
    if task['task_id'] == "HumanEval/105": # Semi-textual examples
        parsed['examples'] = [{'input': '[2, 1, 1, 4, 5, 8, 2, 3]', 'output': '["Eight", "Five", "Four", "Three", "Two", "Two", "One", "One"]', 'comment': 'input -> sort arr -> [1, 1, 2, 2, 3, 4, 5, 8] -> reverse arr -> [8, 5, 4, 3, 2, 2, 1, 1] -> output'},
                              {'input': '[]', 'output': '25', 'comment': 'If the array is empty, return an empty array'},
                              {'input': '[1, -1 , 55]', 'output': '[''One'']', 'comment': 'If the array has any strange number ignore it: input -> sort arr -> [-1, 1, 55] -> reverse arr -> [55, 1, -1] -> output'}]
    if task['task_id'] == "HumanEval/107": # Input/Output examples
        parsed['examples'] = [{'input': '3', 'output': '(1, 2)', 'comment': 'Integer palindrome are 1, 2, 3. one of them is even, and two of them are odd.'},
                              {'input': '12', 'output': '(4, 6)', 'comment': 'Integer palindrome are 1, 2, 3, 4, 5, 6, 7, 8, 9, 11. four of them are even, and 6 of them are odd.'}]
    if task['task_id'] == "HumanEval/112": # Semi-textual examples
        parsed['examples'] = [{'input': '"abcde", "ae"', 'output': '(''bcd'',False)', 'comment': ''},
                              {'input': '"abcdef", "b"', 'output': '(''acdef'',False)', 'comment': ''},
                              {'input': '"abcdedcba", "ab"', 'output': '(''cdedc'',True)', 'comment': ''}]
    if task['task_id'] == "HumanEval/115": # Totally broken due to sus imports (+ semi-textual examples)
        parsed['imports'] = 'import math'
        parsed['description'] = 'You are given a rectangular grid of wells. Each row represents a single well, and each 1 in a row represents a single unit of water. Each well has a corresponding bucket that can be used to extract water from it, and all buckets have the same capacity. Your task is to use the buckets to empty the wells. Output the number of times you need to lower the buckets.'
        parsed['examples'] = [{'input': '[[0,0,1,0], [0,1,0,0], [1,1,1,1]], 1', 'output': '6', 'comment': ''},
                              {'input': '[[0,0,1,1], [0,0,0,0], [1,1,1,1], [0,1,1,1]], 2', 'output': '5', 'comment': ''},
                              {'input': '[[0,0,0], [0,0,0]], 5', 'output': '0', 'comment': ''}]
        parsed['constraints'] = ['all wells have the same length', '1 <= grid.length <= 10^2', '1 <= grid[:,1].length <= 10^2', 'grid[i][j] -> 0 | 1', '1 <= capacity <= 10']
    if task['task_id'] == "HumanEval/120": # Semi-textual examples
        parsed['examples'] = [{'input': '[-3, -4, 5], 3', 'output': '[-4, -3, 5]', 'comment': ''},
                              {'input': '[4, -4, 4], 2', 'output': '[4, 4]', 'comment': ''},
                              {'input': '[-3, 2, 1, 2, -1, -2, 1], 1', 'output': '[2]', 'comment': ''}]
    if task['task_id'] == "HumanEval/122": # Semi-textual example
        parsed['examples'] = [{'input': '[111,21,3,4000,5,6,7,8,9], 4', 'output': '24', 'comment': 'output = 24 # sum of 21 + 3'}]
        parsed['constraints'] = ['1 <= len(arr) <= 100', '1 <= k <= len(arr)']
    if task['task_id'] == "HumanEval/129": # Input/Output examples
        parsed['examples'] = [{'input': '[ [1,2,3], [4,5,6], [7,8,9]], 3', 'output': '[-4, -3, 5]', 'comment': ''},
                              {'input': '[-3, 2, 1, 2, -1, -2, 1], 1', 'output': '[2]', 'comment': ''}]
    if task['task_id'] == "HumanEval/132": # No cue for examples
        parsed['description'] = 'Create a function that takes a string as input which contains only square brackets. The function should return True if and only if there is a valid subsequence of brackets where at least one bracket in the subsequence is nested.'
        parsed['examples'] = [{'input': '''[[]]''', 'output': 'True', 'comment': ''},
                              {'input': '''[]]]]]]][[[[[]''', 'output': 'False', 'comment': ''},
                              {'input': '''[][]''', 'output': 'False', 'comment': ''},
                              {'input': '''[]''', 'output': 'False', 'comment': ''},
                              {'input': '''[[][]]''', 'output': 'True', 'comment': ''},
                              {'input': '''[[]][[''', 'output': 'True', 'comment': ''}]
    if task['task_id'] == "HumanEval/133": # Semi-textual examples
        parsed['examples'] = [{'input': '[1,2,3]', 'output': '14', 'comment': ''},
                              {'input': '[1,4,9]', 'output': '98', 'comment': ''},
                              {'input': '[1,3,5,7]', 'output': '84', 'comment': ''},
                              {'input': '[1.4,4.2,0]', 'output': '29', 'comment': ''},
                              {'input': '[-2.4,1,1]', 'output': '6', 'comment': ''}]
    if task['task_id'] == "HumanEval/137": # No cue for examples
        parsed['description'] = 'Create a function that takes integers, floats, or strings representing real numbers, and returns the larger variable in its given variable type. Return None if the values are equal.'
        #parsed['note'] = 'If a real number is represented as a string, the floating point might be . or ,'
        parsed['examples'] = [{'input': '1, 2.5', 'output': '2.5', 'comment': ''},
                              {'input': '1, "2,3"', 'output': '"2,3"', 'comment': ''},
                              {'input': '"5,1", "6"', 'output': '"6"', 'comment': ''},
                              {'input': '"1", 1', 'output': 'None', 'comment': ''}]
    if task['task_id'] == "HumanEval/141": # Weird comment
        parsed['examples'] = [{'input': '"example.txt"', 'output': "'Yes'", 'comment': ''},
                              {'input': '"1example.dll"', 'output': "'No'", 'comment': 'the name should start with a latin alphapet letter'}]
    if task['task_id'] == "HumanEval/142": # Semi-textual examples
        parsed['examples'] = [{'input': '[1,2,3]', 'output': '6', 'comment': ''},
                              {'input': '[]', 'output': '0', 'comment': ''},
                              {'input': '[-1,-5,2,-1,-5]', 'output': '-126', 'comment': ''}]
    if task['task_id'] == "HumanEval/143": # Input/Output examples
        parsed['examples'] = [{'input': '"This is a test"', 'output': '"is"', 'comment': ''},
                              {'input': '"lets go for swimming"', 'output': '"go for"', 'comment': ''}]
        parsed['constraints'] = ['1 <= len(sentence) <= 100', 'sentence contains only letters']
    if task['task_id'] == "HumanEval/144": # No cue for examples
        parsed['description'] = 'Your task is to implement a function that will simplify the expression x * n. The function returns True if x * n evaluates to a whole number and False otherwise. Both x and n, are string representation of a fraction, and have the following format, <numerator>/<denominator> where both numerator and denominator are positive whole numbers.\nYou can assume that x, and n are valid fractions, and do not have zero as denominator.'
        parsed['examples'] = [{'input': '"1/5", "5/1"', 'output': 'True', 'comment': ''},
                              {'input': '"1/6", "2/1"', 'output': 'False', 'comment': ''},
                              {'input': '"7/10", "10/2"', 'output': 'False', 'comment': ''}]
    if task['task_id'] == "HumanEval/147": # Input/Output example
        parsed['examples'] = [{'input': '5', 'output': '1', 'comment': 'a = [1, 3, 7, 13, 21]\nThe only valid triple is (1, 7, 13).'}]
    if task['task_id'] == "HumanEval/149": # Lists 'assert list_sort' instead of 'sorted_list_sum' in examples
        parsed['examples'] = [{'input': '["aa", "a", "aaa"]', 'output': '[1, 2, 1]', 'comment': ''},
                              {'input': '["ab", "a", "aaa", "cd"]', 'output': '[]', 'comment': ''}]
    if task['task_id'] == "HumanEval/151": # No cue for examples
        parsed['description'] = 'Given a list of numbers, return the sum of squares of the numbers in the list that are odd. Ignore numbers that are negative or not integers. If the input list is empty, return 0.'
        parsed['examples'] = [{'input': '[1, 3, 2, 0]', 'output': '10', 'comment': 'output = 1 + 9 + 0 + 0 = 10'},
                              {'input': '[-1, -2, 0]', 'output': '0', 'comment': ''},
                              {'input': '[9, -2]', 'output': '81', 'comment': ''},
                              {'input': '[0]', 'output': '0', 'comment': ''}]
    if task['task_id'] == "HumanEval/158": # No cue for examples
        parsed['description'] = 'Write a function that accepts a list of strings. The list contains different words. Return the word with maximum number of unique characters. If multiple strings have maximum number of unique characters, return the one which comes first in lexicographical order.'
        parsed['examples'] = [{'input': '["name", "of", "string"]', 'output': '"string"', 'comment': ''},
                              {'input': '["name", "enam", "game"]', 'output': '"enam"', 'comment': ''},
                              {'input': '["aaaaaaa", "bb" ,"cc"]', 'output': '"aaaaaaa"', 'comment': ''}]
    if task['task_id'] == "HumanEval/159": # Defines Variables & 'Constrain:'
        parsed['variables'] = [{'identifier': 'number', 'type': 'integer', 'description': 'the number of carrots that you have eaten.'}, {'identifier': 'need', 'type': 'integer', 'description': 'the number of carrots that you need to eat.'}, {'identifier': 'remaining', 'type': 'integer', 'description': 'the number of remaining carrots thet exist in stock'}]
        parsed['constraints'] = ['0 <= number <= 1000', '0 <= need <= 1000', '0 <= remaining <= 1000']
    if task['task_id'] == "HumanEval/160": # Very weirdly formatted example
        parsed['examples'] = [{'input': '[''+'', ''*'', ''-''], [2, 3, 4, 5]', 'output': '9', 'comment': 'result = 2 + 3 * 4 - 5 => result = 9'}]
    


    parsed_tasks.append(parsed)

    # Print current task
    print("\n\n\n\n\n### " + task['task_id'] + " ###")
    print(task['prompt'])

    print_parsed()

    # if i >= 32:
    #     break

#> chcp 65001
#> python3.11.exe -u .\humaneval_reformatter.py | tee output.txt
print(f"\nSuccessfully parsed {len(parsed_tasks)}/{len(dataset)} tasks")



# Save modified datasets
dataset_json = []
dataset_markdown = []
dataset_yaml = []

for i, task in enumerate(dataset):
    dataset_json.append(copy.deepcopy(task))
    dataset_markdown.append(copy.deepcopy(task))
    dataset_yaml.append(copy.deepcopy(task))

    # JSON
    dataset_json[i]['prompt'] = json.dumps(parsed_tasks[i], indent=2)

    # Markdown
    empty_field = '_None_'
    markdown_prompt = f"\
## Function: `{parsed_tasks[i]['function']}`\n\
\n**Imports**\n\n\
"
    if len(parsed_tasks[i]['imports']) == 0:
        markdown_prompt += f"{empty_field}\n"
    else:
        markdown_prompt += f"\
`{parsed_tasks[i]['imports']}`\n\
"
    markdown_prompt += f"\
\n**Helper Function**\n\n\
"
    if len(parsed_tasks[i]['helper_function']) == 0:
        markdown_prompt += f"{empty_field}\n"
    else:
        markdown_prompt += f"\
```python\n\
{parsed_tasks[i]['helper_function']}\n\
```\
"
    markdown_prompt += f"\
\n**Signature**\n\n\
`{parsed_tasks[i]['signature']}`\n\
\n**Description**\n\n\
{parsed_tasks[i]['description']}\n\
\n**Note**\n\n\
{parsed_tasks[i]['note'] or empty_field}\n\
\n**Examples**\n\
"
    if len(parsed_tasks[i]['examples']) == 0:
        markdown_prompt += f"\n{empty_field}\n"
    else:
        markdown_prompt += f"\
| Input | Output | Comment |\n\
|-------|--------|---------|\n\
"
        for example in parsed_tasks[i]['examples']:
            markdown_prompt += f"| `{example['input']}` | `{example['output']}` | {example['comment']} |\n"
    markdown_prompt += f"\
\n**Variables**\n\
"
    if len(parsed_tasks[i]['variables']) == 0:
        markdown_prompt += f"\n_Not specified_\n"
    else:
        markdown_prompt += f"\
| Identifier | Type | Description |\n\
|------------|------|-------------|\n\
"
        for variable in parsed_tasks[i]['variables']:
            markdown_prompt += f"| `{variable['identifier']}` | {variable['type']} | {variable['description']} |\n"
    markdown_prompt += f"\
\n**Constraints**\n\
"
    if len(parsed_tasks[i]['constraints']) == 0:
        markdown_prompt += f"\n{empty_field}\n"
    else:
        for constraint in parsed_tasks[i]['constraints']:
            markdown_prompt += f"- `{constraint}`\n"

    dataset_markdown[i]['prompt'] = markdown_prompt

    # YAML
    dataset_yaml[i]['prompt'] = yaml.dump(parsed_tasks[i], sort_keys=False)#"yaml"

Dataset.from_list(dataset_json).save_to_disk("./datasets/HumanEval/json")
Dataset.from_list(dataset_markdown).save_to_disk("./datasets/HumanEval/markdown")
Dataset.from_list(dataset_yaml).save_to_disk("./datasets/HumanEval/yaml")

print_index = 159
print(f"\n\n\nOriginal Prompt #{print_index}:\n{dataset[print_index]['prompt']}")
test_json = load_from_disk("./datasets/HumanEval/json")
print(f"\nJSON Prompt #{print_index}:\n{test_json[print_index]['prompt']}")
test_markdown = load_from_disk("./datasets/HumanEval/markdown")
print(f"\nMarkdown Prompt #{print_index}:\n{test_markdown[print_index]['prompt']}")
test_yaml = load_from_disk("./datasets/HumanEval/yaml")
print(f"\nYAML Prompt #{print_index}:\n{test_yaml[print_index]['prompt']}")
