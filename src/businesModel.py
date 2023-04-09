import json
import pickle
import os.path
from enum import Enum
from json import JSONDecodeError
from random import random
import re

from emora_stdm import DialogueFlow
from emora_stdm import Macro, Ngrams
from typing import Dict, Any, List, Callable, Pattern
import openai
from openai.embeddings_utils import cosine_similarity, get_embedding

from src import regexutils

PATH_API_KEY = '../resources/openai_api.txt'
openai.api_key_path = PATH_API_KEY


def visits() -> DialogueFlow:
    transition_model = {
        'state': 'start',
        '`Hi, I am so excited to talk to you about your business. '
        'What is its name and are you selling a product or a service? '
        'A product is something that people can use and is tangible. '
        'Think of a computer or software such as google drive. '
        'A service is something you can provide or perform for another person. '
        'For example, a hair salon or a restaurant service.`':{
            '#SET_BUS_NAME': {
                '`Thanks for letting me know! That sounds super exciting. '
                '`#GET_BUS_NAME` is sure to change the world one day as a fantastic `#GET_INDU`. '
                'My role is to help you brainstorm on fuzzy ideas of your business so that you can have a tangible pitch by the end of our conversation. '
                'Is there a particular problem area you would like to brainstorm about first?`' : {
                    '[{no}]':{
                        '`Ok we can start with product innovation. '
                        'There are three parts to Product Innovation and they are value propositions, capabilities, and target customers. '
                        'They are related as A VALUE PROPOSITION is enabled through a range of CAPABILITIES and is a value for a specific TARGET CUSTOMER segment, '
                        'which has needs to be fulfilled. '
                        'Let’s think about the value proposition being composed of both capabilities and a target customer. '
                        'In that case, capabilities are related to what your `#GET_BUS_NAME` can do and target customer is related to who your `#GET_BUS_NAME` is serving. '
                        'In order to brainstorm effectively let\'s choose whether we want to talk about the `#GET_INDU` more first or the customer more first`': 'end'
                    },
                    '[{yes}]':{
                        '`Great!`': 'end'
                    }
                }
            },
            'error': {
                '`error`': 'end'
            }
        }
    }

    macros = {
        'GET_CATEGORY': MarcoGetCategory(),
        'SET_BUS_NAME': MacroGPTJSON(
            'Please find the person\'s business name and the industry',
            {V.business_name.name: "Microsoft", V.industry.name:"Technology"},
            set_bus_name
        ),
        'GET_BUS_NAME': MacroNLG(get_bus_name),
        'GET_INDU': MacroNLG(get_industry)
    }

    df = DialogueFlow('start', end_state='end')
    df.load_transitions(transition_model)
    df.add_macros(macros)
    return df

class V(Enum):
    business_name = 0
    industry = 1

class MarcoGetCategory(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):
        vars['cat_result'] = 'yesyy'
        prompt = ngrams.raw_text()  # The input text
        candidate_labels = [
            "product innovation",
            "customer relationship",
            "infrastructure management",
            "other"
        ]
        model_name = 'text-embedding-ada-002'  # You can change this to another appropriate model if desired
        # Get embeddings for the prompt and candidate labels
        prompt_embedding = get_embedding(prompt, engine=model_name)
        label_embeddings = [get_embedding(label, engine=model_name) for label in candidate_labels]

        def label_score(prompt_embedding, label_embedding):
            return cosine_similarity(prompt_embedding, label_embedding)

        # Calculate the cosine similarity between the prompt embedding and each label embedding
        similarities = [label_score(prompt_embedding, label_embedding) for label_embedding in label_embeddings]

        # Sort the similarities and their indices in descending order
        sorted_similarities = sorted(enumerate(similarities), key=lambda x: x[1], reverse=True)

        # Find the top two categories and their similarities
        top1_index, top1_similarity = sorted_similarities[0]
        top2_index, top2_similarity = sorted_similarities[1]

        difference_threshold = 0.02
        if top1_similarity - top2_similarity < difference_threshold:
            result = f"{candidate_labels[top1_index]} and {candidate_labels[top2_index]}"
        else:
            result = candidate_labels[top1_index]

        vars['cat_result'] = result

        return True


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
    return ls

def get_industry(vars: Dict[str, Any]):
    ls = vars[V.industry.name]
    return ls

def set_bus_name(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[V.business_name.name] = user[V.business_name.name]
    vars[V.industry.name] = user[V.industry.name]

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

    path = '../resources/visits.pkl'

    check_file = os.path.isfile(path)
    if check_file:
        load(df, '../resources/visits.pkl')
    else:
        df.run()
        save(df, '../resources/visits.pkl')
