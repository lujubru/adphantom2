import re

fp = r'C:\Users\Lucas\Desktop\adphantom-main\backend\server.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()
    
score_func = re.search(r'def calculate_behavioral_score\(.*?\):(?:(?!def ).)*', content, re.DOTALL).group(0)
print(score_func)
