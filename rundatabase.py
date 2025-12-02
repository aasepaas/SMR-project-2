import subprocess
import json


payload = {
    "boxid": "123",
    "id": "456"
}


json_arg = json.dumps(payload)

process = subprocess.Popen(
    ["php", "check.php", json_arg],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

stdout, stderr = process.communicate()

if stderr:
    print("PHP Error:", stderr)

try:
    result = json.loads(stdout)
    print("Result from PHP:", result)
except json.JSONDecodeError:
    print("Invalid JSON received:")
    print(stdout)




