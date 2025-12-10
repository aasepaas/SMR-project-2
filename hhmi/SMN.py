from state_enum import state_enum

class SMNState:
    IDLE = state_enum.IDLE
    SCANNING_GIFTBOX = state_enum.SCANNING_GIFTBOX
    SWITCH_CAMERA = state_enum.SWITCH_CAMERA
    SCANNING_WALLET = state_enum.SCANNING_WALLET
    PROCESSING = state_enum.PROCESSING
    ERROR = state_enum.ERROR
    SEND_WALLET_COORDINATES = state_enum.SEND_WALLET_COORDINATES
    SEND_GIFTBOX_COORDINATES = state_enum.SEND_GIFTBOX_COORDINATES
    DONE_CYCLE = state_enum.DONE_CYCLE

class Event:
    SCANNING_GIFTBOX = "SCAN_GIFTBOX"
    SWITCH_CAMERA = "SWITCH_CAMERA"
    SCANNING_WALLET = "SCAN_WALLET"
    PROCESS_DATA = "PROCESS_DATA"
    ERROR_OCCURRED = "ERROR"
    CYCLE_COMPLETED = "CYCLE_COMPLETED"
    IDLE = "IDLE"
    SEND_WALLET_COORDINATES = "SEND_WALLET_COORDINATES"
    SEND_GIFTBOX_COORDINATES = "SEND_GIFTBOX_COORDINATES"


    ###mogelijke volgorde:
    '''
        SEND_GIFTBOX_DOORDINATES
        #robot pakt giftbox op basis  van coords
        
        SCAN_GIFTBOX
        ##mogelijk niet nodig als jasmijns nieuwe code werkt
        #robot naar boxscanner

        scan success:
        stap verder
        
        scan fout:
        -> ERROR (voor nu niks)
        SEND_WALLET_COORDINATES
        ##giftbox is geplaats in de mold door robot en is nu tijd voor wallet oppaken
        SCAN_WALLET
        #wallet laten scannen door camera

        scan succes:
        stap verder
        scan fout:
        -> ERROR
        CYCLE_COMPLETED
        ##mogelijk onnodig maar robot geeft aan hij heeft wallet in giftbox in doos terug gelegd 
        #terug loopen naar SEND_GIFTBOX_DOORDINATES

        ERROR
        ## process is foutgegaan. haal hudige box en/of wallet op en leg op reject plek
    '''
CHANGE = {#error bij alle staten mogelijk om te gaan 
    SMNState.IDLE: {#idle mag naar send giftbox coords
        Event.SCANNING_GIFTBOX: SMNState.SCANNING_GIFTBOX,
        Event.SEND_GIFTBOX_COORDINATES: SMNState.SEND_GIFTBOX_COORDINATES
    },
    SMNState.SEND_GIFTBOX_COORDINATES:{#send giftbox coords mag naar scan giftbox en send wallet
        Event.SCANNING_GIFTBOX: SMNState.SCANNING_GIFTBOX,
        Event.ERROR_OCCURRED: SMNState.ERROR,
        Event.CYCLE_COMPLETED: SMNState.DONE_CYCLE
        },
    SMNState.SCANNING_GIFTBOX: {#scan giftbox mag naar send wallets
        Event.SWITCH_CAMERA: SMNState.SWITCH_CAMERA,
        Event.ERROR_OCCURRED: SMNState.ERROR,
        Event.SEND_WALLET_COORDINATES: SMNState.SEND_WALLET_COORDINATES
    },
    SMNState.SWITCH_CAMERA: {
        Event.SCANNING_WALLET: SMNState.SCANNING_WALLET,
        Event.ERROR_OCCURRED: SMNState.ERROR
    },
    SMNState.SEND_WALLET_COORDINATES:{#send wallet coords mag naar scan wallet
        Event.SCANNING_WALLET: SMNState.SCANNING_WALLET,
        Event.ERROR_OCCURRED: SMNState.ERROR
    },
    SMNState.SCANNING_WALLET: {#scan wallet mag gaan naar done cycle
        Event.PROCESS_DATA: SMNState.PROCESSING,
        Event.ERROR_OCCURRED: SMNState.ERROR,
        Event.CYCLE_COMPLETED: SMNState.DONE_CYCLE
    },

    SMNState.PROCESSING: {
        Event.CYCLE_COMPLETED: SMNState.DONE_CYCLE,
        Event.ERROR_OCCURRED: SMNState.ERROR

    },
    SMNState.ERROR: {

        Event.CYCLE_COMPLETED: SMNState.DONE_CYCLE

    },
    SMNState.DONE_CYCLE: { #done cycle mag naar idle en send giftbox coords
        Event.SEND_GIFTBOX_COORDINATES: SMNState.SEND_GIFTBOX_COORDINATES,
        Event.IDLE: SMNState.IDLE
    }
    }

CMD_TO_STATE = {
    "SCAN_GIFTBOX": SMNState.SCANNING_GIFTBOX,
    "SWITCH_CAMERA": SMNState.SWITCH_CAMERA,
    "SCAN_WALLET": SMNState.SCANNING_WALLET,
    "PROCESS_DATA": SMNState.PROCESSING,
    "ERROR": SMNState.ERROR,
    "CYCLE_COMPLETED": SMNState.DONE_CYCLE,
    "IDLE": SMNState.IDLE,
    "SEND_GIFTBOX_COORDINATES": SMNState.SEND_GIFTBOX_COORDINATES,
    "SEND_WALLET_COORDINATES": SMNState.SEND_WALLET_COORDINATES
}