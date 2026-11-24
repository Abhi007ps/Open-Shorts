import urllib.request
import json

status = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/status").read().decode("utf-8"))
print("Current video:", status.get("current_video"))

# Let's inspect session_state.json if any, or test /api/clips
req = urllib.request.urlopen("http://127.0.0.1:8000/api/status")
