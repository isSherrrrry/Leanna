import pickle
import os.path
from enum import Enum
from emora_stdm import DialogueFlow
from emora_stdm import Macro, Ngrams
from typing import Dict, Any, List, Callable, Pattern
import openai
from openai.embeddings_utils import cosine_similarity, get_embedding

PATH_API_KEY = '../resources/openai_api.txt'
openai.api_key_path = PATH_API_KEY


def visits() -> DialogueFlow:
    transition_model = {
        'state': 'start',
        '`Let\'s brainstorm to build up a business model! Which part of the business do you want to talk about?`':{
            '#GET_CATEGORY': {
                '`I am confused `$cat_result` asjdk.`': 'end'
            },
            'error': {
                '`error`':'end'
            }
        }
    }

    macros = {
        'GET_CATEGORY': MarcoGetCategory()
    }

    df = DialogueFlow('start', end_state='end')
    df.load_transitions(transition_model)
    df.add_macros(macros)
    return df


class MarcoGetCategory(Macro):
    def run(self, ngrams: Ngrams, vars: Dict[str, Any], args: List[Any]):

        vars['cat_result'] = 'yesyy'

        prompt = ngrams.raw_text()  # The input text
        candidate_labels = [
            "Customer Segment",
            "Value proposition",
            "Capabilities",
            "Information strategy",
            "Feel and serve",
            "Trust and loyalty",
            "Revenue model",
            "Profile and loss",
            "Cost structure",
            "Resources",
            "Activity configuration",
            "Partner network",
        ]

        model_name = 'text-embedding-ada-002'  # You can change this to another appropriate model if desired

        # Get embeddings for the prompt and candidate labels
        prompt_embedding = get_embedding(prompt, engine=model_name)
        label_embeddings = [get_embedding(label, engine=model_name) for label in candidate_labels]

        def label_score(prompt_embedding, label_embedding):
            return cosine_similarity(prompt_embedding, label_embedding)

        # Calculate the cosine similarity between the prompt embedding and each label embedding
        similarities = [label_score(prompt_embedding, label_embedding) for label_embedding in label_embeddings]

        # Find the category with the highest similarity
        max_similarity_index = similarities.index(max(similarities))
        result = candidate_labels[max_similarity_index]

        vars['cat_result'] = result

        return True
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
