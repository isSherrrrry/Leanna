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
        '`Hi, my name is Bomo. I am here to talk about movies.\n'
        'What\'s your name? \n'
        'By the way, although I will be extremely sad:( '
        'but you can quit anytime by typing quit to me.`': {
            '#SET_CALL_NAMES': {
                '#USER_GREETING `Do you like watching movies?`': {
                    '#SET_YESNO': {
                        '#IF($yesno=yes) `Great! I like watching movies too. \n'
                        'I recently just watched a movie called '
                        'Babel.`': 'babel_start',
                        '`Okay, I am actually a big fan of movies. \n'
                        'I just watched a movie called Babel and like it very'
                        ' much!\n`': {
                            'score': 0.1,
                            'state': 'babel_start'
                        }
                    },
                    'error': {
                        '`Okay, I am actually a big fan of movies. \n'
                        'I just watched a movie called Babel and like it very'
                        ' much!\n`': 'babel_start'
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
            'state': 'depart'
        },
        'movie summary': {
            'score': 1.5,
            '`Babel is a 2006 drama film directed by Alejandro González Iñárritu.\n'
            'The movie is told through multiple interweaving storylines, set in Morocco, Japan, and the United States.\n'
            'The film explores themes of miscommunication, cultural differences, and the consequences of actions.\n'
            'The different characters are connected by a tragic incident, and their individual stories gradually unfold,\n'
            'revealing the complexities and intricacies of human relationships.\n'
            'The movie received critical acclaim and was nominated for multiple awards, '
            'including seven Academy Awards, winning for Best Original Score.\n'
            'Let\'s move on to the background story. Do you know the story of Babel Tower?`': 'babel_tower'
        }
    }

    transition_babel = {
        'state': 'babel_start',
        '`I know you have watched the movie before too. \n'
        'I like the movie very much, '
        'especially the background story of Babel Tower.\n'
        'Do you know the story of Babel Tower?\n'
        'Oh, if you would like a summary of the movie to refresh your memory, type movie summary to me directly<:`': {
            'state': 'babel_tower',
            '#SET_YESNO': {
                '#IF($yesno=yes) `I\'m glad you know it too. \n'
                'I like the concept of translating up and down too.`': 'updown',
                '`Here\'s the story of Babel Tower: \n'
                'The story of the Babel tower stems from the bible in the book of Genesis. \n'
                'At the beginning, humanity all spoke one language and because of their ease of communication,\n'
                'they decided to work together to build a tower that reaches to the heavens in order to '
                'make a name for themselves and avoid being scattered across the earth. \n'
                'God saw such work as defiance and is not pleased. \n'
                'God decides to revoke their universal language by causing them to speak different tongues '
                'so they cannot understand each other. \n'
                'This then leads to humanity being dispersed across the world in different nations.\n'
                'How do you feel about it?`': {
                    'score': 0.1,
                    'error': {
                        'Sure. I also like the concept of translating up and down too.': 'updown'
                    }
                }
            },
            'error': {
                '`Sure. Let me show you the story of Babel Tower: \n'
                'The story of the Babel tower stems from the bible in the book of Genesis. \n'
                'At the beginning, humanity all spoke one language and because of their ease of communication,\n'
                'they decided to work together to build a tower that reaches to the heavens in order to '
                'make a name for themselves and avoid being scattered across the earth. \n'
                'God saw such work as defiance and is not pleased. \n'
                'God decides to revoke their universal language by causing them to speak different tongues '
                'so they cannot understand each other. \n'
                'This then leads to humanity being dispersed across the world in different nations.\n'
                'How do you feel about it?`': {
                    'score': 0.1,
                    'error': {
                        'Sure. I also like the concept of translating up and down too.': 'updown'
                    }
                }
            }
        }
    }

    transition_updown = {
        'state': 'updown',
        '`You know, in translation, there is a concept called "translating up/down". \n'
        'Translating up is from less'
        ' powerful language to more powerful language.\n'
        'Translating down is the other way around.\nIt is taking a sophisticated language in terms of language complexity '
        'and technicality and simplifying it,\n'
        'missing the key hints of other meanings to become a literal translation.\n'
        'Do you notice any '
        'scenes where translating down affect?`': {
            '#GET_KNOW_UPDOWN': {
                '#IF($user_know=yes) `Cool! I also know an example too. \n'
                'It is a conversation between Nathan Gamble and Gael Garcia Bernal.\n'
                'Nathan said that \"My mom said Mexico is dangerous.\" and Gael said  \"Yes, it\'s full of Mexicans.\"\n'
                'This is an example of translating down because with Nathan’s quote, '
                'he is saying something that reflects American viewpoints of Mexico. \n'
                'Danger holds many meanings in English, not only is it a word that '
                'describes the potential of not being safe, \n'
                'it is also a word rooted in negative meaning and in a way, racism. \n'
                'However, when a Mexican interprets it, only the central meaning is kept without '
                'the complexity of connections to a negative word and also racism. \n'
                'Therefore, a "weird" interaction occurs between the American child who is quite serious in his statement '
                'and the Mexican relative who is quite comical in his response.\n'
                'I also know a bunch of good quotes in the movie!\n`': 'quote',

                '`Let me give you an example. \n'
                'It is a conversation between Nathan Gamble and Gael Garcia Bernal.'
                'Nathan said that \"My mom said Mexico is dangerous.\" and Gael said  \"Yes, it\'s full of Mexicans.\"\n'
                'This is an example of translating down because with Nathan’s quote, '
                'he is saying something that reflects American viewpoints of Mexico. \n'
                'Danger holds many meanings in English, not only is it a word that '
                'describes the potential of not being safe, \n'
                'it is also a word rooted in negative meaning and in a way, racism. \n'
                'However, when a Mexican interprets it, only the central meaning is kept without '
                'the complexity of connections to a negative word and also racism. \n'
                'Therefore, a "weird" interaction occurs between the American child who is quite serious in his statement '
                'and the Mexican relative who is quite comical in his response.\n'
                'Can you think of any similar scenes in the movie?`': {
                    'score': 0.2,
                    '#SET_YESNO': {
                        '#IF($yesno=yes) `Wow, you are absolutely right. The power of the language definitely '
                        'plays a role in here. This conversation is interesting. I happened to find some quotes '
                        'related to this movie.`': 'quote',
                        '`It’s ok, I have some interesting quotes related to the movie that you might find '
                        'interesting. I want to know how you think about them.\n`': {
                            'score': 0.2,
                            'state': 'quote'
                        }
                    },
                    'error': {
                        '`It’s ok, I have some interesting quotes related to the movie that you might find '
                        'interesting. I want to know how you think about them.\n`': {
                            'state': 'quote'
                        }
                    }

                }

            },
            'error': {
                '`Let me give you an example. \n'
                'It is a conversation between Nathan Gamble and Gael Garcia Bernal.'
                'Nathan said that \"My mom said Mexico is dangerous.\" and Gael said  \"Yes, it\'s full of Mexicans.\"\n'
                'This is an example of translating down because with Nathan’s quote, '
                'he is saying something that reflects American viewpoints of Mexico. \n'
                'Danger holds many meanings in English, not only is it a word that '
                'describes the potential of not being safe, \n'
                'it is also a word rooted in negative meaning and in a way, racism. \n'
                'However, when a Mexican interprets it, only the central meaning is kept without '
                'the complexity of connections to a negative word and also racism. \n'
                'Therefore, a "weird" interaction occurs between the American child who is quite serious in his statement '
                'and the Mexican relative who is quite comical in his response.\n'
                'Can you think of any similar scenes in the movie?`': {
                    'score': 0.2,
                    '#SET_YESNO': {
                        '#IF($yesno=yes) `Wow, you are absolutely right. The power of the language definitely '
                        'plays a role in here. This conversation is interesting.\n'
                        'I happened to find some quotes '
                        'related to this movie.\n`': 'quote',
                        '`It’s ok, I have some interesting quotes related to the movie that you might find '
                        'interesting. I want to know how you think about them.`': {
                            'score': 0.2,
                            'state': 'quote'
                        }
                    },
                    'error': {
                        '`It’s ok, I have some interesting quotes related to the movie that you might find '
                        'interesting. I want to know how you think about them.\n`': {
                            'state': 'quote'
                        }
                    }

                }

            }
        }

    }

    transition_quotes = {
        'state': 'quote',
        '#GET_QUOTE `What do you think of this quote?`': {
            '#QUOTE_ANS': {
                '#IF($yesno=yes) `Yeah, I totally agree` #GET_RESPONSE `Would you like another quote?`': {
                    'state': 'more_quote',
                    '#SET_YESNO': {
                        '#IF($yesno=yes) `Sure, here is another one.\n`': 'quote',
                        'Okay': {
                            'score': 0.1,
                            'state': 'depart'
                        }
                    },
                    'error': {
                        'Let\'s try again. Would you like another quote?': 'more_quote'
                    }
                },
                '`Of course.\n` #GET_RESPONSE `Would you like another quote?`': 'more_quote'
            },
            'error': {
                'Cool! Would you like another quote?': 'more_quote'
            }
        }
    }

    transition_depart = {
        'state': 'depart',
        '`It was nice talking to you! I hope you have a wonderful day. Goodbye.`': 'end'
    }

    macros = {
        'SET_CALL_NAMES': MacroGPTJSON(
            'What is speaker\'s name?, respond in lower case',
            {V.call_names.name: ["mike"]}, V.call_names.name, True),
        'SET_YESNO': MacroGPTJSON(
            'The speaker is answering a yes/no question. Categorize his response into yes or no',
            {V.yesno.name: "yes"}, V.yesno.name, True),
        'GET_KNOW_UPDOWN': MacroGPTJSON(
            'Does the user mentions a scene in the movie Babel and relates to the term of translating down?'
            'Categorize the response into yes or no',
            {V.user_know.name: "yes"}, V.user_know.name, True),
        'QUOTE_ANS': MacroGPTJSON(
            'Does speaker refer to a specific scene in the movie Babel? Categorize the response into yes or no',
            {V.yesno.name: "yes"}, V.yesno.name, True),
        'USER_GREETING': MacroUser(),
        'GET_QUOTE': MacroQuote(),
        'GET_RESPONSE': MacroResponse()
    }

    df = DialogueFlow('start', end_state='end')
    df.load_global_nlu(global_transition)
    df.load_transitions(transition_greeting)
    df.load_transitions(transition_babel)
    df.load_transitions(transition_updown)
    df.load_transitions(transition_quotes)
    df.load_transitions(transition_depart)
    df.add_macros(macros)
    return df

class V(Enum):
    call_names = 0 # str
    yesno = 1 # str
    user_know = 2
    quotes = 3 # list
    response = 4 # str


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
            if isinstance(ls, list):
                vars[self.field] = ls[random.randrange(len(ls))]


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

class MacroQuote(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        with open('../resources/quotes.json') as json_file:
            quotes = json.load(json_file)
        out_quote, response = random.choice(list(quotes.items()))
        if 'quotes' in vars:
            while out_quote in vars['quotes']:
                out_quote, response = random.choice(list(quotes.items()))
            vars['quotes'].append(out_quote)
        else:
            vars['quotes'] = [out_quote]
        vars['response'] = response
        return '"' + out_quote + '"'

class MacroResponse(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        if 'response' in vars:
            return vars['response']
        else:
            return


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
