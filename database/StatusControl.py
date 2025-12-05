from state_enum import state_enum
import logging

class StatusControl:
    def init(self):
        self.state = state_enum.IDLE
    def set_status(self, new_state):
        self.state = new_state


    def update_state(self, state: str) -> str:
        if (self.state != state):
            print(f"State changed from {self.previous_state} to {state}")
            self.previous_state = self.state
            self.state = state
            return self.state

    def run (self, state) -> state_enum:
        self.state = state
        if state == "SCAN_GIFTBOX":
            self.update_state(state_enum.SCANNING_GIFTBOX)
        elif state == "SWITCH_CAMERA":
            self.update_state(state_enum.SWITCH_CAMERA)
        elif state == "SCAN_WALLET":
            self.update_state(state_enum.SCANNING_WALLET)
        elif state == "PROCESS":
            self.update_state(state_enum.PROCESSING)
        elif state == "ERROR":
            self.update_state(state_enum.ERROR)
        elif state == "DONE_CYCLE":
            self.update_state(state_enum.DONE_CYCLE)
        else:
            self.update_state(state_enum.IDLE)

        return self.state
