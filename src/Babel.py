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

PATH_API_KEY = '../resources/openai_api.txt'
openai.api_key_path = PATH_API_KEY


def visits() -> DialogueFlow:
    transition_greeting = {
        'state': 'start',
        '`Hi, my name is Bomo. I am here to talk about movies. \n '
        'What\'s your name? \n '
        'By the way, although I will be extremely sad:( '
        'but you can quit anytime by typing quit to me.`': {
            '#SET_CALL_NAMES': {
                '#USER_GREETING `Do you like watching movies?`': {
                    '#YESNO': {
                        '#IF($yesno=yes) `Great! I like watching movies too. \n '
                        'I recently just watched a movie called '
                        'Babel. `': 'babel_start',
                        '`Okay, I am actually a big fan of movies. \n '
                        'I just watched a movie called Babel and like it very'
                        ' much!`': {
                            'score': 0.1,
                            'state': 'babel_start'
                        }
                    }
                }
            },
            'error': {
                '`Sorry, I did not get that. Could you tell me one more time?`': 'start'
            }
        }
    }

    global_transition = {
        'quit': {
            'score': 1.5,
            'state': 'business_end'
        }
    }

    transition_babel = {
        'state': 'babel_start',
        '`I know you have watched the movie before. \n '
        'I like the movie very much, '
        'especially the background story of Babel Tower. \n'
        ' Do you know the story of Babel Tower?`': {
            '#YESNO': {
                '#IF($yesno=yes) `I\'m glad you know it too. \n '
                'I like the concept of translating up and down too.`': 'updown',
                '`Elaborate the story of Babel Tower. \n'
                ' I like the concept of translating up and down too.`': {
                    'score': 0.1,
                    'state': 'updown'
                }
            }
        }
    }

    transition_updown = {
        'state': 'updown',
        '`You know, in translation, there is a concept called "translating up/down". \n '
        'Translating up is from less'
        ' powerful language to more powerful language. \n'
        ' Translating down is the other way around. Do you notice any '
        'scenes where translating down affect?`': {
            '#GET_KNOW_UPDOWN': {
                '#IF($user_know=yes) `THE PHRASE`': 'end',
                '`THE PHRASE. Can you think of any similar scenes in the movie?`': {
                    'score': 0.2,
                    '#YESNO': {
                        '#IF(#yesno=yes) `Wow, you are absolutely right. The power of the language definitely '
                        'plays a role in here. This conversation is interesting. I happened to find some quotes '
                        'related to this movie.`': 'end',
                        '`It’s ok, I have some interesting quotes related to the movie that you might find '
                        'interesting. I want to know how you think about them.`': {
                            'score': 0.2,
                            'state': 'end'
                        }
                    }

                }

            }
        }

    }

    macros = {
        'SET_CALL_NAMES': MacroGPTJSON(
            'What is speaker\'s name?, respond in lower case',
            {V.call_names.name: ["mike"]}, V.call_names.name, True),
        'YESNO': MacroGPTJSON(
            'The speaker is answering a yes/no question. Categorize his response into yes or no',
            {V.yesno.name: "yes"}, V.yesno.name, True),
        'GET_KNOW_UPDOWN': MacroGPTJSON(
            'Does the user mentions a scene in the movie Babel and relates to the term of translating down?'
            'Categorize the response into yes or no',
            {V.user_know.name: "yes"}, V.user_know.name, True),
        'USER_GREETING': MacroUser()
    }

    df = DialogueFlow('start', end_state='end')
    df.load_global_nlu(global_transition)
    df.load_transitions(transition_greeting)
    df.load_transitions(transition_babel)
    df.load_transitions(transition_updown)
    df.add_macros(macros)
    return df

class V(Enum):
    call_names = 0 #str
    yesno = 1 #str
    user_know = 2


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

        vars[self.field] = None

        if not output:
            return False

        try:
            d = json.loads(output)
        except JSONDecodeError:
            return False
        if self.set_variables:
            self.set_variables(vars, d)
        else:
            vars.update(d)
        if self.direct:
            ls = vars[self.field]
            vars[self.field] = ls[random.randrange(len(ls))]

        print(vars) # for debug

        return True

class MacroUser(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        name = vars['call_names'].lower()
        if name not in vars:
            vars['VISIT'] = 'first'
            vars[name] = {}
            return 'Nice to meet you, ' + vars['call_names'] + '.'
        else:
            vars['VISIT'] = 'multi'
            if 'prev_adv' in vars[vars['call_names']]:
                return 'Hi ' + vars[
                    'call_names'] + ', nice to see you again. Did you try the advice I gave you last time? How was it?'
            else:
                return 'Hi ' + vars['call_names'] + ', nice to see you again.'


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


def save(df: DialogueFlow, varfile: str):
    d = {k: v for k, v in df.vars().items() if not k.startswith('_')}
    pickle.dump(d, open(varfile, 'wb'))


def load(df: DialogueFlow, varfile: str):
    d = pickle.load(open(varfile, 'rb'))
    df.vars().update(d)


if __name__ == '__main__':
    df = visits()
    path = '../resources/Babel.pkl'
    check_file = os.path.isfile(path)
    if check_file:
        load(df, path)
    df.run()
    save(df, path)
