'''
from scanner import *
from databaserun import DatabaseRun
from NetworkClient import Network_client
import threading
from state_enum import state_enum

def main():
    lock = threading.Lock()
    top1, left1 = 525, 800
    bottom1, right1 = top1 + 100, left1 + 100
    top2, left2 = 300, 800
    bottom2, right2 = top2 + 150, left2 + 150

    profilewallet = ScanProfile(name="Wallet",
            roi=(top1, bottom1, left1, right1),
            focus=175,
            exposure=-5,
            brightness=100,
            data_timeout=0.5)


    profileprotector = ScanProfile(
            name="GiftBox",
            roi=(top2, bottom2, left2, right2),
            focus=120,
            exposure=-4,
            brightness=100,
            data_timeout=0.5
        )
    dummyprofile = ScanProfile(
            name="Dummy",
            roi=(0, 100, 0, 100),
            focus=120,
            exposure=-4,
            brightness=100,
            data_timeout=0.5
        )

    valswallet = CameraScanner(profile=profilewallet)
    valsprotector = CameraScanner(profile=profileprotector)
    dummyprof = CameraScanner(profile=dummyprofile)
    
    decoder = DataMatrixDecoder()
    
    client_socket = Network_client('192.168.1.105', 5000)
    client_socket.strt_socket()
    client_socket.connect_client()

    state = client_socket.receive_client()

    program_state =dummyprof.stateselect(state)

    

    if program_state == state_enum.SCANNING_GIFTBOX:
        db_run = DatabaseRun()
        db_run.collect_codes(valswallet, valsprotector, dummyprof, decoder)
        db_run.send_data()
    
    if program_state == state_enum.SWITCH_CAMERA:
        print("Switching Camera")
        dummyprof.switch_camera()
    
    if program_state == state_enum.IDLE:
        print("System is Idle")

    if program_state == state_enum.ERROR:
        print("An Error has occurred")

'''



       


