import pandas as pd
import json
import pickle
import os.path
from enum import Enum
from json import JSONDecodeError
import random
from emora_stdm import DialogueFlow
from emora_stdm import Macro, Ngrams
from typing import Dict, Any, List, Callable, Pattern
import re
import openai
import regexutils
import LEANNA
import businesModel

PATH_API_KEY = 'resources/openai_api.txt'
openai.api_key_path = PATH_API_KEY

all_cat = []
business_plan = {}
example_dict = {"customer needs": 1, "customer fears": 1, "customer wants": 1, "product benefit": 1,
                "product experiences": 1, "value proposition": 1, "before purchase": 1, "during purchase": 1,
                "after purchase": 1, "intellectual strategy": 1, "value chain strategy": 1, "architectural strategy": 1,
                "disruption strategy": 1, "trust strengths": 1, "value loyalty": 1, "team skills": 1,
                "team culture": 1, "operations": 1, "inbound logistics": 1, "outbound logistics": 1,
                "resource gathering": 1}

transition_record = {
    'state': 'start',
    '#QUESTION': {
        '#REC_BUS': {
            '#GET_KNOW': {
                'IF($KNOW=yes)': 'pos',
                '` `': {
                    'state': 'neg',
                    'score': 0.2
                }
            },
            'error': {
                '`Your idea is good. Are you confident to skip this start up category?`': {
                    '#CONFIDENCE': {
                        'IF($CONFI=yes) ` `': 'pos',
                        '` `': 'neg'
                    },
                    'error': {

                    }
                }
            }
        },
        'error': {

        }
    }
}

transition_pos = {
    'state': 'pos',
    '`Thanks, I have recorded it to the business plan. What do you want to talk about next?`': 'big_small_cat'
}

# transition_neg = {
#     'state': 'neg',
#     '#EX': {
#         '#IDEA_EX': {
#             'IF($ALL=true)': 'final',
#             'IF($IDEA_EX=business plan) #REC_BUS': 'pos',
#             'IF($IDEA_EX=example)': 'neg',
#             'IF($IDEA_EX=move on)': 'next topic',
#             '`Glad you feel good about this part`': {
#                 'state': 'next topic',
#                 'score': 0.1
#             }
#         },
#         'error': {
#
#         }
#     }
# }


class MacroQuestion(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        df = pd.read_csv("resources/data.csv")
        all_cat.append(vars['SUB_CAT'])
        question = df[df['Section'] == vars['large_cat'] and df['Subcategory'] == vars['SUB_CAT']]['Question']
        vars['CUR_Q'] = question
        return 'Let\'s brainstorm ' + vars['SUB_CAT'] + ' together ' + question


class MacroExample(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        df = pd.read_csv("resources/data.csv")
        examples = df[df['Section'] == vars['large_cat'] and df['Subcategory'] == vars['SUB_CAT']]
        if example_dict[vars['SUB_CAT']] == 1:
            example = examples['E1']
        elif example_dict[vars['SUB_CAT']] == 2:
            example = examples['E2']
        elif example_dict[vars['SUB_CAT']] == 3:
            example = examples['E3']
        elif example_dict[vars['SUB_CAT']] == 4:
            example = examples['E4']
        else:
            return 'Sorry I don\'t have more examples'

        example_dict[vars['SUB_CAT']] += 1

        if len(all_cat) == 22:
            vars['ALL'] = 'true'

        if len(all_cat) != 0:
            encourage = all_cat[random.randrange(len(all_cat))]
            return 'Building a start up is a long process. But you have a good business plan on ' \
                + encourage + 'Here is an ' + vars['SUB_CAT'] + 'example that might help you \n' + \
                example + 'What do you think about your business plan in this topic now?'
        else:
            return 'Here is an ' + vars['SUB_CAT'] + 'example that might help you \n' + \
                example + 'What do you think about your business plan in this topic now?'


class V(Enum):
    KNOW = 0,
    CONFI = 1,
    IDEA_EX = 2


def gpt_completion(input: str, regex: Pattern = None) -> str:
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{'role': 'user', 'content': input}]
    )
    output = response['choices'][0]['message']['content'].strip()

    if regex is not None:
        m = regex.search(output)
        output = m.group().strip() if m else None

    return output


class MacroGPTJSON(Macro):
    def __init__(self, request: str, full_ex: Dict[str, Any], field: str, direct: bool, empty_ex: Dict[str, Any] = None,
                 set_variables: Callable[[Dict[str, Any], Dict[str, Any]], None] = None):
        self.request = request
        self.full_ex = json.dumps(full_ex)
        self.empty_ex = '' if empty_ex is None else json.dumps(empty_ex)
        self.check = re.compile(regexutils.generate(full_ex))
        self.set_variables = set_variables
        self.field = field
        self.direct = direct

    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        examples = f'{self.full_ex} or {self.empty_ex} if unavailable' if self.empty_ex else self.full_ex
        prompt = f'{self.request} Respond in the JSON schema such as {examples}: {ngrams.raw_text().strip()}'
        output = gpt_completion(prompt)
        if not output: return False

        try:
            d = json.loads(output)
        except JSONDecodeError:
            print(f'Invalid: {output}')
            return False

        if self.set_variables:
            self.set_variables(vars, d)
        else:
            vars.update(d)

        if self.direct:
            ls = vars[self.field]
            vars[self.field] = ls[random.randrange(len(ls))]

        return True


class MacroGPTJSON_REC(Macro):
    def __init__(self, empty_ex: Dict[str, Any] = None,
                 set_variables: Callable[[Dict[str, Any], Dict[str, Any]], None] = None):
        self.request = 'Extract user\'s answer to the following question: '
        # self.full_ex = json.dumps({vars['SUB_CAT']: "This is my business idea"})
        self.empty_ex = '' if empty_ex is None else json.dumps(empty_ex)
        # self.check = re.compile(regexutils.generate(full_ex))
        self.set_variables = set_variables

    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        examples = f'{json.dumps({vars["SUB_CAT"]: "This is my business idea"})} or {self.empty_ex} if unavailable' if self.empty_ex else self.full_ex
        prompt = f'{self.request + vars["CUR_Q"]} Respond in the JSON schema such as {examples}: {ngrams.raw_text().strip()}'
        output = gpt_completion(prompt)
        if not output: return False

        try:
            d = json.loads(output)
        except JSONDecodeError:
            print(f'Invalid: {output}')
            return False

        if self.set_variables:
            self.set_variables(vars, d)
        else:
            vars.update(d)

        business_plan.update(vars["SUB_CAT"])

        return True


macros = {
    'QUESTION': MacroQuestion(),
    'REC_BUS': MacroGPTJSON_REC(),
    'GET_KNOW': MacroGPTJSON(
        'Does the user answer the question well and adequate? Provide binary answer, yes or no',
        {V.KNOW.name: ["yes"]}, V.KNOW.name, True
    ),
    'CONFIDENCE': MacroGPTJSON(
        'Is the user confident to skip this start up section? Provide binary answer, yes or no',
        {V.CONFI.name: ["yes"]}, V.CONFI.name, True
    ),
    'EX': MacroExample(),
    'IDEA_EX': MacroGPTJSON(
        'Is the user providing an business idea, requesting another example or wanting to move on to next topic? '
        'Provide answers in, business idea, example, or move on',
        {V.IDEA_EX.name: ["business idea"]}, V.IDEA_EX.name, True
    )
}


df = DialogueFlow('start', end_state='end')
df.load_transitions(transition_record)
df.load_transitions(transition_neg)
df.load_transitions(transition_pos)
df.add_macros(macros)


if __name__ == '__main__':
    df.run()