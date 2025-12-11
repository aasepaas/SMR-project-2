import sys
import os
import time
import threading


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
sys.path.append(ROOT)

from rundatabase import DatabaseRun
from StatusControl import StatusControl
from NetworkClient import Network_client
from SMN import Event, CMD_TO_STATE, SMNState
from state_enum import state_enum


def server_thread(server, status_control, db):
   
    server.strt_socket()
    server.connect_client()

    while True:
        cmd = server.receive_client()
        if cmd is None:
            print("Client disconnected.")
            break

        print(f"COMMAND: {cmd}")

        if cmd not in CMD_TO_STATE:
            print(f"Unknown command: {cmd}")
            continue

        
        for event_key, state in CMD_TO_STATE.items():
            if state == CMD_TO_STATE[cmd]:
                event = event_key
                break
        if not event:
            print(f"No matching event for command {cmd}")
            continue

        
        print(f"event: {event}")
        result_state = status_control.run(event)
        print(f" new state: {result_state}")

      
        if result_state == SMNState.SCANNING_GIFTBOX:
            print("STATE: SCANNING_GIFTBOX")
            db.bbuffer = "FK19T-0L3N-R8H6"
            db.send_data(SMNState.SCANNING_GIFTBOX)

        elif result_state == SMNState.SCANNING_WALLET:
            print("STATE: SCANNING_WALLET")
            db.bbuffer = "FK19T-0L3N-R8H6"
            db.ibuffer = "QH82M-9D5Z-B7X1"
            db.send_data(SMNState.SCANNING_WALLET)

        elif result_state == SMNState.PROCESSING:
            print("STATE: PROCESSING")

        time.sleep(0.1)

    server.clse_socket()


def test_pipeline():
    
    server = Network_client("127.0.0.1", 5005)
    status_control = StatusControl()
    db = DatabaseRun()

    
    thread = threading.Thread(target=server_thread, args=(server, status_control, db), daemon=True)
    thread.start()

    time.sleep(0.5)

    
    import socket
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", 5005))

    print("test")

    
    commands = [
        "SCAN_GIFTBOX",
        "SWITCH_CAMERA",
        "SCAN_WALLET",
        "PROCESS_DATA",
        "CYCLE_COMPLETED",
        "IDLE"
    ]

    for cmd in commands:
        print(f"CLIENT SENDS: {cmd}")
        CMD_TO_STATE.get(cmd)
        client.send(cmd.encode('utf-8'))
        time.sleep(1)

    print("closing")
    client.close()
    time.sleep(2)


if __name__ == "__main__":
    test_pipeline()
