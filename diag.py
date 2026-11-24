import sys
import os
import subprocess

print("Python version:", sys.version)

video_path = r'C:\Users\apsin\OpenShorts-Studio\storage\uploads\🔴 LIVE! - GTA 6 on PS5 PRO with TYPICAL GAMER!_7223_10765.mp4'
print("Checking video_path:", os.path.exists(video_path))

from backend.clipper import generate_preview_frame

try:
    generate_preview_frame(
        video_path=video_path,
        timestamp=10.0,
        template_config={'layout_mode': 'split_screen', 'canvas_w': 1080, 'canvas_h': 1920, 'gameplay_w': 1080, 'gameplay_h': 560, 'webcam_w': 1080, 'webcam_h': 560},
        subtitle_config={'font_family': 'Impact', 'font_size': 62},
        output_png=r'C:\Users\apsin\OpenShorts-Studio\storage\temp\test_preview.png'
    )
    print("PREVIEW GENERATION SUCCESS!")
except subprocess.CalledProcessError as err:
    print("PREVIEW FAILED WITH RETURN CODE:", err.returncode)
    print("PREVIEW STDERR:\n", err.stderr.decode('utf-8', errors='ignore'))
except Exception as e:
    import traceback
    traceback.print_exc()
