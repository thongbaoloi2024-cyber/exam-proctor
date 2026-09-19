"""Check report source links, provenance and reported arithmetic without compiling PDF."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import math
import statistics

ROOT=Path(__file__).resolve().parent
visited=[]; errors=[]; figures=[]
def read_tree(path):
    if path in visited:
        errors.append(f'Repeated input: {path.name}');return ''
    visited.append(path)
    text=path.read_text(encoding='utf-8')
    if any(ord(char)<32 and char not in '\n\r\t' for char in text):
        errors.append(f'Unexpected control character: {path.name}')
    # Comments and literal code do not contribute TeX references or environments.
    text=re.sub(r'\\begin\{Verbatim\}.*?\\end\{Verbatim\}','',text,flags=re.S)
    text=re.sub(r'(?m)(?<!\\)%.*$','',text)
    for name in re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}',text):
        figures.append(name)
        if not (ROOT/name).is_file():errors.append(f'Missing figure: {name}')
    stack=[]
    for kind,name in re.findall(r'\\(begin|end)\{([^}]+)\}',text):
        if kind=='begin':stack.append(name)
        elif not stack or stack.pop()!=name:errors.append(f'Environment mismatch: {path.name}: {name}')
    if stack:errors.append(f'Unclosed environments: {path.name}: {stack}')
    braces=0
    for char in re.sub(r'\\[{}]','',text):
        if char=='{':braces+=1
        elif char=='}':braces-=1
        if braces<0:errors.append(f'Extra closing brace: {path.name}');break
    if braces:errors.append(f'Unbalanced braces: {path.name}: {braces}')
    def expand(match):
        name=match.group(1); child=ROOT/(name if name.endswith('.tex') else name+'.tex')
        if not child.is_file():errors.append(f'Missing input: {name}');return ''
        return read_tree(child)
    return re.sub(r'\\input\{([^}]+)\}',expand,text)

all_text=read_tree(ROOT/'main.tex')
labels=re.findall(r'\\label\{([^}]+)\}',all_text)
refs=re.findall(r'\\(?:ref|eqref|pageref)\{([^}]+)\}',all_text)
keys=re.findall(r'\\bibitem\{([^}]+)\}',all_text)
cites=[k.strip() for group in re.findall(r'\\cite\{([^}]+)\}',all_text) for k in group.split(',')]
for label,n in Counter(labels).items():
    if n>1:errors.append(f'Duplicate label: {label}')
for label in set(refs)-set(labels):errors.append(f'Missing label: {label}')
for key in set(cites)-set(keys):errors.append(f'Missing citation: {key}')
if len(keys)!=len(set(keys)):errors.append('Duplicate bibliography keys')
for folder in ['synthetic_evaluation','interval_evaluation']:
    d=ROOT/'data'/folder;manifest=json.loads((d/'manifest.json').read_text(encoding='utf-8'))
    for file,key in [(d/'evaluation.json','data_sha256'),(ROOT/manifest['generator'],'generator_sha256')]:
        if hashlib.sha256(file.read_bytes()).hexdigest()!=manifest[key]:errors.append(f'Hash mismatch: {file}')
    if 'module' in manifest:
        if hashlib.sha256((ROOT/manifest['module']).read_bytes()).hexdigest()!=manifest['module_sha256']:
            errors.append('Reference module hash mismatch')
run_manifest=json.loads((ROOT/'computational_evaluation/manifest.json').read_text(encoding='utf-8'))
for name,expected in run_manifest['hashes'].items():
    if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
        errors.append(f'Computational experiment hash mismatch: {name}')

# Recalculate existing data without executing the generator or replacing its output.
data=json.loads((ROOT/'data/synthetic_evaluation/evaluation.json').read_text(encoding='utf-8'))
def equal(actual, expected, context):
    if actual is None or expected is None:
        ok=actual is expected
    else:
        ok=math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-10)
    if not ok:errors.append(f'Arithmetic mismatch: {context}: {actual} != {expected}')
for group in ['person_counts','presence_counts','phone_counts']:
    for row in data[group]:
        tp,fp,fn=(row[k] for k in ['tp','fp','fn'])
        equal(row['precision'],tp/(tp+fp) if tp+fp else None,group+'/precision')
        equal(row['recall'],tp/(tp+fn) if tp+fn else None,group+'/recall')
        equal(row['f1'],2*tp/(2*tp+fp+fn) if tp+fn else None,group+'/f1')
        if 'fpr' in row:equal(row['fpr'],fp/(fp+row['tn']) if fp+row['tn'] else None,group+'/fpr')
        if 'wpar' in row:
            equal(row['wpar'],row['wrong_owner_events']/row['assigned_events'] if row['assigned_events'] else None,group+'/wpar')
def check_durations(reference,estimate,metrics):
    error=[b-a for a,b in zip(reference,estimate)]
    absolute=sorted(map(abs,error))
    positive=[(a,abs(b-a)) for a,b in zip(reference,estimate) if a>0]
    position=(len(absolute)-1)*.95
    lo=math.floor(position);hi=math.ceil(position)
    values=dict(n=len(error),mae_s=statistics.mean(absolute),median_ae_s=statistics.median(absolute),
                p95_ae_s=absolute[lo]+(absolute[hi]-absolute[lo])*(position-lo),
                max_ae_s=max(absolute),bias_s=statistics.mean(error),mape_n=len(positive),
                mape_percent=statistics.mean(e/a*100 for a,e in positive))
    for key,value in values.items():equal(metrics[key],value,'duration/'+key)
check_durations([r['reference_s'] for r in data['phone_sessions']],
                [r['synthetic_estimate_s'] for r in data['phone_sessions']],data['phone_duration_metrics'])
for level,metrics in data['shift_metrics'].items():
    for row in data['shifts']:
        equal(row['reference_effective_s'],row['reference_presence_s']-max(0,row['reference_phone_s']-row['allowance_s']),row['shift_id'])
        estimate=row['estimates'][level]
        equal(estimate['effective_s'],estimate['presence_s']-max(0,estimate['phone_s']-row['allowance_s']),row['shift_id']+'/'+level)
    check_durations([r['reference_effective_s'] for r in data['shifts']],
                    [r['estimates'][level]['effective_s'] for r in data['shifts']],metrics)
summary=dict(status='PASS' if not errors else 'FAIL',tex_files=len(visited),labels=len(labels),
             bibliography_entries=len(keys),unused_bibliography=sorted(set(keys)-set(cites)),
             unique_figures=sorted(set(figures)),errors=errors,
             scope='Source structure, links, provenance and independent metric recalculation. No PDF layout check.')
(ROOT/'data'/'source_review_20260919.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
