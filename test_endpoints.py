import os
import json
import urllib.request

def test():
    # 1. Fetch demo video from /api/demo_video
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/demo_video") as resp:
            demo_info = json.loads(resp.read().decode())
        video_path = demo_info.get("path") if demo_info.get("success") else ""
    except Exception as e:
        print("Server not running or demo endpoint error:", e)
        return

    if not video_path:
        print("No demo video found in storage/uploads.")
        return

    # Test set_source with quotation marks around path
    url = "http://127.0.0.1:8000/api/set_source"
    payload = json.dumps({"video_path": f'"{video_path}"'}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print("SET_SOURCE SUCCESS:", data["status"], "Clips count:", len(data["clips"]))
        for c in data["clips"]:
            print("  -", c["id"], c["title"], f"{c['start']}s -> {c['end']}s")

    # 2. Test preview
    url_preview = "http://127.0.0.1:8000/api/preview"
    preview_payload = json.dumps({
        "timestamp": 12.0,
        "template_config": {
            "canvas_w": 1080, "canvas_h": 1920, "bg_blur_sigma": 30, "bg_brightness": -0.12,
            "gameplay_w": 960, "gameplay_h": 540, "gameplay_radius": 36, "gameplay_border_w": 6,
            "gameplay_border_color": "#FFFFFF", "gameplay_y": 690, "webcam_w": 300, "webcam_h": 300,
            "webcam_border_w": 6, "webcam_border_color": "#FFFFFF", "webcam_y": 540,
            "webcam_crop": {"x": 22, "y": 160, "w": 84, "h": 84}
        },
        "subtitle_config": {
            "font_family": "Impact", "font_size": 56, "position_y": 82, "style_preset": "hormozi",
            "primary_color": "#FFFFFF", "highlight_color": "#FFDE00", "outline_color": "#000000",
            "outline_width": 4, "shadow_depth": 2, "is_uppercase": True, "preview_text": "UNREAL CLUTCH AIM"
        }
    }).encode("utf-8")
    req_p = urllib.request.Request(url_preview, data=preview_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_p) as resp:
        p_data = json.loads(resp.read().decode())
        print("PREVIEW SUCCESS:", p_data["status"], p_data["preview_url"])

    # 3. Test outputs
    with urllib.request.urlopen("http://127.0.0.1:8000/api/outputs") as resp:
        out_data = json.loads(resp.read().decode())
        print("OUTPUTS COUNT:", len(out_data["files"]))

if __name__ == "__main__":
    test()
