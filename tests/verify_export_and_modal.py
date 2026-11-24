import urllib.request
import json
import sys

def run_tests():
    print("=== 1. Verifying HTML served by FastAPI ===")
    html = urllib.request.urlopen("http://127.0.0.1:8000/").read().decode("utf-8")

    elements = [
        'id="video-modal"',
        'id="modal-title"',
        'id="modal-video"',
        'id="modal-download"',
        'id="modal-close"',
        'id="outputs-grid"',
        'data-tab="tab-clips"',
        'data-tab="tab-template"',
        'data-tab="tab-subtitles"',
        'data-tab="tab-enhance"',
        'data-tab="tab-export"'
    ]

    for el in elements:
        assert el in html, f"Missing element in index.html: {el}"
        print(f"  [PASS] Found {el}")

    print("\n=== 2. Verifying CSS served by FastAPI ===")
    css = urllib.request.urlopen("http://127.0.0.1:8000/static/styles.css").read().decode("utf-8")

    css_rules = [
        ".modal-backdrop",
        ".modal-content",
        ".modal-body video",
        ".gallery-card",
        ".gallery-thumb",
        "max-width: 400px",
        "max-height: 56vh",
        "width: 52px",
        "height: 92px"
    ]

    for rule in css_rules:
        assert rule in css, f"Missing CSS rule: {rule}"
        print(f"  [PASS] Found CSS rule: {rule}")

    print("\n=== 3. Verifying JavaScript served by FastAPI ===")
    js = urllib.request.urlopen("http://127.0.0.1:8000/static/app.js").read().decode("utf-8")

    js_patterns = [
        "window.openVideoModal = function",
        "window.closeModal = closeModal",
        "video-modal",
        "modal-title",
        "openVideoModal(data.clip.video_url, data.clip.title)",
        "renderOutputs"
    ]

    for pat in js_patterns:
        assert pat in js, f"Missing JS pattern: {pat}"
        print(f"  [PASS] Found JS pattern: {pat}")

    print("\n=== 4. Verifying Outputs API & Static Media Serving ===")
    outputs_data = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/outputs").read().decode("utf-8"))
    assert "files" in outputs_data and len(outputs_data["files"]) > 0, "No output files found"
    first_file = outputs_data["files"][0]
    print(f"  First file in gallery: {first_file['filename']} ({first_file['size_mb']} MB)")

    video_url = "http://127.0.0.1:8000" + first_file["video_url"]
    req_vid = urllib.request.Request(video_url, method="HEAD")
    with urllib.request.urlopen(req_vid) as r:
        assert r.status == 200, f"Video HEAD failed: {r.status}"
        print(f"  [PASS] Video serving verified (200 OK): {video_url}")

    if first_file.get("thumb_url"):
        thumb_url = "http://127.0.0.1:8000" + first_file["thumb_url"]
        req_thumb = urllib.request.Request(thumb_url, method="HEAD")
        with urllib.request.urlopen(req_thumb) as r:
            assert r.status == 200, f"Thumb HEAD failed: {r.status}"
            print(f"  [PASS] Thumbnail serving verified (200 OK): {thumb_url}")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print("TEST FAILED:", e)
        sys.exit(1)
