"""Reproducible synthetic laboratory acceptance, using the actual Qt app and engines.

Run with classic Python and QT_QPA_PLATFORM=offscreen. Outputs are explicitly
synthetic and are never written into a user's laboratory project.
"""
import argparse
import copy
import hashlib
import html
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from unittest.mock import patch
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/nanobo-simulation-mpl')
import typing_extensions
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QDialog
from chembo.app import Window
from chembo.engine import validate_project, read_observations, read_candidates, reconcile_project, _same
from chembo.storage import save_project, write_csv
from chembo.space import feasible, candidate_pool
from chembo.table_io import read_table, sheet_names
from chembo.recipe_dialog import RecipeDialog

SEED = 20261031
NOTICE = 'SYNTHETIC / 模拟实验；非真实测量，不得用作真实化学效果证据。'


def numeric_objective(name, goal='max'):
    return dict(name=name, goal=goal, tolerance=.2)


def base_project(name, engine='bo-mcp'):
    return dict(name='模拟验证 · '+name,engine=engine,task='optimization',objective_mode='hierarchical',
                seed=SEED,batch_size=2,parameters=[
                    dict(name='temperature',type='continuous',low=35,high=85,unit='°C'),
                    dict(name='time',type='discrete',low=10,high=60,unit='min'),
                    dict(name='catalyst',type='categorical',options=['配体A','配体B','配体C'],unit='')],
                objectives=[numeric_objective('yield_pct')],observations=[],pending=[],notes=NOTICE)


def scenarios():
    result=[]
    for engine in ['gryffin','atlas','bo-mcp']:
        p=base_project(engine,engine)
        if engine=='bo-mcp':
            p['parameters'][0]['step']=5
            p['parameters'][1]['step']=10
        result.append((engine+'-single',p,4))
    p=base_project('Chimera 优先级多目标','gryffin')
    p['objectives'].append(numeric_objective('cost','min'))
    result.append(('gryffin-chimera',p,4))
    p=base_project('可执行总量配方')
    p['parameters']=[dict(name='A',type='continuous',low=.2,high=2.2,step=.2,unit='mL'),
                     dict(name='B',type='continuous',low=.2,high=2.2,step=.2,unit='mL'),
                     dict(name='catalyst',type='categorical',options=['配体A','配体B'],unit='')]
    p['constraints']=[dict(kind='linear',coefficients={'A':1,'B':1},relation='eq',rhs=2.4),
                      dict(kind='linear',coefficients={'A':1},relation='le',rhs=1.8),
                      dict(kind='ratio',numerator='A',denominator='B',low=.2,high=4)]
    p['candidates']=[dict(A=round(a*.2,8),B=round(2.4-a*.2,8),catalyst=c) for a in range(2,10) for c in ['配体A','配体B']]
    result.append(('recipe-candidates',p,5))
    p=copy.deepcopy(p);p['name']='模拟验证 · 连续总量消元';p.pop('candidates');p['parameters'][0].pop('step');p['parameters'][1].pop('step')
    result.append(('continuous-equality',p,3))
    p=base_project('三目标 Pareto')
    p['parameters'][0]['step']=5;p['parameters'][1]['step']=10
    p['objective_mode']='pareto'
    p['objectives']=[numeric_objective('yield_pct'),numeric_objective('cost','min'),numeric_objective('selectivity')]
    p['reference_point']={'yield_pct':0,'cost':12,'selectivity':0}
    result.append(('pareto-3d',p,5))
    for classes in [['失败','成功'],['球形','中间形貌','各向异性']]:
        p=base_project('分类 '+str(len(classes))+'类')
        p.update(task='classification',classification={'labels':classes},objectives=[numeric_objective('outcome')])
        p['parameters']=[dict(name='A',type='continuous',low=0,high=1,step=.025,unit='mL')]
        result.append(('classification-'+str(len(classes)),p,6))
    return result


def response(row, project, case, serial):
    """A hidden deterministic response surface plus seeded observation noise."""
    fingerprint=json.dumps([case,row,serial,SEED],ensure_ascii=False,sort_keys=True)
    rng=random.Random(int(hashlib.sha256(fingerprint.encode()).hexdigest()[:16],16))
    if project.get('task')=='classification':
        x=row['A'];labels=project['classification']['labels']
        label=labels[int(x>.48)] if len(labels)==2 else labels[0 if x<.30 else 2 if x>.67 else 1]
        return {'outcome':label}
    ligand=row.get('catalyst','配体A');effect={'配体A':.75,'配体B':1.,'配体C':.88}[ligand]
    if 'temperature' in row:
        x=(row['temperature']-35)/50;t=(row['time']-10)/50
        true=8+88*effect*math.exp(-((x-.56)/.28)**2-((t-.52)/.40)**2)
        cost=1.2+3*x+2.5*t+({'配体A':.1,'配体B':1.1,'配体C':.6}[ligand])
        selectivity=35+58*math.exp(-((x-.36)/.34)**2-((t-.72)/.50)**2)
    else:
        x=row['A']/2.4
        true=10+83*effect*math.exp(-((x-.48)/.24)**2)
        cost=1+2*x;selectivity=80-15*x
    values={'yield_pct':round(max(0,min(100,true+rng.gauss(0,1.2))),6),
            'cost':round(cost+rng.gauss(0,.02),6),'selectivity':round(max(0,min(100,selectivity+rng.gauss(0,.6))),6)}
    return {o['name']:values[o['name']] for o in project['objectives']}


def workbook(path, columns, rows, other=False):
    from openpyxl import Workbook
    book=Workbook();sheet=book.active;sheet.title='实验结果'
    sheet.append(columns)
    for row in rows:sheet.append([row.get(c) for c in columns])
    if other:book.create_sheet('说明').append([NOTICE])
    book.save(path)


class Lab:
    def __init__(self, folder, bundle=None):
        self.folder=folder;folder.mkdir(parents=True,exist_ok=True)
        self.bundle=bundle.resolve() if bundle else None
        self.app=QApplication.instance() or QApplication([])
        self.window=Window();self.window.show();self.app.processEvents()
        self.errors=[];self.window.error=lambda e:self.errors.append(str(e))
        if self.bundle:
            self.window.worker_command=self.frozen_command
        self.checks=[];self.cases=[];self.started=time.time()
        self._write()

    def frozen_command(self, request, result):
        root=self.bundle/'Contents'
        if self.window.project['engine']=='bo-mcp':
            return str(root/'Resources/engines/modern/chembo-modern-worker'),[str(request),str(result)]
        return str(root/'MacOS/NaNoBO'),['--worker',str(request),str(result)]

    def check(self, name, condition, detail=''):
        record=dict(name=name,status='passed' if condition else 'failed',detail=detail)
        self.checks.append(record);self._write()
        if not condition:raise AssertionError(name+': '+str(detail))

    def _write(self):
        data=dict(notice=NOTICE,seed=SEED,time_utc=datetime.now(timezone.utc).isoformat(),
                  application_version=__import__('chembo').__version__,bundle=str(self.bundle) if self.bundle else None,
                  status='running',checks=self.checks,cases=self.cases,elapsed_seconds=round(time.time()-getattr(self,'started',time.time()),2))
        save_project(self.folder/'RESULTS.json',data)

    def run_worker(self, operation='recommend'):
        self.errors.clear()
        previous=copy.deepcopy(self.window.project['pending'])
        self.window.run(operation=operation)
        loop=QEventLoop();timer=QTimer();deadline=QTimer()
        timer.setInterval(30);timer.timeout.connect(lambda:loop.quit() if self.window.process is None else None)
        deadline.setSingleShot(True);deadline.timeout.connect(loop.quit)
        timer.start();deadline.start(300000)
        if self.window.process is not None:loop.exec()
        timer.stop();deadline.stop()
        if self.window.process:
            self.window.cancel_run();raise TimeoutError('Actual worker exceeded 300 seconds')
        self.app.processEvents()
        if self.errors:raise RuntimeError('; '.join(self.errors)+'\n'+self.window.logs.toPlainText()[-5000:])
        payload=json.loads(self.window.result_path.read_text())
        if operation=='analyze':self.check('分析不增加待实验',self.window.project['pending']==previous)
        return payload

    def import_results(self,path,sheet=None):
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')),patch.object(self.window,'choose_sheet',return_value=sheet):
            self.window.import_csv()
        if self.errors:raise RuntimeError('; '.join(self.errors))

    def export_case(self,folder,project):
        view=self.window.analysis_view
        exported_analysis=copy.deepcopy(project.get('analysis',{}))
        exported_analysis.setdefault('warnings',[]).append(NOTICE)
        view.set_analysis(exported_analysis,project)
        images=[]
        def export(page,mode,name):
            view.tabs.setCurrentWidget(page);page.kind.setCurrentIndex(mode);self.app.processEvents()
            target=folder/'plots'/name;target.parent.mkdir(exist_ok=True)
            for suffix in ['png','pdf','svg']:
                view.export_figure(target.with_suffix('.'+suffix))
                self.check('导图 '+name+'.'+suffix,target.with_suffix('.'+suffix).stat().st_size>200)
            images.append(str(target.with_suffix('.png').relative_to(self.folder)))
        if project.get('task')=='classification':
            for mode,name in [(0,'class-probability'),(1,'class-entropy'),(2,'class-counts'),(3,'confusion')]:export(view.classification,mode,name)
        else:
            if project['engine']=='bo-mcp':
                for mode,name in [(0,'posterior'),(1,'mean-uncertainty'),(2,'acquisition')]:export(view.prediction,mode,name)
                for mode,name in [(0,'loo-parity'),(1,'loo-error')]:export(view.validation,mode,name)
            export(view.distribution,0,'distribution');export(view.distribution,1,'measured-history')
            if project.get('objective_mode')=='pareto':
                for mode,name in [(0,'pareto-2d'),(1,'pareto-3d'),(2,'hypervolume')]:export(view.multi,mode,name)
        if view._rows:
            view.export_predictions(folder/'candidate-predictions.csv')
            _,rows=read_table(folder/'candidate-predictions.csv')
            self.check('候选预测 CSV 行数一致',len(rows)==len(view._rows))
        return images

    def case(self,name,project,rounds):
        folder=self.folder/'cases'/name;folder.mkdir(parents=True,exist_ok=True)
        project=validate_project(project)
        # Exercise candidate-table import through the actual reader and editor.
        if project.get('candidates'):
            path=folder/'allowed-candidates.xlsx';names=[p['name'] for p in project['parameters']]
            workbook(path,names,project['candidates'])
            candidates=read_candidates(project,path)
            dialog=RecipeDialog(project,self.window)
            with patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')):
                dialog.import_candidates()
            dialog.accept_checked()
            self.check('候选配方编辑器实际导入',dialog.result()==QDialog.Accepted and dialog.project['candidates']==candidates)
            project=dialog.project
        self.window.set_project(project,str(folder/'project.chembo.json'))
        save_project(folder/'initial-project.chembo.json',project)
        round_records=[];seen=[]
        for index in range(rounds):
            before=copy.deepcopy(self.window.project)
            payload=self.run_worker()
            suggestions=payload['recommendations']
            self.check(name+' batch count',len(suggestions)==project['batch_size'])
            blocked=before['observations']+before['pending']
            self.check(name+' 可执行且不重复',all(feasible(row,project) and not any(_same(row,b,project['parameters']) for b in blocked+seen) for row in suggestions))
            # Distinct rows within this actual batch.
            self.check(name+' 批内不重复',not any(_same(a,b,project['parameters']) for i,a in enumerate(suggestions) for b in suggestions[:i]))
            if project.get('candidates'):self.check('候选必须来自合法表',all(row in project['candidates'] for row in suggestions))
            seen.extend(suggestions)
            rows=[dict(row,**response(row,project,name,len(before['observations'])+j)) for j,row in enumerate(suggestions)]
            request=folder/f'round-{index+1:02d}-request.json';save_project(request,before)
            save_project(folder/f'round-{index+1:02d}-worker-result.json',payload)
            columns=[p['name'] for p in project['parameters']]+[o['name'] for o in project['objectives']]
            # Test both export templates and real result import; retain every file.
            template=folder/f'round-{index+1:02d}-to-lab.csv'
            with patch.object(QFileDialog,'getSaveFileName',return_value=(str(template),'')):self.window.export_pending()
            suffix='xlsx' if index%2 else 'csv'
            measured=folder/f'round-{index+1:02d}-measured.{suffix}'
            if suffix=='xlsx':workbook(measured,columns,rows,other=True)
            else:write_csv(measured,columns,rows)
            self.import_results(measured,'实验结果' if suffix=='xlsx' else None)
            self.check(name+' 回填协调',not self.window.project['pending'] and len(self.window.project['observations'])==len(before['observations'])+len(rows))
            self.check(name+' 新结果令旧分析失效','analysis' not in self.window.collect())
            self.check(name+' save project',self.window.save())
            reopened=validate_project(json.loads((folder/'project.chembo.json').read_text()))
            self.window.set_project(reopened,str(folder/'project.chembo.json'))
            self.check(name+' 保存重开保留实验',reopened['observations']==self.window.collect()['observations'])
            objectives=project['objectives']
            round_records.append(dict(round=index+1,observations=len(reopened['observations']),results=rows,
                                      best={o['name']:(min if o['goal']=='min' else max)(r[o['name']] for r in reopened['observations']) for o in objectives} if project['task']!='classification' else {},
                                      model_status=payload.get('analysis',{}).get('status','upstream-native')))
            print(f'PASS {name} round {index+1}: {len(reopened["observations"])} simulated observations',flush=True)
        if project['engine']=='bo-mcp':
            payload=self.run_worker('analyze');analysis=payload['analysis']
            predictions=analysis.get('predictions',[])
            self.check(name+' 实际模型已训练',analysis['status']=='trained')
            self.check(name+' 同模型留一验证',analysis['diagnostics']['evaluated']>=3)
            scores=[r['score'] for r in predictions]
            self.check(name+' 候选排序',scores==sorted(scores,reverse=True))
            if project['task']=='classification':
                self.check(name+' 概率归一',all(abs(sum(r['probabilities'].values())-1)<1e-8 for r in predictions))
                confusion=analysis['diagnostics']['confusion']['matrix']
                self.check(name+' 混淆矩阵计数',sum(map(sum,confusion))==analysis['diagnostics']['evaluated'])
            else:
                self.check(name+' 预测与标准差有限',all(math.isfinite(v) for r in predictions for v in [*r['mean'].values(),*r['std'].values()]))
                d=analysis['diagnostics']
                for objective in project['objectives']:
                    key=objective['name'];rmse=math.sqrt(sum((r['actual'][key]-r['predicted'][key])**2 for r in d['rows'])/len(d['rows']))
                    self.check(name+' RMSE 独立重算 '+key,abs(rmse-d['metrics'][key]['rmse'])<1e-8)
            if project.get('objective_mode')=='pareto':self.verify_pareto(self.window.project,analysis)
            save_project(folder/'final-analysis.json',analysis)
        self.check(name+' final save',self.window.save())
        images=self.export_case(folder,self.window.project)
        record=dict(name=name,engine=project['engine'],task=project['task'],objective_mode=project['objective_mode'],rounds=round_records,
                    observations=len(self.window.project['observations']),analysis=self.window.project.get('analysis',{}),images=images)
        # The full posterior stays in final-analysis.json, not repeated in the summary.
        record['analysis']={k:v for k,v in record['analysis'].items() if k!='predictions'}
        self.cases.append(record);self._write()

    def verify_pareto(self,project,analysis):
        rows=project['observations'];objectives=project['objectives']
        signed=lambda row:[row[o['name']]*(1 if o['goal']=='max' else -1) for o in objectives]
        data=[signed(row) for row in rows]
        expected=[i for i,y in enumerate(data) if not any(all(a>=b for a,b in zip(x,y)) and any(a>b for a,b in zip(x,y)) for x in data)]
        self.check('独立计算非支配集合',set(expected)==set(analysis['pareto']['indices']))
        values=[r['value'] for r in analysis['pareto']['hypervolume_history']]
        self.check('固定参考点下超体积不下降',all(b>=a-1e-8 for a,b in zip(values,values[1:])))

    def recovery(self):
        """UI cancel/error paths must not erase laboratory data."""
        p=scenarios()[4][1];self.window.set_project(p)
        original=copy.deepcopy(self.window.project)
        command=self.window.worker_command
        self.window.worker_command=lambda request,result:('/usr/bin/false',[])
        self.window.run();self.wait_for_end()
        self.check('引擎失败不会伪造结果',bool(self.errors) and self.window.project==original)
        self.errors.clear()
        self.window.worker_command=lambda request,result:('/bin/sleep',['30'])
        self.window.run();self.window.cancel_run();self.wait_for_end()
        self.check('取消计算保留全部记录',not self.errors and self.window.project==original)
        self.window.worker_command=command
        result=self.run_worker();self.check('取消后可重新推荐',len(result['recommendations'])==2)
        # A missing executable triggers FailedToStart and restores controls.
        self.window.set_project(p);self.errors.clear()
        self.window.worker_command=lambda request,result:('/nonexistent/nanobo-worker',[])
        self.window.run();self.wait_for_end()
        self.check('启动失败恢复界面',bool(self.errors) and self.window.process is None and self.window.generate.isEnabled())
        self.window.worker_command=command;self.errors.clear()

    def wait_for_end(self):
        loop=QEventLoop();timer=QTimer();timer.setInterval(20)
        timer.timeout.connect(lambda:loop.quit() if self.window.process is None else None)
        timer.start();QTimer.singleShot(10000,loop.quit)
        if self.window.process is not None:loop.exec()
        timer.stop();self.app.processEvents()
        if self.window.process:raise RuntimeError('Recovery check did not finish')

    def report(self):
        data=json.loads((self.folder/'RESULTS.json').read_text())
        data.update(status='passed' if all(c['status']=='passed' for c in self.checks) else 'failed',elapsed_seconds=round(time.time()-self.started,2))
        save_project(self.folder/'RESULTS.json',data)
        rows=[]
        for case in self.cases:
            metrics=case['analysis'].get('diagnostics',{}).get('metrics',{})
            rows.append(f"| {case['name']} | {case['engine']} | {len(case['rounds'])} | {case['observations']} | {json.dumps(metrics,ensure_ascii=False)} |")
        text=f'''# NaNoBO 模拟真实实验功能验收\n\n{NOTICE}\n\n状态：{data['status']}。随机种子：{SEED}。通过 {len(self.checks)} 项断言，{len(self.cases)} 个完整工作流。\n\n本次使用真实 Qt 界面数据路径、真实模型计算和合成观测值。模拟的产率曲面包含温度、时间、催化剂效应和固定种子的观测噪声；分类使用预设的类别边界。它验证软件行为，不代表真实反应的预测能力或算法优劣。\n\n| 工作流 | 引擎 | 迭代轮数 | 模拟实测数 | 留一验证指标 |\n| --- | --- | --- | --- | --- |\n'''+ '\n'.join(rows)
        text+='\n\n## 文件\n\n每个 cases 子目录保留初始项目、每轮请求／引擎结果、待实验 CSV、模拟回填 CSV/XLSX、最终可打开的项目、完整预测和 PNG/PDF/SVG 图。原始数据及判定记录见 RESULTS.json。\n\n## 验证边界\n\n本机 macOS arm64。Windows、Intel Mac、Apple 公证及真实化学湿实验未做。Gryffin/Atlas 诊断接口未开放，已按当前产品范围验收其推荐；增强约束、Pareto、分类和同模型诊断使用 BoTorch。有限域/连续域的候选采样上限仍适用。\n'
        (self.folder/'REPORT.md').write_text(text)
        cards=''.join('<section><h2>'+html.escape(c['name'])+'</h2><p>'+str(c['observations'])+' 个合成观测；'+str(len(c['rounds']))+' 轮闭环</p>'+''.join('<a href="'+html.escape(i)+'"><img src="'+html.escape(i)+'"></a>' for i in c['images'])+'</section>' for c in self.cases)
        checks=''.join('<tr><td>'+html.escape(c['name'])+'</td><td>'+c['status']+'</td></tr>' for c in self.checks)
        (self.folder/'REPORT.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>NaNoBO 模拟实验验收</title><style>body{max-width:1100px;margin:40px auto;padding:0 24px;font:16px -apple-system,BlinkMacSystemFont,sans-serif;color:#233d34;background:#fcfdfb}header{padding:26px;background:#eaf3ee;border-radius:12px}img{width:47%;vertical-align:top;margin:1%;border:1px solid #e0e8e2}table{border-collapse:collapse;width:100%}td{padding:7px;border-bottom:1px solid #ddd}section{margin:40px 0}h2{border-bottom:2px solid #a9cbbb;padding-bottom:10px}</style><header><h1>NaNoBO 模拟真实实验验收</h1><p>'+html.escape(NOTICE)+'</p><p>'+str(len(self.cases))+' 个闭环工作流 · '+str(len(self.checks))+' 项断言通过 · seed '+str(SEED)+'</p><a href="REPORT.md">完整文字报告</a> · <a href="RESULTS.json">原始判定与数据</a></header>'+cards+'<details><summary>逐项检查</summary><table>'+checks+'</table></details></html>')
        self.window.dirty=False;self.window.close();self.app.processEvents()
        print(f'PASS {len(self.cases)} cases / {len(self.checks)} checks in {data["elapsed_seconds"]}s',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--case',action='append',help='Only selected case IDs; omit for all')
    args=parser.parse_args();lab=Lab(args.output.resolve(),args.bundle)
    try:
        for name,p,rounds in scenarios():
            if args.case and name not in args.case:continue
            lab.case(name,p,rounds)
        if not args.case:lab.recovery()
        lab.report()
    except Exception:
        import traceback
        data=json.loads((lab.folder/'RESULTS.json').read_text());data.update(status='failed',error=traceback.format_exc())
        save_project(lab.folder/'RESULTS.json',data)
        lab.window.dirty=False;lab.window.close()
        raise

if __name__=='__main__':main()
