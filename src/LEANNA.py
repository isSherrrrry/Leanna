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

told_jokes = []
talked_sub = []
asw_cat = []

# language: not natural. too blunt. no introduction. no quit. error state not handled
# next step
# branch out the returning business name

# comment

def visits() -> DialogueFlow:
    transition_visit = {
        'state': 'start',
        "`Hi, I\'m Leanna, your personal start-up consultant. I had the pleasure to meet you at `#TIME` \n "
        "May I know your name please? Also, I won\'t be offended anytime if you want to take a break."
        " Just type 'quit', we can pick up where we left off next time`": {
            '#SET_CALL_NAMES': {
                '#USER_PROFILE': {
                    '#SET_SENTIMENT': {
                        '#IF($sentiment=positive) #DEL_ADV ` `': 'emobus',
                        '#IF($sentiment=neutral) #DEL_ADV ` `': 'joke',
                        '#IF($sentiment=negative) ` I\'m sorry to hear that. `': 'personality',
                        '` `': {
                            'state': 'business_start',
                            'score': 0.1
                        }
                    },
                    'error': {
                        'state': 'joke'
                    }
                }
            },
            'error': {
                '`I\'m not sure I understood. Let\'s try this again`': 'start'
            }
        }
    }

    transition_emobus = {
        'state': 'emobus',
        '#IF($bus_true=False) `We didn\'t get to business conversation last time. So let\'t dive right in today\n`': {
            'score': 0.7,
            'state': 'business_start'
        },
        '#IF($VISIT=multi) `Hi, we were discussing your `#GET_BUS_NAME`'
        'Are you still working on the same business idea?`': {
            'score': 0.5,
            '#SAME_BUS': {
                '#IF($same_bus=new) #DEL_PROFILE `Sorry to hear that, what made you '
                'decide to give up your old business idea?`': {
                    'error': {
                        '`What you have said is quite common for college entrepreneurs. Things happen but you guys'
                        ' are always good at discovering new ideas. \n'
                        'I\'m really interested in your new business. '
                        'What is its name and in what industry?`': 'bus_name_indu'
                    }
                },
                '#talked_sub': {
                    'score': 0.4,
                    'state': 'big_small_cat'
                }
            },
            'error': {
                '`I actually think` #GET_BUS_NAME is quite interesting. Do you want to keep working on it?': {
                    '#SET_YES_NO_B': {
                        '#IF($prev_bus=yes)': {
                            'state': 'business_part'
                        },
                        '#DEL_PROFILE `Sorry to hear that, but I will help you do this all over again.\n'
                        'What is the name of your new business and what industry is it in?`': 'bus_name_indu'
                    }
                }

            }
        },
        '`Glad to hear that. So`$call_names`, how far along have you gone with your business idea?`': {
            'score': 0.4,
            'error': {
                '`Good to her that! Let me help you further your entrepreneurial journey\n`': 'business_start'
            }
        }
    }

    transition_personality = {
        'state': 'personality',
        '#IF(#CHAR_CHECK) #EMO_ADV': {
            '#BUSINESS': {
                '#IF($business=true) ` `': 'emobus',
                '`No need to push it, please rest well. I\'m always here when you need me. '
                'Come back when you are ready to talk about business. `': {
                    'state': 'end'
                }
            },
            'error': {
                '`No need to push it, I understand college students are busy\n'
                'Building a startup is a long process. Go and recharge today and we can talk later`': 'end'
            }
        },
        '`I want to get to know you better. Maybe I can give a suggestion that would help relieve some of your stress. '
        'How would you describe your personality, or maybe your work style?`': {
            'score': 0.4,
            '#SET_BIG_FIVE': {
                '#EMO_ADV': {
                    '#BUSINESS': {
                        '#IF($business=true) ` `': 'emobus',
                        '`OK please rest well. I\'m always here when you need me. '
                        'Come back when you are ready to talk about business. `': {
                            'score': 0.1,
                            'state': 'end'
                        }
                    },
                    'error': {
                        '`No need to push it, I understand college students are busy\n'
                        'Building a startup is a long process. Go and recharge today and we can talk later`': 'end'
                    }
                }
            },
            'error': {
                '`That\'s interesting to hear. \n`': 'business_start'
            }
        }
    }

    transition_joke = {
        'state': 'joke',
        '#IF($more_jokes=true) `Here comes another one. \n` #JOKE `\n'
        'How do you like it? Feeling better?` #SET($more_jokes=false)': {
            'state': 'joke_next'
        },
        '`Let me tell you something to brighten your day.\n` #JOKE `\n'
        'How do you like it? Feeling better?`': {
            'state': 'joke_next',
            'score': 0.4,
            '#JOKE_FEEL #SET_SENTIMENT': {
                '#IF($joke_feel=yes) #SET($more_jokes=true) ` `': 'joke',
                '#IF($sentiment=positive) ` `': {
                    'score': 0.7,
                    'state': 'business_start'
                },
                '` `': {
                    'state': 'personality',
                    'score': 0.5
                }
            },
            'error': {
                '`I hope I get you to chuckle. Having a optimistic attitude on your entrepreneurial '
                'journey is very important. OK!`': 'business_start'
            }
        }

    }

    global_transition = {
        'quit': {
            'score': 1.5,
            'state': 'business_end'
        },
        '[{next topic, different topic}]': {
            'score': 1.5,
            '`Glad you feel confident on this part. What topics do you want to discuss next? '
            'I can pick for you if you need it.`': {
                'state': 'big_small_cat'
            }
        }
    }

    transition_business = {
        'state': 'business_start',
        '`I am so excited to talk to you about your business. '
        'What is its name? And what industry is your business in?`': {
            'score': 0.4,
            'state': 'bus_name_indu',
            '#SET_BUS_NAME': {
                '`Thanks for letting me know! That sounds super exciting. \n'
                'My role is to help you brainstorm by asking you critical business elements for a start up \n'
                'so that you can have a tangible pitch by the end of our conversation. \n'
                'I have prepared questions and examples for 23 business concepts\nAfter going through them, '
                '`#GET_BUS_NAME`is sure to change the world one day as a fantastic`#GET_INDU`company. \n'
                'At the end of the session, I will forward you to a business expert to evaluate your plan.\n'
                'What business concepts do you want to start with?'
                'If you are not sure where to start, we can start with` #GET_AVAIL_CATE `. Is that ok for you?`': {
                    'state': 'big_small_cat',
                    '#SET_BIG_SAMLL_CATE': {
                        '` `': 'business_sub'
                    },
                    'error': {
                        '` `': 'business_sub'
                    }
                }
            },
            'error': {
                '`It is OK if you haven\'t named your business yet. Take your time to think. We can brainstorm '
                'your business plan today without it\n'
                'My role is to help you brainstorm by asking you critical business element for a start up \n'
                'so that you can have a tangible pitch by the end of our conversation. \n'
                'I have prepared questions and examples for 23 business concepts\nAfter going through them, '
                '`#GET_BUS_NAME`is sure to change the world one day as a fantastic`#GET_INDU`company. \n'
                'And I will forward you to another business expert to evaluate your business plan at the end\n'
                'I can start you with `#GET_AVAIL_CATE` or what business concept you would like to '
                'brainstorm about first?`': 'big_small_cat'
            }
        }
    }

    transition_end = {
        'state': 'business_end',
        '#IF($bus_true=True) `Thank you so much for talking with me. This interaction has been fabulous. \n'
        'I got to know more about`#GET_BUS_NAME`and it was awesome! '
        'I hope you have thought about more aspects of your business by brainstorming with my questions.\n'
        'Would you like a summary of what we talked about? `': {
            '#SET_YES_NO_S': {
                '#IF($summary=yes) `Here\'s your summary \n `#GET_SUMMARY` '
                'Thank you! and It\'s very nice to meet you`$call_names': 'end',
                '`Alright. Thanks for using Leanna! Please come back when you have more ideas. '
                'We can pick up where we have left`': {
                    'score': 0.2,
                    'state': 'end'
                }
            },
            'error': {
                '`Here\'s your summary \n `#GET_SUMMARY` Thank you! and It\'s very nice to meet you`$call_names': 'end'
            }
        },
        '`Although we didn\'t get to any business conversation, it is a pleasure to meet you` '
        '$call_names `. Have a good one.`': {
            'score': 0.2,
            'state': 'end'
        }
    }

    transition_question = {
        'state': 'business_sub',
        '#IF($VISIT=multi) #CHECK_TALK': {
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
        },
        '`Let\'s talk about`#GET_SMALL_CAT`in` #GET_BIG_CAT `. When it comes to`#GET_SMALL_CAT`,'
        'it is important to ask yourself\n` #GET_QUESTION': {
            'score': 0.4,
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
                'state': 'business_neg'
            }
        }
    }

    # 同一次visit无法重复讨论一个topic
    transition_positive = {
        'state': 'business_pos',
        '#IF($all) `Good idea, that sounds like a tangible plan to me. I have recorded it to the our meeting notes. '
        'Congratulations, we have touched all critical '
        'business topics for a start up to succeed. Don\'t forget me if you become a business tycoon one day!` '
        '#UPDATE_BP': 'business_end',
        '`Good idea, that sounds like a tangible plan to me. I have recorded it to the meeting notes.'
        'We have `#GET_PROG` topics to go. \n What do you want to talk about next? Anything related to product innovation,'
        ' customer relationships, and infrastructure management can be beneficial to` #GET_BUS_NAME`. '
        'I can recommend one for you as well` #UPDATE_BP': {
            'state': 'big_small_cat',
            'score': 0.2
        }
    }
    transition_negative = {
        'state': 'business_neg',
        '#GET_EXAMPLE': {
            '#SET_IDEA_EX': {
                '#IF($ex_choice=yes)': {
                    'state': 'business_neg',
                    'score': 0.2
                },
                '#IF($ex_choice=no) `Glad you feel better about this question. Let\'s try answering the question again? '
                'We can also move on to the next topic if you don\'t think this business area matters to`#GET_BUS_NAME` '
                'very much`': {
                    'score': 0.2,
                    '#MOVE_ON': {
                        '#IF($moveon_choice=yes) `Sure. Let\'s move on to the next topic. Is there any particular topic you have in mind? '
                        'I can pick one if you don\'t have one in mind. Or, if you want time to think about it, '
                        'you can type \'quit\' to end our conversation and come back later.`': 'big_small_cat',
                        '` `': {
                            'score': 0.2,
                            'state': 'business_pos'
                        }
                    }
                },
                '`Glad you feel confident on this part. What topics do you want to discuss next? I can pick for '
                'you if you need it. Or, if you want time to think about it, you can type \'quit\' to end our '
                'conversation and come back later.`': {
                    'state': 'big_small_cat',
                    'score': 0.1
                }
            },
            'error': {
                '`Glad you feel good on this part. What topics do you want to discuss next? I can pick for '
                'you if you need it. Or, if you want time to think about it, you can type \'quit\' to end our '
                'conversation and come back later.`': 'big_small_cat'
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
        'SET_FEEL': MacroGPTJSON(
            'Is the speaker feeling better? Respond in yes or no',
            {V.feel.name: ["yes"]}, V.feel.name, True),
        'JOKE': MacroJokes(),
        'CHAR_CHECK': MacroCharCheck(),
        'SET_BIG_FIVE': MacroGPTJSON(
            'Analyze the speaker\'s response, categorize  speaker\'s personality into one of the following: '
            'open, conscience, extroversion, introversion, agreeable, and neurotic.',
            {V.big_five.name: ["open", "conscience", "extroversion"]}, V.big_five.name, False),
        'EMO_ADV': MacroEmotion(),
        'DEL_ADV': MacroDelAdv(),
        'BUSINESS': MacroGPTJSON(
            'This is a response to the question of whether the speaker want to relax or talk about business.'
            'Analyze the speaker\'s desired action and categorize it into true or false: '
            'true for talking about business or false for relax.',
            {V.business.name: ["false"]}, V.business.name, True),
        'JOKE_FEEL': MacroGPTJSON(
            'Is the user requesting more jokes? Answer in yes or no. If the user does not specify, then answer no ',
            {V.joke_feel.name: ["no"]}, V.joke_feel.name, True),
        'SET_BUS_EMO': MacroGPTJSON(
            'Categorize speaker\'s response based on if he is struggling. Positive for no trouble and negative for having trouble.',
            {V.sentiment.name: ["positive"]}, V.sentiment.name, True),
        'SET_BUS_NAME': MacroGPTJSON_BUS(
            'Please find the person\'s business name and the industry',
            {V.business_name.name: "Microsoft", V.industry.name: "technology"},
            set_bus_name
        ),
        'SET_BIG_SAMLL_CATE': MacroGPTJSON_BS(
            'Please classify the input sentence into the following three large categories '
            'and the corresponding small category within each large category. If small catgeory does not exist, leave it blank: '
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
        'MOVE_ON': MacroGPTJSON_BP(
            'Does the input sentence indicates that the user wants to move on to next topic? '
            'Please only return binary answer, yes or no, to the first variable in json. Please also return the entire input sentence to the second variable',
            {V.moveon_choice.name: "yes", V.ans_bp.name: "here's the entire input"},
            set_move_on
        ),
        'SET_YES_NO_Topic': MacroGPTJSON_BUS_1(
            'Does the user want to continue on the topic? Please only return yes or no to this question',
            {V.sounds_yesno.name: "yes"},
            set_yesno
        ),
        'SET_USER_KNOW': MacroGPTJSON_BUS_SETKNOW(
            'Is the user\'s answer relevant to the question given? Provide binary answer, yes or no.'
            'Please also provide the entire input as the next output. '
            'Phrase them into a json, with yes/no as the first element, and the input as the second;'
            'Only return the json file, please. thanks',
            {V.user_know.name: "yes", V.ans_bp.name: "here's the entire input"},
            set_know
        ),
        'SET_YES_NO_S': MacroGPTJSON(
            'Does the user want a summary of the conversation. Categorize the input sentence as either yes or no',
            {V.summary.name: ["yes"]}, V.summary.name, True),
        'SET_YES_NO_B': MacroGPTJSON(
            'Does the user want to keep working on his business plan? Categorize the input sentence as either yes or no',
            {V.prev_bus.name: ["yes"]}, V.prev_bus.name, True),
        'SET_YES_NO_E': MacroGPTJSON(
            'Does the user want to work on his business plan today. Categorize the input sentence as either yes or no',
            {V.work.name: ["yes"]}, V.work.name, True),
        'SET_IDEA_EX': MacroGPTJSON(
            'Does the users want another example? either because the current example does not apply to their business '
            'or they directly request another one. Categorize the input sentence as either yes or no',
            {V.ex_choice.name: ["yes"]}, V.ex_choice.name, True),
        'SAME_BUS': MacroGPTJSON(
            'Does the user still work on the same business as before? '
            'Categorize the input sentence as either same business or new business',
            {V.same_bus.name: ["same"]}, V.same_bus.name, True),
        'GET_PROG': MacroGetProg(),
        'CHECK_TALK': MacroCheckTalk(),
        'DEL_PROFILE': MacroDelProfile(),
        'talked_sub': MacroTalkedSub(),
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
    df.load_transitions(transition_emobus)
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
    summary = 14
    moveon_choice = 15
    same_bus = 16
    work = 17
    feel = 18
    prev_bus = 19


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


# THERE'S ERROR!
class MacroGetProg(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        if vars[vars['call_names']]['small_cat'] not in asw_cat:
            vars[vars['call_names']]['progress'] = vars[vars['call_names']].get('progress', 23) - 1

        prog = str(vars[vars['call_names']].get('progress'))
        if prog is not None:
            return prog

        return None


class MacroDelProfile(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        if 'user_responses' in vars[vars['call_names']]:
            del vars[vars['call_names']]['user_responses']


class MacroCheckTalk(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        prev_sub = None
        if vars[vars['call_names']].get('user_responses'):
            prev_sub = list(vars[vars['call_names']].get('user_responses').keys())
        small_cat = vars[vars['call_names']].get('small_cat')
        question_text = None
        with open('../resources/data.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['subsec'] == small_cat:
                    question_text = row['Question']
                    break

        if prev_sub is not None:
            if small_cat in prev_sub:
                prev_plan = vars[vars['call_names']]['user_responses'].get(small_cat)
                str = 'I asked you about \n' + question_text + '\n and your ' \
                                                               'previous plan was \n' + prev_plan + '. ' + '\n What do you think about it now?'
                return str
            else:
                str = 'let\'s think about this question: \n' + question_text
                return str

        return 'let\'s think about this question: \n' + question_text


class MacroTalkedSub(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        prev_sub = None
        if vars[vars['call_names']].get('user_responses') is not None:
            prev_sub = list(vars[vars['call_names']].get('user_responses').keys())

        talked_subsecs = talked_sub

        all_subsecs = []  # List of all possible subsec values
        subsec_to_section = {}  # Mapping of subsec values to their corresponding section

        with open('../resources/data.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                subsec = row['subsec']
                section = row['Section']
                all_subsecs.append(subsec)
                subsec_to_section[subsec] = section

        available_subsecs = list(set(all_subsecs) - set(talked_subsecs))

        if not available_subsecs:
            return "Sorry, we have already covered all available subcategories."

        chosen_subsec = random.choice(available_subsecs) if available_subsecs else None

        if prev_sub is None:
            return 'It was nice to meet you last time but we did not get to any of the business element during ' \
                   'our last conversation. I can start you with' + chosen_subsec + 'Or what business concept ' \
                    'you would like to brainstorm about?'

        str = ''
        for i in range(len(prev_sub)):
            str += prev_sub[i] + ', '

        last_topic = vars[vars['call_names']].get('small_cat')

        return 'Last time we talked about ' + str + 'And we left off with ' + last_topic + '. ' \
                'How is going with ' + last_topic + '? What topic you want to talk about today. If you have new ideas ' \
                'on topics we discussed last time, we can revisit them'


class MacroUser(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        name = vars['call_names'].lower()
        vars['first_ex'] = True

        if name not in vars:
            vars['VISIT'] = 'first'
            vars[name] = {}
            return 'Nice to meet you ' + vars['call_names'] + '. Before we dive into business, ' \
                                                              'I want to know how you are doing. ' \
                                                              'Do you mind sharing with me how your week has been?'
        else:
            if 'bus_true' not in vars[vars['call_names']]:
                vars[vars['call_names']]['bus_true'] = 'False'
                vars['bus_true'] = vars[vars['call_names']]['bus_true']
            else:
                vars['bus_true'] = vars[vars['call_names']]['bus_true']

            vars['VISIT'] = 'multi'
            vars['more_jokes'] = 'false'

            if 'prev_adv' in vars[vars['call_names']]:
                return 'Hi ' + vars['call_names'] + ', nice to see you again. ' \
                        'Last time you seem really stressed. Did you try the advice I gave you last time? How was it?'
            else:
                return 'Hi ' + vars['call_names'] + ', nice to see you again. How\'s your weekend?'


class MacroCharCheck(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        if 'big_five' in vars[vars['call_names']]:
            return True
        else:
            return False


class MacroSave(Macro):
    def __init__(self, new_stuff):
        self.save = new_stuff

    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        name = vars['call_names'].lower()
        if name not in vars:
            vars[name] = {}
        vars[name].update({self.save: vars[vars['call_names']][self.save]})


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

        return True


class MacroEmotion(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        with open('../resources/personality.json') as json_file:
            emo_dict = json.load(json_file)
        personality = None
        if 'big_five' not in vars[vars['call_names']]:
            if 'big_five' in vars and vars['big_five']:
                ls = vars['big_five']
                personality = ls[random.randrange(len(ls))]
                vars[vars['call_names']]['big_five'] = ls
        else:
            ls = vars[vars['call_names']]['big_five']
            personality = ls[random.randrange(len(ls))]

        if personality == 'neurotic':
            personality = 'agreeable'

        if personality:
            adv = emo_dict[personality][random.randrange(3)]
            if 'prev_adv' in vars[vars['call_names']]:
                while vars[vars['call_names']]['prev_adv'] == adv:
                    adv = emo_dict[personality][random.randrange(3)]
            vars[vars['call_names']]['prev_adv'] = adv
            return 'I have several other friends like you and I know this advice has helped them a lot. ' + adv + '\n Also, relax, I know doing a start-up is ' \
                        'stressful especially for college students like you. Do you feel like ' \
                        'working on your business idea today? Or would you like to relax and try my advice?'
        else:
            return


class MacroDelAdv(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        if 'prev_adv' in vars[vars['call_names']]:
            vars[vars['call_names']]['prev_adv'] = None


class MacroJokes(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[str]):
        data = list(csv.reader(open('../resources/jokes.csv')))
        index = random.randint(1, len(data) - 1)
        while index in told_jokes:
            index = random.randint(1, len(data) - 1)
        told_jokes.append(index)
        vars['more_jokes'] = 'false'
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

        question_text = None

        with open('../resources/data.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['subsec'] == small_cat:
                    question_text = row['Question']
                    break
        vars['SELECTED_QUESTION'] = question_text

        talked_sub.append(small_cat)

        return question_text


class MacroPrintResponses(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        user_responses = vars[vars['call_names']].get('user_responses', {})
        response_text = ""

        for small_cat, user_response in user_responses.items():
            if user_response is not None:
                response_text += f"{small_cat}: {user_response}\n\n"

        return response_text.strip()


class MacroUpdateResponses(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        small_cat = vars[vars['call_names']].get('small_cat')
        ans_bp = vars.get('ans_bp')

        user_responses = vars[vars['call_names']].get('user_responses', {})

        if small_cat and ans_bp:
            user_responses[small_cat] = ans_bp
            vars[vars['call_names']]['user_responses'] = user_responses

        return True


class MacroGetAvailCat(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        talked_subsecs = talked_sub

        all_subsecs = []  # List of all possible subsec values
        subsec_to_section = {}  # Mapping of subsec values to their corresponding section

        with open('../resources/data.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                subsec = row['subsec']
                section = row['Section']
                all_subsecs.append(subsec)
                subsec_to_section[subsec] = section

        available_subsecs = list(set(all_subsecs) - set(talked_subsecs))

        if not available_subsecs:
            return "Sorry, we have already covered all available subcategories."

        chosen_subsec = random.choice(available_subsecs) if available_subsecs else None
        if chosen_subsec is None:
            return "Unfortunately, there are no more subcategories to discuss."

        chosen_large_cat = subsec_to_section[chosen_subsec]
        vars[vars['call_names']]['small_cat'] = chosen_subsec
        vars[vars['call_names']]['large_cat'] = chosen_large_cat
        vars[vars['call_names']]['large_cat_name'] = chosen_large_cat

        talked_sub.append(chosen_subsec)

        return f"{chosen_subsec}? It is an important component of {chosen_large_cat}"


class MacroGetExample(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        small_cat = vars[vars['call_names']].get('small_cat')

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
            return "Sorry, I can't think of more examples off the top of my head. We can come back to this later"

        selected_example = remaining_examples[0]  # Select the first remaining example
        used_examples.append(selected_example)
        vars[vars['call_names']][used_examples_key] = used_examples

        if vars['first_ex']:
            vars['first_ex'] = False
            return 'Let me scaffold you to this question. Here is an ' + vars[vars['call_names']]['small_cat'] \
                + ' example that might help you understand and brainstorm\n' + \
                selected_example + '\n If this example doesn\'t apply to your business, I can give you a different one. ' \
                                   'Do you want another example?'
        else:
            return 'Here is an example that might align with your business\n' + selected_example + \
                ' Do you need another example to gain more inspiration?'


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
            return False

        if d is None:
            return False

        if self.set_variables:
            self.set_variables(vars[vars['call_names']], d)
        else:
            vars[vars['call_names']].update(d)

        return True


class MacroGPTJSON_BUS_1(Macro):
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
            return False

        if d is None:
            return False

        if self.set_variables:
            self.set_variables(vars[vars['call_names']], d)
        else:
            vars[vars['call_names']].update(d)

        if d.get('sounds_yesno'):
            vars['sounds_yesno'] = d.get('sounds_yesno')

        return True


class MacroGPTJSON_BUS_SETKNOW(Macro):
    def __init__(self, request: str, full_ex: Dict[str, Any], field: str, empty_ex: Dict[str, Any] = None,
                 set_variables: Callable[[Dict[str, Any], Dict[str, Any]], None] = None):
        self.request = request
        self.full_ex = json.dumps(full_ex)
        self.empty_ex = '' if empty_ex is None else json.dumps(empty_ex)
        self.check = re.compile(regexutils.generate(full_ex))
        self.set_variables = set_variables
        self.field = field

    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):

        questions = vars.get('SELECTED_QUESTION')

        examples = f'{self.full_ex} or {self.empty_ex} if unavailable' if self.empty_ex else self.full_ex
        prompt = f'Here is the question: {questions}. {self.request} Respond in the JSON schema such as {examples}: {ngrams.raw_text().strip()}'
        output = gpt_completion(prompt)
        if not output: return False

        try:
            d = json.loads(output)
        except JSONDecodeError:
            return False

        if d is None:
            return False

        vars['user_know'] = d.get('user_know')
        vars['ans_bp'] = d.get('ans_bp')

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
            return False

        if d is None:
            return False

        if self.set_variables:
            self.set_variables(vars[vars['call_names']], d)
        else:
            vars[vars['call_names']].update(d)

        if d.get('moveon_choice'):
            vars['moveon_choice'] = d.get('moveon_choice')

        if d.get('ans_bp'):
            vars['ans_bp'] = d.get('ans_bp')

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
            return False

        if d is None:
            return False

        if self.set_variables:
            self.set_variables(vars[vars['call_names']], d)
        else:
            vars[vars['call_names']].update(d)

        if not d['large_cat']:
            return False

        vars['first_ex'] = True

        if d['small_cat'] in talked_sub:
            d['small_cat'] = None
        elif d['small_cat']:
            talked_sub.append(d['small_cat'])

        if 'user_responses' in vars[vars['call_names']]:
            asw_cat = vars[vars['call_names']]['user_responses'].keys()

        vars[vars['call_names']]['bus_true'] = 'True'
        vars['bus_true'] = vars[vars['call_names']]['bus_true']

        if (not d['small_cat'] or d['small_cat'] == "N/A") and d['large_cat']:
            all_subsecs = [row['subsec'] for row in
                           csv.DictReader(open('../resources/data.csv', newline='', encoding='utf-8')) if
                           row['Section'] == d['large_cat']]
            available_subsecs = list(set(all_subsecs) - set(talked_sub))

            if not available_subsecs:
                all_rows = list(csv.DictReader(open('../resources/data.csv', newline='', encoding='utf-8')))
                unique_subsecs = set(row['subsec'] for row in all_rows)
                available_subsecs = list(unique_subsecs - set(talked_sub))
                chosen_row = random.choice(all_rows)
                d['large_cat'] = chosen_row['Section']
                chosen_subsec = chosen_row['subsec']
            else:
                chosen_subsec = random.choice(available_subsecs) if available_subsecs else None

            vars[vars['call_names']][V.small_cat.name] = chosen_subsec

        return True


class MacroNLG(Macro):
    def __init__(self, generate: Callable[[Dict[str, Any]], str]):
        self.generate = generate

    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        return self.generate(vars)


def get_bus_name(vars: Dict[str, Any]):
    ls = vars[vars['call_names']].get(V.business_name.name)
    if ls is not None:
        return ls
    return "Your business"


def get_industry(vars: Dict[str, Any]):
    ls = vars[vars['call_names']].get(V.industry.name)
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


def set_move_on(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[V.moveon_choice.name] = user[V.moveon_choice.name]
    vars[V.ans_bp.name] = user[V.ans_bp.name]


def set_cat_name(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[vars['call_names']][V.large_cat.name] = user[V.large_cat.name]
    vars[vars['call_names']][V.small_cat.name] = user[V.small_cat.name]


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
    d['call_names'] = None
    d['VISIT'] = None
    d['big_five'] = None
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
