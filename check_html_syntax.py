import re

with open(r'engine/reports/templates/expert_technical.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    # find HTML tags
    tags = re.findall(r'<[^>]+>', line)
    for t in tags:
        # ignore jinja comments
        if t.startswith('<!--'):
            continue
        sq = t.count("'")
        dq = t.count('"')
        if dq % 2 != 0:
            print(f"Mismatched double quote at line {i}: {t}")
        # check style attribute
        if 'style="' in t:
            print(f"Style attribute at line {i}: {t}")
