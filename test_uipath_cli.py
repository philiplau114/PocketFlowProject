import subprocess
import json
import os
import time

# Path to UiRobot and your test package
UIROBOT_PATH = r"C:\Users\Philip\AppData\Local\Programs\UiPath\Studio\UiRobot.exe"
PACKAGE_PATH = r"C:\Users\Philip\Documents\UiPath\Packages\TestProcess.1.0.4.nupkg"

# Path to output JSON file (must match in_OutputJsonPath in UiPath workflow)
OUTPUT_JSON_PATH = r"C:\Users\Philip\Documents\UiPath\Packages\output.json"

# Example input argument
input_args = {
    "in_argu": "Hello from Python",
    "in_OutputJsonPath": OUTPUT_JSON_PATH
}
input_args_json = json.dumps(input_args)

# Build the command
cmd = [
    UIROBOT_PATH,
    "execute",
    "--file", PACKAGE_PATH,
    "--input", input_args_json
]

print("Running command:")
print(' '.join(cmd))

# Start the UiPath process (non-blocking)
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Poll for the output file and check with json.load()
max_wait = 300  # seconds
poll_interval = 1  # seconds
waited = 0
output_data = None

while waited < max_wait:
    if os.path.exists(OUTPUT_JSON_PATH):
        try:
            with open(OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
                output_data = json.load(f)
            print(f"Output JSON file found and loaded: {OUTPUT_JSON_PATH}")
            print("--- Output Data ---")
            print(json.dumps(output_data, indent=2))
            break
        except json.JSONDecodeError:
            # File is not completely written yet
            pass
        except Exception as e:
            print(f"Error reading JSON: {e}")
    time.sleep(poll_interval)
    waited += poll_interval

if output_data is not None:
    # File found and read, now kill the UiPath process
    print("Killing UiPath process...")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print("UiPath process did not terminate, killing forcefully.")
        process.kill()
else:
    print(f"Output JSON file was not found or not readable after {max_wait} seconds.")

# Optional: read any leftover stdout/stderr
try:
    stdout, stderr = process.communicate(timeout=5)
    print("\n--- STDOUT ---\n", stdout)
    print("\n--- STDERR ---\n", stderr)
except Exception as e:
    print(f"Error retrieving remaining process output: {e}")