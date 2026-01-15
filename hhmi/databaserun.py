
import subprocess
import json
import time
import threading



from statuscontrol import StatusControl
from SMN import SMNState
from state_enum import state_enum

class DatabaseRun:
        def __init__(self):
            boxid, ids = None, None
            self.bbuffer, self.ibuffer = None, None
            self.lock = threading.Lock()

        def check_box_id(self, valswallet, valsprotector, dummyprof, decoder):
            cam_thread = threading.Thread(target=dummyprof.run, args=(valswallet, valsprotector), daemon = True)
            cam_thread.start()
            while self.bbuffer is  None:
                with self.lock:
                    if decoder.last_code is not None:
                        boxid, ids = get_values(valswallet, valsprotector, dummyprof, self.iterator)
                        self.iterator += 1
                    if boxid is not None:
                        self.bbuffer = boxid
                    print(f"Box ID: {self.bbuffer}")
            dummyprof.stop()
            cam_thread.join()
            self.send_data(state_enum.SCANNING_GIFTBOX)

        def collect_codes(self, valswallet, valsprotector, dummyprof, decoder):
            cam_thread = threading.Thread(target=dummyprof.run, args=(valswallet, valsprotector), daemon = True)
            cam_thread.start()

            while self.bbuffer is  None or self.ibuffer is  None:
                with self.lock:
                    if decoder.last_code is not None:
                        boxid, ids = get_values(valswallet, valsprotector, dummyprof)
                        

                    if boxid is not None:
                        self.bbuffer = boxid
                    if ids is not None:
                        self.ibuffer = ids
                print(f"Box ID: {self.bbuffer}, IDs: {self.ibuffer}")

            dummyprof.stop()
            cam_thread.join()


        def send_data(self, state):

            if state == SMNState.SCANNING_WALLET:
            

        
                payload = {
                            "boxid": self.bbuffer,
                            "id": self.ibuffer
                        }


                json_arg = json.dumps(payload)

                process = subprocess.Popen(
                            [r"C:\xampp\php\php.exe", r"C:\J2S4\vakken\C_coderen\secridCodeTest\check2.php", "final_check", json_arg],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                self.bbuffer, self.ibuffer = None, None

                

            elif state == state_enum.SCANNING_GIFTBOX:
                payload = {
                            "boxid": self.bbuffer
                        }
                json_arg = json.dumps(payload)
                process = subprocess.Popen(
                            [r"C:\xampp\php\php.exe", r"C:\J2S4\vakken\C_coderen\secridCodeTest\check2.php","check_boxid", json_arg],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                self.bbuffer = None

            stdout, stderr = process.communicate()

            print("=== RAW STDOUT ===")
            print(repr(stdout))
            print("=== RAW STDERR ===")
            print(repr(stderr))


            if stderr:
                print("PHP Error:", stderr)

            try:
                        result = json.loads(stdout)
                        resBruikbaar = result.get("result", False)
                        return resBruikbaar
                        print(result)
                        print("Result from PHP:", result)
            except json.JSONDecodeError:
                        print("Invalid JSON received:")
                        print(stdout)

                


                
             


def get_values(valswallet, valsprotector, dummy):
    with dummy.lock:
        state = StatusControl().get_status()

    if state == SMNState.SCANNING_GIFTBOX:
        return valswallet.get_code(), None

    if state == SMNState.SCANNING_WALLET:
        return None, valsprotector.get_code()

    return None, None




       




