import openai
from emora_stdm import DialogueFlow
from emora_stdm import Macro, Ngrams
from typing import Dict, Any, List, Pattern, Callable
import json
import pickle

from regexutils import generate


PATH_API_KEY = 'resources/openai_api.txt'
openai.api_key_path = PATH_API_KEY


def visits() -> DialogueFlow:
    trainsitions = {
        'state': 'start',
        '`what is your name?`': {
            '#SET_CALL_NAMES': {
                '`Hi` #GET_CALL_NAME': 'end'
            }
        }
    }

    class MacroGPTJSON(Macro):
        def __init__(self, request: str, full_ex: Dict[str, Any], empty_ex: Dict[str, Any] = None,
                     set_variables: Callable[[Dict[str, Any], Dict[str, Any]], None] = None):
            self.request = request
            self.full_ex = json.dumps(full_ex)
            self.empty_ex = '' if empty_ex is None else json.dumps(empty_ex)
            self.check = re.compile(regexutils.generate(full_ex))
            self.set_variables = set_variables

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

    macros = {
        'GET_CALL_NAME': MacroNLG(get_call_name),
        'GET_OFFICE_LOCATION_HOURS': MacroNLG(get_office_location_hours),
        'SET_CALL_NAMES': MacroGPTJSON(
            'How does the speaker want to be called?',
            {V.call_names.name: ["Mike", "Michael"]})#,
        # 'SET_OFFICE_LOCATION_HOURS': MacroGPTJSON(
        #     'Where is the speaker\'s office and when are the office hours?',
        #     {V.office_location.name: "White Hall E305",
        #      V.office_hours.name: [{"day": "Monday", "begin": "14:00", "end": "15:00"},
        #                            {"day": "Friday", "begin": "11:00", "end": "12:30"}]},
        #     {V.office_location.name: "N/A", V.office_hours.name: []},
        #     set_office_location_hours
        # ),
    }

    df = DialogueFlow('start', end_state='end')
    df.load_transitions(transitions)
    df.add_macros(macros)

# def gpt_text_completion(input: str, regex: Pattern = None, model: str = 'gpt-3.5-turbo') -> str:
#     response = openai.ChatCompletion.create(
#         model=model,
#         messages=[{'role': 'user', 'content': input}]
#     )
#     output = response['choices'][0]['message']['content'].strip()
#
#     if regex is not None:
#         m = regex.search(output)
#         output = m.group().strip() if m else None
#
#     return output

def get_call_name(vars: Dict[str, Any]):
    ls = vars[V.call_names.name]
    return ls[random.randrange(len(ls))]

def get_office_location_hours(vars: Dict[str, Any]):
    return '\n- Location: {}\n- Hours: {}'.format(vars[V.office_location.name], vars[V.office_hours.name])

def set_office_location_hours(vars: Dict[str, Any], user: Dict[str, Any]):
    vars[V.office_location.name] = user[V.office_location.name]
    vars[V.office_hours.name] = {d['day']: [d['begin'], d['end']] for d in user[V.office_hours.name]}
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


if __name__ == '__main__':
    # df = visits()
    # # load(df, 'resources/visits.pkl')
    # df.run()
    #
    # with open('resources/personality.json') as json_file:
    #     emo_dict = json.load(json_file)
    #
    # print(emo_dict)

    data = pickle.load(open('resources/visits.pkl', 'rb'))
    data['call_names'] = None
    data['VISIT'] = None
    print(data)
