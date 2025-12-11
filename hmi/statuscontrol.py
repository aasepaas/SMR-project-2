
from state_enum import state_enum
import logging
from SMN import CHANGE, Event, SMNState

class StatusControl:
    def __init__(self):
        self.state = SMNState.IDLE


    def set_status(self, new_state):
        self.state = new_state


   

    def run (self, event:Event) -> SMNState:
        logging.info(f"Current State: {self.state}, Event: {event}")
        if event in CHANGE[self.state]:
            self.state = CHANGE[self.state][event]
            logging.info(f"Transitioned to State: {self.state}")
        else:
            logging.warning(f"No transition defined for State: {self.state} with Event: {event}")
            self.state = SMNState.ERROR
        return self.state
        