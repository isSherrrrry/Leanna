import json
import pickle
import os.path
from enum import Enum
from json import JSONDecodeError
import re

from emora_stdm import DialogueFlow
from emora_stdm import Macro, Ngrams
from typing import Dict, Any, List, Callable, Pattern
import openai

from src import regexutils

import brainstorm

PATH_API_KEY = '../resources/openai_api.txt'
openai.api_key_path = PATH_API_KEY


def visits() -> DialogueFlow:
    transition_business = {
        'state': 'business_start',
        '`Hi, I am so excited to talk to you about your business. \n'
        'What is its name and are you selling a product or a service? \n'
        'A product is something that people can use and is tangible. \n'
        'Think of a computer or software such as google drive. \n'
        'A service is something you can provide or perform for another person. \n'
        'For example, a hair salon or a restaurant service.`':{
            'state': 'bus_name_indu',
            '#SET_BUS_NAME': {
                '`Thanks for letting me know! That sounds super exciting.'
                '`#GET_BUS_NAME`is sure to change the world one day as a fantastic`#GET_INDU`industry. '
                'My role is to help you brainstorm on fuzzy ideas of your business so that you '
                'can have a tangible pitch by the end of our conversation. '
                'Is there a particular problem area you would like to brainstorm about first?`' : {
                    'state': 'big_small_cat',
                    '#SET_BIG_SAMLL_CATE': {
                        '`Cool! Let\'s talk about`#GET_SMALL_CAT`in`#GET_BIG_CAT`category!`': 'record'
                    },
                    'error': {
                        '`Cool! I can start you with product innovation talking about customer needs. '
                        'Does that sound good?`': {
                            '#SET_YES_NO': {
                                '`Cool! Let\'s start.`': 'end'
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

    macros = {
        'SET_BUS_NAME': MacroGPTJSON(
            'Please find the person\'s business name and the industry',
            {V.business_name.name: "Microsoft", V.industry.name:"technology"},
            set_bus_name
        ),
        'SET_BIG_SAMLL_CATE': MacroGPTJSON(
            'Please classify the input sentence into the following three large categories '
            'and the corresponding small category within each large category: '
            'product innovation (includes customer needs, customer fears, customer wants, '
            'product benefits, product features, product experiences, and value proposition), '
            'ustomer relationship (includes before purchase, during purchase, after purchase, '
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
        'GET_BUS_NAME': MacroNLG(get_bus_name),
        'GET_INDU': MacroNLG(get_industry),
        'GET_BIG_CAT': MacroNLG(get_big_cat),
        'GET_SMALL_CAT': MacroNLG(get_small_cat),
    }

    df = DialogueFlow('business_start', end_state='end')
    df.load_transitions(transition_business)
    df.load_transitions(transition_end)
    df.add_macros(macros)
    return df

class V(Enum):
    business_name = 0
    industry = 1
    large_cat = 2
    small_cat = 3
    sounds_yesno = 4

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
