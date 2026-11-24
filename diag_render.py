import sys
import os
import subprocess
import traceback

sys.path.insert(0, r'C:\Users\apsin\OpenShorts-Studio')
from backend.clipper import render_clip

video_path = r'C:\Users\apsin\OpenShorts-Studio\storage\uploads\🔴 LIVE! - GTA 6 on PS5 PRO with TYPICAL GAMER!_7223_10765.mp4'

template_config = {
    'layout_mode': 'split_screen',
    'canvas_w': 1080,
    'canvas_h': 1920,
    'gameplay_w': 1080,
    'gameplay_h': 560,
    'gameplay_crop': {'x': 528, 'y': 108, 'w': 864, 'h': 864},
    'webcam_w': 1080,
    'webcam_h': 560,
    'webcam_crop': {'x': 22, 'y': 160, 'w': 84, 'h': 84},
    'sharpen_amount': 0.8,
    'contrast_boost': 1.08,
    'saturation_boost': 1.22,
    'brightness_offset': 0.01,
    'deblock_level': 'medium',
    'micro_texture': 0.6,
    'dynamic_range_pop': True,
    'pixel_generator': True,
    'pixel_generator_mode': 'ultra',
    'export_bitrate': '35M'
}

subtitle_config = {
    'font_family': 'Impact',
    'font_size': 62,
    'position_x': 50,
    'position_y': 50,
    'style_preset': 'speed',
    'primary_color': '#FFFFFF',
    'highlight_color': '#CCFF00',
    'outline_color': '#000000',
    'outline_width': 8,
    'shadow_depth': 6,
    'is_uppercase': True,
    'words_per_line': 3
}

all_subs = [
    {
        'start': 2092.5,
        'end': 2095.0,
        'text': 'HE WAS COMPLETELY SPEECHLESS',
        'words': [
            {'word': 'HE', 'start': 2092.5, 'end': 2093.0},
            {'word': 'WAS', 'start': 2093.0, 'end': 2093.5},
            {'word': 'COMPLETELY', 'start': 2093.5, 'end': 2094.2},
            {'word': 'SPEECHLESS', 'start': 2094.2, 'end': 2095.0}
        ]
    }
]

print("Testing render_clip...")
try:
    res = render_clip(
        video_path=video_path,
        clip_id="clip_4",
        start_time=2092.3,
        end_time=2104.2,
        title="Rank 4 • HE WAS COMPLETELY SPEECHLESS",
        template_config=template_config,
        subtitle_config=subtitle_config,
        all_subtitles=all_subs,
        hook_config=None,
        output_dir=r'C:\Users\apsin\OpenShorts-Studio\storage\exports',
        encoder='libx264'
    )
    print("RENDER SUCCESS:", res)
except subprocess.CalledProcessError as err:
    print("RENDER FAILED WITH CODE:", err.returncode)
    print("STDERR:\n", err.stderr.decode('utf-8', errors='ignore'))
except Exception as ex:
    traceback.print_exc()
