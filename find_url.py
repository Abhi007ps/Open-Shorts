import re

with open(r'C:\Users\apsin\.gemini\antigravity\brain\d9e2819f-df12-4455-afbb-dbec68e0d6e6\.system_generated\tasks\task-18862.log', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

for line in text.splitlines():
    if 'youtube' in line or 'youtu.be' in line or 'EXPLORING' in line:
        print(line)
