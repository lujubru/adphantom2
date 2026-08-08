import difflib

def extract_func(fp, func_name):
    with open(fp, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    start = -1
    for i, line in enumerate(lines):
        if line.startswith(f"def {func_name}("):
            start = i
            break
    if start == -1: return []
    func = [lines[start]]
    start += 1
    while start < len(lines):
        if lines[start].startswith('def ') or lines[start].startswith('async def ') or lines[start].startswith('@'): break
        func.append(lines[start])
        start += 1
    return func

f1 = extract_func(r'c:\Users\Lucas\Documents\Proyectos\adphantom2\backend\server.py', 'is_bot')
f2 = extract_func(r'C:\Users\Lucas\Desktop\adphantom-main\backend\server.py', 'is_bot')

diff = list(difflib.unified_diff(f2, f1, fromfile='main', tofile='adphantom2', n=0))
with open('diff_out_bot.txt', 'w', encoding='utf-8') as out:
    out.write(''.join(diff))
