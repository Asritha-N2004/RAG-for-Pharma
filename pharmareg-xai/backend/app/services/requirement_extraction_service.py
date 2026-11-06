"""Reviewable lexical candidates; preserve wrapped sentences and original text."""
import re
def candidates(text,section=''):
    body=text.strip()
    if section and body.startswith(section):body=body[len(section):].lstrip()
    for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])',body):
        if re.search(r'\b(shall|must|should|required)\b',sentence,re.I):
            yield {'original':sentence.strip(),'statement':re.sub(r'\s+',' ',sentence).strip()}
