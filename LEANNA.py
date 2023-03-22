import pickle
import os.path
from emora_stdm import DialogueFlow
from emora_stdm import Macro, Ngrams
from typing import Dict, Any, List
import time
import re

def visits() -> DialogueFlow:
    transition_visit = {
        'state': 'start',
        '`Hi, I\'m Leanna, your personal start-up consultant. May I know the name of future business tycoon?`': {

        }
    }




    macros = {

    }

    df = DialogueFlow('start', end_state='end')
    df.load_transitions(transition_visit)
    df.add_macros(macros)
    return df
