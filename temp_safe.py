with open(r'C:\Users\Lucas\Desktop\adphantom-main\backend\server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_html = False
for i, line in enumerate(lines):
    if 'SAFE_PAGE_HTML =' in line:
        in_html = True
    if in_html:
        print(line.strip())
        if '"""' in line and not 'SAFE_PAGE_HTML =' in line:
            break
