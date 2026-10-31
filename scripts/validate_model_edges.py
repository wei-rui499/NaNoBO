import copy,json,sys,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from chembo.modeling import plan
from chembo.engine import validate_project
out=ROOT/'validation/simulated-lab-20261031/edge-cases';out.mkdir(parents=True,exist_ok=True)
checks=[]
def check(n,c):
 assert c,n
 checks.append({'name':n,'status':'passed'})
p={'name':'SYNTHETIC finite exhaustion','engine':'bo-mcp','seed':23,'batch_size':2,'parameters':[{'name':'A','type':'continuous','low':0,'high':1,'step':.25}], 'objectives':[{'name':'yield','goal':'max'}], 'observations':[], 'pending':[],'_modeling_v2':True}
for n in range(2):
 result=plan(p)
 p['observations'] += [{**row,'yield':1-(row['A']-.4)**2} for row in result['recommendations']]
# one point remains, request size 2 rejected with no partial batch.
try:plan(p);check('剩余不足拒绝部分批量',False)
except ValueError as e:check('剩余不足拒绝部分批量','只剩 1' in str(e))
p['batch_size']=1;r=plan(p);p['observations'] += [{**r['recommendations'][0],'yield':.5}]
p['_operation']='analyze';r=plan(p)
check('全部候选耗尽仍能分析',not r['recommendations'] and not r['analysis']['predictions'] and len(r['analysis']['diagnostics']['rows'])==5)
p=copy.deepcopy(p);p['parameters'][0]['step']=.02;p['observations']=[{'A':i*.02,'yield':1-(i*.02-.42)**2} for i in range(35)]
r=plan(p);d=r['analysis']['diagnostics'];check('超过30条的真实留一验证上限',d['total']==35 and d['evaluated']==30 and len(d['rows'])==30 and '30' in d['note'])
(out/'loo-cap-35-results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
p['task']='classification';p['classification']={'labels':['失败','成功','尚未观察类']};p['objectives']=[{'name':'outcome','goal':'max'}];p['observations']=[{'A':i*.1,'outcome':'失败' if i<5 else '成功'} for i in range(10)]
r=plan(p);a=r['analysis'];check('未见类不捏造概率',all('尚未观察类' not in row['probabilities'] for row in a['predictions']) and any('尚未观察类' in s for s in a['warnings']))
(out/'unseen-class-results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
p['observations']=[{'A':.2,'outcome':'失败'},{'A':.4,'outcome':'失败'},{'A':.8,'outcome':'失败'}]
r=plan(p);check('单类时不伪造分类预测',r['analysis']['status']=='initial_design' and not r['analysis']['predictions'])
p.pop('task');p.pop('classification');p['objectives']=[{'name':'yield','goal':'max'}];p['observations']=[];p['_operation']='recommend';p['_diagnostics']=False;p['batch_size']=24
r=plan(p);check('最大24条批量可执行且互异',len(r['recommendations'])==24 and len({row['A'] for row in r['recommendations']})==24)
(out/'max-batch-results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
(out/'RESULTS.json').write_text(json.dumps({'notice':'SYNTHETIC / 非真实实验','checks':checks},ensure_ascii=False,indent=2))
print('PASS',len(checks),'edge cases')
