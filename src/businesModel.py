import csv
import json
import pickle
import os.path
import random
from enum import Enum
from json import JSONDecodeError
import re

from emora_stdm import DialogueFlow
from emora_stdm import Macro, Ngrams
from typing import Dict, Any, List, Callable, Pattern
import openai

from src import regexutils

PATH_API_KEY = '../resources/openai_api.txt'
openai.api_key_path = PATH_API_KEY


def visits() -> DialogueFlow:
    transition_business = {
        'state': 'business_start',
        '`I am so excited to talk to you about your business. \n'
        'What is its name and are you selling a product or a service? \n'
        'A product is something that people can use and is tangible. \n'
        'Think of a computer or software such as google drive. \n'
        'A service is something you can provide or perform for another person. \n'
        'For example, a hair salon or a restaurant service.`': {
            'state': 'bus_name_indu',
            '#SET_BUS_NAME': {
                '`Thanks for letting me know! That sounds super exciting.'
                '`#GET_BUS_NAME`is sure to change the world one day as a fantastic`#GET_INDU`industry. '
                'My role is to help you brainstorm on fuzzy ideas of your business so that you '
                'can have a tangible pitch by the end of our conversation. '
                'Is there a particular problem area you would like to brainstorm about first?`' : {
                    'state': 'big_small_cat',
                    '#SET_BIG_SAMLL_CATE': {
                        '`Cool! Let\'s talk about`#GET_SMALL_CAT`in`#GET_BIG_CAT`category!`': 'business_sub'
                    },
                    'error': {
                        '`Hello `#GET_AVAIL_CATE`hja': {
                            '#SET_YES_NO': {
                                '`Cool! Let\'s start.`': 'business_sub'
                            },
                            'error':{
                                '`Okay, do want to start with something else? '
                                'We can talk about product innovation, customer relationships, '
                                'and infrastructure management. '
                                'You can always leave Leanna and come back later. '
                                'Just type \'quit\' to leave.`': 'big_small_cat'
                            }
                        }
                    }
                }
            },
            'error': {
                '`I\'m sorry I did not get your business industry. '
                'We recommend using Leanna when you have an idea in the industry you want to be working at. '
                'You can always leave Leanna and come back later. Just type \'quit\' to leave. '
                'Now, do you want to try again by telling us about your business name and industry?`': 'bus_name_indu'
            }
        }
    }

    transition_end = {
        'state': 'business_end',
        '`Thank you so much for talking with me. This interaction has been fabulous. '
        'I get to know more about`#GET_BUS_NAME`and it was awesome!'
        'Would you like a summary of what we talked about? `': {
            '#SET_YES_NO': {
                '`#GET_SUMMARY`': 'end'
            },
            'error': {
                '`Alright. Thanks for using Leanna! Please come back when you have more ideas. '
                'Leanna can always pick up where we have left this time. `': 'end'
            }
        }
    }

    transition_question = {
        'state': 'business_sub',
        '`We are going to brainstorm`#GET_SMALL_CAT`under`#GET_BIG_CAT`category. \n'
        'Let\'s think about this question:\n`#GET_QUESTION` `': {
            'state': 'set_user_know',
            '#SET_USER_KNOW': {
                '#IF($user_know=yes)':{
                    'state': 'business_pos'
                },
                '` `': {
                    'state': 'business_neg',
                    'score': 0.2
                }
            },
            'error': {
                '`Cool. Can you elaborate more on the plan please? `': 'set_user_know'
            }
        }
    }

    transition_positive = {
        'state': 'business_pos',
        '#IF($all) `Thanks, I have recorded it to the business plan.`': 'business_end',
        '`Thanks, I have recorded it to the business plan. What do you want to talk about next?`': {
            'state': 'big_small_cat',
            'score': 0.2
        }
    }

    transition_negative = {
        'state': 'business_neg',
        '#GET_EXAMPLE': {
            '#SET_IDEA_EX': {
                '#IF($ex_choice=businessplan)': {
                    'state': 'business_pos',
                    'score': 0.2
                },
                '#IF($ex_choice=example)': {
                    'state': 'business_neg',
                    'score': 0.2
                },
                '#IF($ex_choice=moveon) `Cool, let\'s move on. What topics do you want to discuss next?`': {
                    'state': 'big_small_cat',
                    'score': 0.2
                },
                '`Glad you feel good about this part. What topics do you want to discuss next?`': {
                    'state': 'big_small_cat',
                    'score': 0.1
                }
            },
            'error': {
                '`sorry`': 'end'
            }
        }
    }

    macros = {
        'SET_BUS_NAME': MacroGPTJSON(
            'Please find the person\'s business name and the industry',
            {V.business_name.name: "Microsoft", V.industry.name:"technology"},
            set_bus_name
        ),
        'SET_BIG_SAMLL_CATE': MacroGPTJSON_BS(
            'Please classify the input sentence into the following three large categories '
            'and the corresponding small category within each large category: '
            'product innovation (includes customer needs, customer fears, customer wants, '
            'product benefits, product features, product experiences, and value proposition), '
            'customer relationship (includes before purchase, during purchase, after purchase, '
            'intellectual strategy, value chain strategy, architectural strategy, disruption strategy, '
            'trust strengths, and values loyalty) , and infrastructure management (team skills, team culture, '
            'operations, inbound logistics, outbound logistics, and resource gathering).  '
            'Please only return the large category and small category, and nothing else.',
            {V.large_cat.name: "product innovation", V.small_cat.name: "customer needs"},
            set_cat_name
        ),
        'SET_YES_NO': MacroGPTJSON(
            'Please find out if this means yes or no. '
            'if it means yes, please only return yes in json; '
            'if it means no, please return an empty string in json',
            {V.sounds_yesno.name: "yes"},
            set_yesno
        ),
        'SET_USER_KNOW': MacroGPTJSON(
            'Does the user answer the question well and adequate? Provide binary answer, yes or no.'
            'Please also provide the entire input as the next output. '
            'Phrase them into a json, with yes/no as the first element, and the input as the second;'
            'Only return the json file, please. thanks',
            {V.user_know.name: "yes", V.ans_bp.name: "here's the entire input"},
            set_know
        ),
        'SET_IDEA_EX': MacroGPTJSON_BP(
            'Is the user providing an business idea, requesting another example or wanting to move on to next topic? '
            'Please choose the answer from the following: businessplan, moveon, example ',
            {V.ex_choice.name: "businessplan"},
            set_ex_idea
        ),
        'GET_BUS_NAME': MacroNLG(get_bus_name),
        'GET_INDU': MacroNLG(get_industry),
        'GET_BIG_CAT': MacroNLG(get_big_cat),
        'GET_SMALL_CAT': MacroNLG(get_small_cat),
        'GET_QUESTION': MacroGetQuestion(),
        'GET_EXAMPLE': MacroGetExample(),
        'GET_AVAIL_CATE': MacroGetAvailCat()
    }

    df = DialogueFlow('business_start', end_state='end')
    df.load_transitions(transition_business)
    df.load_transitions(transition_end)
    df.load_transitions(transition_question)
    df.load_transitions(transition_negative)
    df.load_transitions(transition_positive)
    df.add_macros(macros)
    return df

class MacroGetQuestion(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        small_cat = vars.get('small_cat')
        if small_cat is None:
            return "Please provide a valid subsec."

        small_cat = small_cat.replace(" ", "")  # Remove spaces from the small_cat string
        question_text = None

        with open('../resources/data.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['subsec'] == small_cat:
                    question_text = row['Question']
                    break
        vars['SELECTED_QUESTION'] = question_text
        return question_text


class MacroGetAvailCat(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        small_cat_answers = vars.get('small_cat_answers', {})
        talked_subsecs = set(small_cat_answers.keys())
        large_cat = vars.get('large_cat', None)

        all_subsecs = []  # List of all possible subsec values
        subsec_to_section = {}  # Mapping of subsec values to their corresponding section

        with open('../resources/data.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                subsec = row['subsec']
                section = row['section']
                if large_cat is None or section == large_cat:
                    all_subsecs.append(subsec)
                    subsec_to_section[subsec] = section

        available_subsecs = list(set(all_subsecs) - talked_subsecs)

        chosen_subsec = random.choice(available_subsecs)
        chosen_large_cat = subsec_to_section[chosen_subsec]
        vars['small_cat'] = chosen_subsec
        vars['large_cat'] = chosen_large_cat

        return f"Cool! I can start you with {chosen_large_cat} talking about {chosen_subsec}. Does that sound good?"

class V(Enum):
    business_name = 0
    industry = 1
    large_cat = 2
    small_cat = 3
    sounds_yesno = 4
    user_know = 5
    ans_bp = 6
    ex_choice = 7

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

class MacroGetExample(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        small_cat = vars.get('small_cat')

        small_cat = small_cat.replace(" ", "")  # Remove spaces from the small_cat string
        available_examples = []

        with open('../resources/data.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['subsec'] == small_cat:
                    for col in ['E1', 'E2', 'E3', 'E4']:
                        available_examples.append(row[col])
                    break

        used_examples_key = f"USED_EXAMPLES_{small_cat}"
        used_examples = vars.get(used_examples_key, [])

        remaining_examples = [example for example in available_examples if example not in used_examples]

        if len(remaining_examples) == 0:
            return "Sorry, I don't have more examples."

        selected_example = remaining_examples[0]  # Select the first remaining example
        used_examples.append(selected_example)
        vars[used_examples_key] = used_examples

        small_cat_answers = vars.get('small_cat_answers', {})

        if len(vars['small_cat_answers']) != 0:
            if small_cat_answers:
                encourage = random.choice(list(small_cat_answers.keys()))
            else:
                encourage = ''
            return 'Building a start up is a long process. But you have a good business plan on ' \
                + encourage + ' Here is an ' + vars['small_cat'] + ' example that might help you \n' + \
                selected_example + ' What do you think about your business plan in this topic now?'
        else:
            return 'Here is an ' + vars['small_cat'] + 'example that might help you \n' + \
                selected_example + ' What do you think about your business plan in this topic now?'

class MacroGPTJSON(Macro):
    def __init__(self, request: str, full_ex: Dict[str, Any], field: str, empty_ex: Dict[str, Any] = None,
                 set_variables: Callable[[Dict[str, Any], Dict[str, Any]], None] = None):
        self.request = request
        self.full_ex = json.dumps(full_ex)
        self.empty_ex = '' if empty_ex is None else json.dumps(empty_ex)
        self.check = re.compile(regexutils.generate(full_ex))
        self.set_variables = set_variables
        self.field = field

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

        if d is None:
            return False

        if self.set_variables:
            self.set_variables(vars, d)
        else:
            vars.update(d)

        return True

class MacroGPTJSON_BS(Macro):
    def __init__(self, request: str, full_ex: Dict[str, Any], field: str, empty_ex: Dict[str, Any] = None,
                 set_variables: Callable[[Dict[str, Any], Dict[str, Any]], None] = None):
        self.request = request
        self.full_ex = json.dumps(full_ex)
        self.empty_ex = '' if empty_ex is None else json.dumps(empty_ex)
        self.check = re.compile(regexutils.generate(full_ex))
        self.set_variables = set_variables
        self.field = field

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

        if d is None:
            return False

        if self.set_variables:
            self.set_variables(vars, d)
        else:
            vars.update(d)


        return True

class MacroGPTJSON_BP(Macro):
    def __init__(self, request: str, full_ex: Dict[str, Any], field: str, empty_ex: Dict[str, Any] = None,
                 set_variables: Callable[[Dict[str, Any], Dict[str, Any]], None] = None):
        self.request = request
        self.full_ex = json.dumps(full_ex)
        self.empty_ex = '' if empty_ex is None else json.dumps(empty_ex)
        self.check = re.compile(regexutils.generate(full_ex))
        self.set_variables = set_variables
        self.field = field

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

        if d is None:
            return False

        if self.set_variables:
            self.set_variables(vars, d)
        else:
            vars.update(d)


        small_cat_answers = vars.get('small_cat_answers', {})

        vars['user_know'] = d.get('user_know')
        small_cat = vars.get('small_cat')
        ans_bp = d.get('ans_bp')
        if small_cat and ans_bp:
            small_cat_answers = vars.get('small_cat_answers', {})
            small_cat_answers[small_cat] = ans_bp
            vars['small_cat_answers'] = small_cat_answers

        vars['all'] = False
        if len(small_cat_answers) == 22:
            vars['all'] = True

        return True



class MacroNLG(Macro):
    def __init__(self, generate: Callable[[Dict[str, Any]], str]):
        self.generate = generate

    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        return self.generate(vars)


def get_bus_name(vars: Dict[str, Any]):
    ls = vars[V.business_name.name]
    if ls is None:
        return "Your business"
    return ls

def get_industry(vars: Dict[str, Any]):
    ls = vars[V.industry.name]
    return ls

def get_big_cat(vars: Dict[str, Any]):
    ls = vars[V.large_cat.name]
    return ls

def get_small_cat(vars: Dict[str, Any]):
    ls = vars[V.small_cat.name]
    return ls

def set_bus_name(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[V.business_name.name] = user[V.business_name.name]
    vars[V.industry.name] = user[V.industry.name]

def set_cat_name(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[V.large_cat.name] = user[V.large_cat.name]
    vars[V.small_cat.name] = user[V.small_cat.name]

def set_yesno(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[V.sounds_yesno.name] = user[V.sounds_yesno.name]

def set_know(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[V.user_know.name] = user[V.user_know.name]
    vars[V.ans_bp.name] = user[V.ans_bp.name]

def set_ex_idea(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[V.ex_choice.name] = user[V.ex_choice.name]

def save(df: DialogueFlow, varfile: str):
    d = {k: v for k, v in df.vars().items() if not k.startswith('_')}
    pickle.dump(d, open(varfile, 'wb'))


def load(df: DialogueFlow, varfile: str):
    d = pickle.load(open(varfile, 'rb'))
    df.vars().update(d)
    df.run()
    save(df, varfile)


if __name__ == '__main__':
    df = visits()

    path = '../resources/visits.pkl'

    check_file = os.path.isfile(path)
    if check_file:
        load(df, '../resources/visits.pkl')
    else:
        df.run()
        save(df, '../resources/visits.pkl')
