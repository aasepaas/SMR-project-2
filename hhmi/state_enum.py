from enum import Enum

class state_enum(Enum):
    IDLE = 0
    SCANNING_GIFTBOX = 1
    SWITCH_CAMERA = 2
    SCANNING_WALLET = 3
    PROCESSING = 4
    ERROR = 5
    SEND_WALLET_COORDINATES = 6
    SEND_GIFTBOX_DOORDINATES = 7
    DONE_CYCLE = 8