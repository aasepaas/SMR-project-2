
import subprocess
import json
import time
import threading


from scanner import CameraScanner, ScanProfile, DataMatrixDecoder

class DatabaseRun:
        def __init__(self):

            self.iterator = 0
            boxid, ids = None, None
            self.bbuffer, self.ibuffer = None, None
            self.lock = threading.Lock()

        def collect_codes(self, valswallet, valsprotector, dummyprof, decoder):
            cam_thread = threading.Thread(target=dummyprof.run, args=(valswallet, valsprotector), daemon = True)
            cam_thread.start()

            while self.bbuffer is  None or self.ibuffer is  None:
                with self.lock:
                    if decoder.last_code is not None:
                        boxid, ids = get_values(valswallet, valsprotector, dummyprof, self.iterator)
                        self.iterator += 1

                    if boxid is not None:
                        self.bbuffer = boxid
                    if ids is not None:
                        self.ibuffer = ids
                print(f"Box ID: {self.bbuffer}, IDs: {self.ibuffer}")

            dummyprof.stop()
            cam_thread.join()


        def send_data(self):

            if self.bbuffer is not None and self.ibuffer is not None:
            

        
                payload = {
                            "boxid": self.bbuffer,
                            "id": self.ibuffer
                        }


                json_arg = json.dumps(payload)

                process = subprocess.Popen(
                            [r"C:\xampp\php\php.exe", r"C:\Users\basti\source\repos\databaserun\check2.php", json_arg],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )

                stdout, stderr = process.communicate()

                print("=== RAW STDOUT ===")
                print(repr(stdout))
                print("=== RAW STDERR ===")
                print(repr(stderr))


                if stderr:
                    print("PHP Error:", stderr)

                try:
                            result = json.loads(stdout)
                            print(result)
                            print("Result from PHP:", result)
                except json.JSONDecodeError:
                            print("Invalid JSON received:")
                            print(stdout)

                boxid, ids = None, None
             


def get_values(valswallet, valsprotector, dummy, iterator):
    with dummy.lock:
        dummy.update_state("box" if iterator % 2 == 0 else "id")
        state = dummy.state

    if state == "box":
        return valswallet.get_code(iterator), None

    if state == "id":
        return None, valsprotector.get_code(iterator)

    return None, None




       






