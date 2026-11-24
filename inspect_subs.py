import json

subs = json.load(open('storage/default_subtitles.json', 'r', encoding='utf-8'))
print(f"Total lines: {len(subs)}")
for s in subs:
    print(f"[{s['start']:5.1f}s -> {s['end']:5.1f}s] {s['text']}")
