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
import businesModel

PATH_API_KEY = '../resources/openai_api.txt'
openai.api_key_path = PATH_API_KEY

told_jokes = []


def visits() -> DialogueFlow:
    transition_visit = {
        'state': 'start',
        '`Hi, I\'m Leanna, your personal start-up consultant. At` #TIME `, I had the pleasure to meet '
        ' \n With time as our guide, our encounter was meant to be. May I know the name of future business tycoon?`': {
            '#SET_CALL_NAMES': {
                '#USER_PROFILE': {
                    '#SET_SENTIMENT': {
                        '#IF($sentiment=positive) `Wow, that sounds awesome! `': 'business_start',
                        '#IF($sentiment=neutral) ` `': 'joke',
                        '#IF($sentiment=negative) ` `': 'personality',
                        '` `': {
                            'state': 'business_start',
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
        '#IF($VISIT=multi) #EMO_ADV': {
            '#BUSINESS': {
                '#IF($business=true) ` `': 'business_start',
                '`OK please rest well. I\'m always here when you need me. '
                'Come back when you are ready to talk about business `': {
                    'score': 0.1,
                    'state': 'end'
                }
            }
        },
        '`I had a great time with some of my other chatbot friends last week, trading stories, macros, '
        'funny ChatGPT responses... My friends tell me I’m a really good listener! '
        'How would your friends describe you?`': {
            'score': 0.5,
            '#SET_BIG_FIVE': {
                '#EMO_ADV': {
                    '#BUSINESS': {
                        '#IF($business=true) ` `': 'business_start',
                        '`OK please rest well. I\'m always here when you need me. '
                        'Come back when you are ready to talk about business `': {
                            'score': 0.1,
                            'state': 'end'
                        }
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
            '#JOKE_FEEL #SET_SENTIMENT': {
                '#IF($joke_feel=yes) ` `': 'joke',
                '#IF($sentiment=positive) ` `': 'business_start',
                '` `': {
                    'state': 'personality',
                    'score': 0.5
                }
            },
            'error': {
                '`I don\'t understand you`': 'end'
            }
        }

    }

    global_transition = {
        'quit': {
            'score': 1.5,
            'state': 'business_end'
        }
    }

    transition_business = {
        'state': 'business_start',
        '`I am so excited to talk to you about your business. \n'
        'What is its name and are you selling a product or a service? \n'
        'A product is something that people can use and is tangible. \n'
        'Think of a computer or software such as google drive. \n'
        'A service is something you can provide or perform for another person. \n'
        'For example, a hair salon or a restaurant service. And what industry is your business in?`': {
            'state': 'bus_name_indu',
            '#SET_BUS_NAME': {
                '#SAVE_BUS_NAME `Thanks for letting me know! That sounds super exciting. \n'
                '`#GET_BUS_NAME`is sure to change the world one day as a fantastic`#GET_INDU`industry. \n'
                'My role is to help you brainstorm on fuzzy ideas of your business so that you \n'
                'can have a tangible pitch by the end of our conversation. \n'
                'Is there a particular problem area you would like to brainstorm about first?`': {
                    'state': 'big_small_cat',
                    '#SET_BIG_SAMLL_CATE': {
                        '`Cool! Let\'s talk about`#GET_SMALL_CAT`in`#GET_BIG_CAT`category!`': 'business_sub'
                    },
                    'error': {
                        '`Cool!`#GET_AVAIL_CATE`Does that sound good?`': {
                            '#SET_YES_NO': {
                                '#IF($sounds_yesno=yes)`Cool! Let\'s start.`': 'business_sub',
                                '`Okay, what topic you want to start with? '
                                'We can talk about product innovation, customer relationships, '
                                'and infrastructure management. `': {
                                    'score': 0.4,
                                    'state': 'big_small_cat'
                                }
                            },
                            'error': {
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
        '`Thanks! Have a good one.`': 'end',
        '#IF($bus_true) `Thank you so much for talking with me. This interaction has been fabulous. '
        'I get to know more about`#GET_BUS_NAME`and it was awesome!'
        'Would you like a summary of what we talked about? `': {
            '#SET_YES_NO': {
                'Here\'s the summary. Thanks for using Leanna! \n`#GET_SUMMARY`': 'end'
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
                '#IF($user_know=yes)': {
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
        '#IF($all) `Thanks, I have recorded it to the business plan.` #UPDATE_BP': 'business_end',
        '`Thanks, I have recorded it to the business plan. What do you want to talk about next?` #UPDATE_BP': {
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
        'SET_CALL_NAMES': MacroGPTJSON(
            'What is speaker\'s name?, respond in lower case',
            {V.call_names.name: ["mike"]}, V.call_names.name, True),
        'TIME': MacroTime(),
        'USER_PROFILE': MacroUser(),
        'SET_SENTIMENT': MacroGPTJSON(
            'Among the three sentiments, negative, positive, and neutral, what is the speaker\'s sentiment?',
            {V.sentiment.name: ["positive"]}, V.sentiment.name, True),
        'JOKE': MacroJokes(),
        'SET_BIG_FIVE': MacroGPTJSON(
            'Analyze the speaker\'s response, categorize  speaker\'s personality into one of the following: '
            'open, conscience, extroversion, introversion, agreeable, and neurotic.',
            {V.big_five.name: ["open", "conscience", "extroversion"]}, V.big_five.name, False),
        'EMO_ADV': MacroEmotion(),
        'BUSINESS': MacroGPTJSON(
            'This is a response to the question of whether the speaker want to relax or talk about business.'
            'Analyze the speaker\'s desired action and categorize it into true or false: '
            'true for talking about business or false for relax.',
            {V.business.name: ["false"]}, V.business.name, True),
        'JOKE_FEEL': MacroGPTJSON(
            'Is the user requesting more jokes? Answer in yes or no',
            {V.joke_feel.name: ["yes"]}, V.joke_feel.name, True),

        'SET_BUS_NAME': MacroGPTJSON_BUS(
            'Please find the person\'s business name and the industry',
            {V.business_name.name: "Microsoft", V.industry.name: "technology"},
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
            'Please only return the large category and small category, and nothing else. ',
            {V.large_cat.name: "product innovation", V.small_cat.name: "customer needs"},
            set_cat_name
        ),
        'SET_YES_NO': MacroGPTJSON_BUS(
            'Please find out if the speaker wants to talk about this topic.'
            'If the speaker wants to, please only return yes.'
            'If the speaker does not want to, please only return no',
            {V.sounds_yesno.name: "yes"},
            set_yesno
        ),
        'SET_USER_KNOW': MacroGPTJSON_BUS(
            'Does the user answer the question well and adequate? Provide binary answer, yes or no.'
            'Please also provide the entire input as the next output. '
            'Phrase them into a json, with yes/no as the first element, and the input as the second;'
            'Only return the json file, please. thanks',
            {V.user_know.name: "yes", V.ans_bp.name: "here's the entire input"},
            set_know
        ),
        'SET_IDEA_EX': MacroGPTJSON_BP(
            'Is the user providing an business idea, requesting another example or wanting to move on to next topic? '
            'Please choose the answer from the following: businessplan, moveon, example.'
            'Please also provide the entire input as the next output. '
            'Phrase them into a json, with the categories (businessplan, moveon, example) as the first element, '
            'and the input as the second; Only return the json file, please. thanks',
            {V.ex_choice.name: "businessplan", V.ex_bp.name: "here's the entire input"},
            set_ex_idea
        ),
        'GET_BUS_NAME': MacroNLG(get_bus_name),
        'GET_INDU': MacroNLG(get_industry),
        'GET_BIG_CAT': MacroNLG(get_big_cat),
        'GET_SMALL_CAT': MacroNLG(get_small_cat),
        'GET_QUESTION': MacroGetQuestion(),
        'GET_EXAMPLE': MacroGetExample(),
        'GET_AVAIL_CATE': MacroGetAvailCat(),
        'UPDATE_BP': MacroUpdateResponses(),
        'GET_SUMMARY': MacroPrintResponses(),
        'SAVE_BUS_NAME': MacroSave('business_name')
    }

    df = DialogueFlow('start', end_state='end')
    df.load_transitions(transition_visit)
    df.load_transitions(transition_personality)
    df.load_transitions(transition_joke)
    df.load_global_nlu(global_transition)
    df.load_transitions(transition_business)
    df.load_transitions(transition_end)
    df.load_transitions(transition_question)
    df.load_transitions(transition_negative)
    df.load_transitions(transition_positive)
    df.add_macros(macros)
    return df


class V(Enum):
    call_names = 0  # str
    sentiment = 1
    big_five = 2
    business = 3
    joke_feel = 4
    business_name = 5
    industry = 6
    large_cat = 7
    small_cat = 8
    sounds_yesno = 9
    user_know = 10
    ans_bp = 11
    ex_choice = 12
    ex_bp = 13


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


class MacroUser(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        name = vars['call_names'].lower()
        if name not in vars:
            vars[name] = {}
            return 'Nice to meet you ' + vars['call_names'] + ' Before we dive into business, ' \
                                                              'I want to know how you are doing. Do you mind sharing to me your most exciting day in this week?'
        else:
            vars['VISIT'] = 'multi'
            return 'Hi ' + vars['call_names'] + ', nice to see you again. How\'s your weekend?'

class MacroSave(Macro):
    def __init__(self, new_stuff):
        self.save = new_stuff
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        name = vars['call_names'].lower()
        if name not in vars:
            vars[name] = {}
        vars[name].update({self.save: vars[self.save]})
        # print(vars[name][self.save])



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
            return False
        # print(d)
        if self.set_variables:
            self.set_variables(vars, d)
        else:
            vars.update(d)
        if self.direct:
            ls = vars[self.field]
            vars[self.field] = ls[random.randrange(len(ls))]
        # print(self.field)
        # print(vars[self.field])

        return True


class MacroEmotion(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        with open('../resources/personality.json') as json_file:
            emo_dict = json.load(json_file)
        personality = None
        if 'big_five' not in vars[vars['call_names']]:
            if 'big_five' in vars:
                ls = vars['big_five']
                personality = ls[random.randrange(len(ls))]
                vars[vars['call_names']]['big_five'] = ls
        else:
            ls = vars[vars['call_names']]['big_five']
            personality = ls[random.randrange(len(ls))]

        if personality == 'neurotic':
            personality = 'agreeable'

        if personality:
            return emo_dict[personality][random.randrange(3)] + 'Also, relax, I know doing a start-up could be hard. ' \
                                                            'That\'s the reason why I was created to help. Do you feel like working on your business idea today?' \
                                                            ' Or you rather relax?'
        else:
            return

class MacroJokes(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[str]):
        data = list(csv.reader(open('../resources/jokes.csv')))
        index = random.randint(1, len(data))
        while index in told_jokes:
            index = random.randint(1, len(data))
        told_jokes.append(index)
        return data[index][0]


class MacroTime(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[str]):
        current_time = time.strftime("%H:%M")
        return current_time


class MacroGetQuestion(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        small_cat = vars[vars['call_names']].get('small_cat')
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


class MacroPrintResponses(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        user_responses = vars.get('user_responses', {})
        response_text = ""

        for small_cat, user_response in user_responses.items():
            response_text += f"{small_cat}: {user_response}\n\n"

        return response_text.strip()


class MacroUpdateResponses(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        small_cat = vars[vars['call_names']].get('small_cat')
        ans_bp = vars[vars['call_names']].get('ans_bp')

        user_responses = vars[vars['call_names']].get('user_responses', {})

        if small_cat and ans_bp:
            user_responses[small_cat] = ans_bp
            vars[vars['call_names']]['user_responses'] = user_responses

        return True


class MacroGetAvailCat(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        user_responses = vars[vars['call_names']].get('user_responses', {})
        talked_subsecs = set(user_responses.keys())

        all_subsecs = []  # List of all possible subsec values
        subsec_to_section = {}  # Mapping of subsec values to their corresponding section

        with open('../resources/data.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                subsec = row['subsec']
                section = row['Section']
                all_subsecs.append(subsec)
                subsec_to_section[subsec] = section

        available_subsecs = list(set(all_subsecs) - talked_subsecs)

        if not available_subsecs:
            return "Sorry, we have already covered all available subcategories."

        chosen_subsec = random.choice(available_subsecs) if available_subsecs else None
        if chosen_subsec is None:
            return "Unfortunately, there are no more subcategories to discuss."

        chosen_large_cat = subsec_to_section[chosen_subsec]
        vars[vars['call_names']]['small_cat'] = chosen_subsec
        vars[vars['call_names']]['large_cat'] = chosen_large_cat
        vars[vars['call_names']]['large_cat_name'] = chosen_large_cat

        return f"I can start you with {chosen_large_cat} in the {chosen_subsec}"

class MacroGetExample(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        small_cat = vars[vars['call_names']].get('small_cat')

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
        used_examples = vars[vars['call_names']].get(used_examples_key, [])

        remaining_examples = [example for example in available_examples if example not in used_examples]

        if len(remaining_examples) == 0:
            return "Sorry, I don't have more examples."

        selected_example = remaining_examples[0]  # Select the first remaining example
        used_examples.append(selected_example)
        vars[used_examples_key] = used_examples

        user_responses = vars.get('user_responses', {})

        if len(user_responses) != 0:
            if user_responses:
                encourage = random.choice(list(user_responses.keys()))
            else:
                encourage = ''
            return 'Here is an ' + vars['small_cat'] + ' example that might help you \n' + \
                selected_example + ' What do you think about your business plan in this topic now?'
        else:
            return 'Here is an ' + vars['small_cat'] + 'example that might help you \n' + \
                selected_example + ' What do you think about your business plan in this topic now?'


class MacroGPTJSON_BUS(Macro):
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
            self.set_variables(vars[vars['call_names']], d)
        else:
            vars[vars['call_names']].update(d)

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
            self.set_variables(vars[vars['call_names']], d)
        else:
            vars[vars['call_names']].update(d)

        if d['ex_choice'] == 'businessplan':
            vars[vars['call_names']][V.ans_bp.name] = d[V.ex_bp.name]

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
            # print(f'Invalid: {output}')
            return False

        if d is None:
            return False

        if self.set_variables:
            self.set_variables(vars[vars['call_names']], d)
        else:
            vars[vars['call_names']].update(d)

        vars['bus_true'] = True

        if (d['small_cat'] is None or d['small_cat'] == "N/A") and d['large_cat'] is not None:
            user_responses = vars[vars['call_names']].get('user_responses', {})
            talked_subsecs = set(user_responses.keys())

            all_subsecs = []  # List of all possible subsec values

            with open('../resources/data.csv', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    subsec = row['subsec']
                    section = row['Section']
                    if section == d['large_cat']:
                        all_subsecs.append(subsec)

            available_subsecs = list(set(all_subsecs) - talked_subsecs)

            chosen_subsec = random.choice(available_subsecs) if available_subsecs else None

            vars[vars['call_names']][V.small_cat.name] = chosen_subsec

        return True


class MacroNLG(Macro):
    def __init__(self, generate: Callable[[Dict[str, Any]], str]):
        self.generate = generate

    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        return self.generate(vars)


def get_bus_name(vars: Dict[str, Any]):
    if V.business_name.name in vars:
        ls = vars[vars['call_names']][V.business_name.name]
        if ls is not None:
            return ls
    return "Your business"



def get_industry(vars: Dict[str, Any]):
    ls = vars[vars['call_names']][V.industry.name]
    return ls


def get_big_cat(vars: Dict[str, Any]):
    ls = vars[vars['call_names']]["large_cat"]
    return ls


def get_small_cat(vars: Dict[str, Any]):
    ls = vars[vars['call_names']]["small_cat"]
    return ls


def set_bus_name(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[vars['call_names']][V.business_name.name] = user[V.business_name.name]
    vars[vars['call_names']][V.industry.name] = user[V.industry.name]
    print("hello")
    print(vars[vars['call_names']][V.industry.name])


def set_cat_name(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[vars['call_names']][V.large_cat.name] = user[V.large_cat.name]
    vars[vars['call_names']][V.small_cat.name] = user[V.small_cat.name]


def set_yesno(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[V.sounds_yesno.name] = user[V.sounds_yesno.name]


def set_know(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[V.user_know.name] = user[V.user_know.name]
    vars[vars['call_names']][V.ans_bp.name] = user[V.ans_bp.name]


def set_ex_idea(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[vars['call_names']][V.ex_choice.name] = user[V.ex_choice.name]
    vars[vars['call_names']][V.ex_bp.name] = user[V.ex_bp.name]


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
