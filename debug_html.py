#!/usr/bin/env python3
import sys, re

html = sys.stdin.read()
# Remove all style content
html_clean = re.sub(r'<style>.*?</style>', '<style>...</style>', html, flags=re.DOTALL)

# Extract body
body_match = re.search(r'<body>(.*)</body>', html_clean, re.DOTALL)
if body_match:
    body = body_match.group(1)
else:
    body = html_clean

# Show structure with indentation
tags = re.findall(r'<[^>]+>', body)
depth = 0
for t in tags:
    is_close = t.startswith('</')
    is_self_close = t.endswith('/>')
    is_comment = t.startswith('<!--')
    
    if is_comment or t == '<br>':
        print('  ' * depth + t)
        continue
    
    if is_close:
        depth -= 1
        if depth < 0:
            depth = 0
        print('  ' * depth + t)
    elif is_self_close:
        print('  ' * depth + t)
    else:
        print('  ' * depth + t[:80])
        depth += 1
