import urllib.request
import json

def test_detect():
    url = "http://127.0.0.1:8000/api/detect_clips"
    
    # 1. Test Auto Mode
    print("Testing Auto Mode...")
    payload_auto = json.dumps({"min_duration": 8.0, "max_duration": 25.0, "mode": "auto"}).encode()
    req = urllib.request.Request(url, data=payload_auto, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print(f"Auto Mode: detected {len(data['clips'])} viral clips:")
        for c in data["clips"]:
            print(f"  * [{c.get('virality_score')}% - {c.get('reason')}] {c['title']} ({c['start']}s -> {c['end']}s)")

    # 2. Test Manual Mode (e.g. 5 clips)
    print("\nTesting Manual Mode (target 5 clips)...")
    payload_manual = json.dumps({"min_duration": 10.0, "max_duration": 25.0, "mode": "manual", "target_clips": 5}).encode()
    req = urllib.request.Request(url, data=payload_manual, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print(f"Manual Mode: selected {len(data['clips'])} viral clips:")
        for c in data["clips"]:
            print(f"  * [{c.get('virality_score')}% - {c.get('reason')}] {c['title']} ({c['start']}s -> {c['end']}s)")

if __name__ == "__main__":
    test_detect()
