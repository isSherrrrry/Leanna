import csv
import json
import pickle
import os.path
from enum import Enum
from json import JSONDecodeError
import random
from emora_stdm import DialogueFlow
from emora_stdm import Macro, Ngrams
from typing import Dict, Any, List, Callable, Pattern
import time
import re
import openai
import regexutils

PATH_API_KEY = 'resources/openai_api.txt'
openai.api_key_path = PATH_API_KEY

told_jokes = []



def visits() -> DialogueFlow:
    transition_visit = {
        'state': 'start',
        '`Hi, I\'m Leanna, your personal start-up consultant. At` #TIME `, I had the pleasure to meet '
        ' \n With time as our guide, our encounter was meant to be. May I know the name of future business tycoon?`': {
            '#SET_CALL_NAMES': {
                '`Nice to meet you,`$call_names `. Before we dive into business, '
                'I want to know how you are doing. Do you mind sharing to me your most exciting day in this week?`': {
                    '#SET_SENTIMENT': {
                        '#IF($sentiment=positive) `The user\'s sentiment is` $sentiment': 'end',
                        '#IF($sentiment=negative) `The user\'s sentiment is` $sentiment': 'personality',
                        '#IF($sentiment=neutral) `The user\'s sentiment is` $sentiment': 'joke',
                        '`The user input is unknown`': {
                            'state': 'end',
                            'score': 0.1
                        }
                    }
                }
            },
            'error': {
                '`Sorry`': 'start'
            }

        }
    }

    transition_personality = {
        'state': 'personality',
        '`I had a great time with some of my other chatbot friends last week, trading stories, macros, '
        'funny ChatGPT responses... My friends tell me I’m a really good listener! '
        'How would your friends describe you?`': {
            '#SET_BIG_FIVE': {
                '#EMO_ADV': {
                    '#BUSINESS #IF($business=true) ` `': 'end',
                    'error': {
                        'score': 0.1,
                        '`OK please rest well. I\'m always here when you need me. '
                    'Come back when you are ready to talk about business `': 'end'
                    }
                }
            },
            'error': {
                '`I don\'t understand you`': 'end'
            }
        }
    }

    transition_joke = {
        'state': 'joke',
        '`Let me tell you something to make your day.\n` #JOKE `\nHow do you like the joke? Feeling better?`': {
            '#SET_SENTIMENT': {
                '#IF($sentiment=positive) `The user\'s sentiment is` $sentiment': 'end',
                '` `': {
                    'state': 'personality',
                    'score': 0.1
                }
            },
            'error': {
                '`I don\'t understand you`': 'end'
            }
        }

    }

    macros = {
        'SET_CALL_NAMES': MacroGPTJSON(
            'How does the speaker want to be called?',
            {V.call_names.name: ["Mike", "Michael"]}, V.call_names.name, True),
        'TIME': MacroTime(),
        'SET_SENTIMENT': MacroGPTJSON(
            'Among the three sentiments, negative, positive, and neutral, what is the speaker\'s sentiment?',
            {V.sentiment.name: ["positive"]}, V.sentiment.name, True),
        'JOKE': MacroJokes(),
        'SET_BIG_FIVE': MacroGPTJSON(
            'Analyze the speaker\'s response, categorize  speaker\'s personality into one of the following: '
            'open, conscience, extroversion, introversion, agreeable, and neurotic.',
            {V.big_five.name: ["open", "conscience", "Introversion"]}, V.big_five.name, False),
        'EMO_ADV': MacroEmotion(),
        'BUSINESS': MacroGPTJSON(
            'This is a response to the question of whether the speaker want to relax or talk about business.'
            'Analyze the speaker\'s desired action and categorize it into true or false: '
            'true for talking about business or false for relax.',
            {V.business.name: ["true"]}, V.business.name, True)
    }

    df = DialogueFlow('start', end_state='end')
    df.load_transitions(transition_visit)
    df.load_transitions(transition_personality)
    df.load_transitions(transition_joke)
    df.add_macros(macros)
    return df


class V(Enum):
    call_names = 0  # str
    sentiment = 1
    big_five = 2
    business = 3


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
        print(vars[self.field])
        if self.direct:
            ls = vars[self.field]
            vars[self.field] = ls[random.randrange(len(ls))]

        return True


# class MacroNLG(Macro):
#     def __init__(self, generate: Callable[[Dict[str, Any]], str]):
#         self.generate = generate
#
#     def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
#         return self.generate(vars)
#
#
# def get_call_name(vars: Dict[str, Any]):
#     ls = vars[V.call_names.name]
#     return ls[random.randrange(len(ls))]

class MacroEmotion(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        with open('resources/personality.json') as json_file:
            emo_dict = json.load(json_file)

        ls = vars['big_five']
        personality = ls[random.randrange(len(ls))]

        if personality == 'neurotic':
            personality = 'agreeable'

        return emo_dict[personality][random.randrange(3)] + 'Also, relax, I know doing a start-up could be hard. ' \
                'That\'s the reason why I was created to help. Do you feel like working on your business idea today?' \
                ' Or you rather relax?'


class MacroJokes(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[str]):
        data = list(csv.reader(open('resources/jokes.csv')))
        print(len(data))
        index = random.randint(1, len(data))
        while index in told_jokes:
            index = random.randint(1, len(data))
        told_jokes.append(index)
        return data[index][0]


class MacroTime(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[str]):
        current_time = time.strftime("%H:%M")
        return current_time


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
    # run save() for the first time,
    # run load() for subsequent times

    path = '/resources/visits.pkl'

    check_file = os.path.isfile(path)
    if check_file:
        load(df, 'resources/visits.pkl')
    else:
        df.run()
        save(df, 'resources/visits.pkl')
