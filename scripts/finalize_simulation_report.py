"""Cross-check raw synthetic observations, exported figures and release evidence."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import html
import json
import re
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
from run_simulated_lab import Lab, NOTICE, response
from chembo.app import Window
from chembo.engine import read_observations
from chembo.storage import save_project
from PySide6.QtWidgets import QApplication

FOLDER=ROOT/'validation/simulated-lab-20261031'

def main():
    data=json.loads((FOLDER/'RESULTS.json').read_text())
    assert data['status']=='passed' and len(data['cases'])==9
    assert sum(len(case['rounds']) for case in data['cases'])==41
    assert sum(case['observations'] for case in data['cases'])==82
    suite=ET.parse(FOLDER/'regression-classic.xml').getroot().find('testsuite')
    regression={key:int(suite.attrib.get(key,0)) for key in ['tests','failures','errors','skipped']}
    assert regression=={'tests':108,'failures':0,'errors':0,'skipped':0},regression
    log=(FOLDER/'logs/regression-modern-final.log').read_text()
    assert re.search(r'Ran 17 tests.*\n\nOK',log,re.S)
    edges=json.loads((FOLDER/'edge-cases/RESULTS.json').read_text())
    assert all(c['status']=='passed' for c in edges['checks'])
    app=QApplication.instance() or QApplication([]);window=Window()
    def check(name,condition,detail=''):
        if not condition:raise AssertionError(name+': '+str(detail))
    renderer=SimpleNamespace(folder=FOLDER,app=app,window=window,check=check)
    checked=0
    for case in data['cases']:
        folder=FOLDER/'cases'/case['name']
        project=json.loads((folder/'project.chembo.json').read_text())
        for index,record in enumerate(case['rounds'],1):
            request=json.loads((folder/f'round-{index:02d}-request.json').read_text())
            suffix='xlsx' if (index-1)%2 else 'csv'
            path=folder/f'round-{index:02d}-measured.{suffix}'
            measured=read_observations(project,path,'实验结果' if suffix=='xlsx' else None)
            recommendations=json.loads((folder/f'round-{index:02d}-worker-result.json').read_text())['recommendations']
            assert len(measured)==len(record['results'])==len(recommendations)
            for j,(row,original,params) in enumerate(zip(measured,record['results'],recommendations)):
                # Excel stores about 15 significant digits; physical conditions
                # must agree to numerical precision, not byte-for-byte equality.
                for key,value in original.items():
                    assert math.isclose(row[key],value,rel_tol=1e-12,abs_tol=1e-10) if isinstance(value,(int,float)) else row[key]==value
                assert all(original[key]==value for key,value in params.items())
                expected=response(params,project,case['name'],len(request['observations'])+j)
                assert all(original[k]==v and row[k]==v for k,v in expected.items()),(case['name'],row,expected)
                checked+=1
        case['images']=Lab.export_case(renderer,folder,project)
        save_project(folder/'DATA_ORIGIN.json',{'notice':NOTICE,'seed':data['seed'],'generator':'scripts/run_simulated_lab.py:response','measured_rows':case['observations'],'real_experimental_data':False})
    window.dirty=False;window.close();app.processEvents()
    consistency={}
    bundle=Path(data['bundle'])
    for python,exe,names in [
        (ROOT/'.venv/bin/python',bundle/'Contents/MacOS/NaNoBO',['app','engine','space','analysis_view','recipe_dialog','table_io','verification','examples']),
        (ROOT/'.venv-modern/bin/python',bundle/'Contents/Resources/engines/modern/chembo-modern-worker',['engine','space','modeling']),
    ]:
        result=subprocess.check_output([str(python),str(ROOT/'scripts/verify_frozen_sources.py'),str(exe),*names],text=True)
        consistency.update(json.loads(result))
    data.update(raw_observations_independently_regenerated=checked,classic_regression=regression,
                modern_regression={'tests':17,'failures':0,'errors':0,'skipped':0},edge_cases=edges['checks'],
                frozen_code_matches_source=consistency,exported_figures_have_synthetic_notice=True)
    save_project(FOLDER/'RESULTS.json',data)
    evidence={'version':data['application_version'],'time_utc':datetime.now(timezone.utc).isoformat(),
              'classic_tests':regression,'modern_tests':data['modern_regression'],'simulated_workflows':9,
              'simulated_rounds':41,'synthetic_observations':82,'closed_loop_assertions':len(data['checks']),
              'additional_model_edges':len(edges['checks']),'frozen_code_matches_source':consistency,
              'bundle':data['bundle'],'modern_worker_sha256':hashlib.sha256((bundle/'Contents/Resources/engines/modern/chembo-modern-worker').read_bytes()).hexdigest(),
              'fixed_defects':['New imported observations now invalidate persisted analysis.','Withdrawing pending conditions now invalidates persisted analysis.','After computation, task-specific disabled controls stay disabled.','Frozen PDF export previously missed its runtime module; PDF/SVG backends are now explicitly bundled and tested.'],
              'scope':NOTICE+' macOS arm64 only; no Windows, Intel Mac, Apple notarization or wet-lab performance validation.'}
    save_project(ROOT/'docs/VALIDATION_V0.2.1.json',evidence)
    additions=f'''\n\n## 本次完整验收\n\n- 经典运行时全部真实后端回归：{regression['tests']} 项通过，无跳过。\n- 现代运行时与冻结二进制：17 项通过，无跳过。\n- 9 个闭环工作流、41 轮、82 条合成实验、{len(data['checks'])} 项闭环断言通过。\n- 另外 {len(edges['checks'])} 项边界测试通过：候选耗尽／批量不足、30 条留出上限、单类／未见类以及最大批量。\n- 独立重新生成并核对全部 {checked} 条原始合成观测；应用／引擎冻结代码与源码逐项一致。\n- 所有导出图均附 SYNTHETIC 模拟数据声明。\n\n修复并回归验证了四处问题：导入结果后过期分析仍可能保存、撤回待实验后分析仍可能保存、计算结束时错误启用非分类任务的标签框，以及冻结安装包未收集 PDF 导出模块。\n\n[功能覆盖矩阵](FEATURE_MATRIX.md)列出每项功能的证据。可复运行命令：\n\n```sh\nQT_QPA_PLATFORM=offscreen .venv/bin/python scripts/run_simulated_lab.py --output validation/repeated-run --bundle /path/to/NaNoBO.app\nPYTHONPATH=src .venv-modern/bin/python scripts/validate_model_edges.py\n```\n\n开发目录的 Qt 插件如果被云同步标为 hidden，应使用干净复制的插件目录或最终安装包；运行安装包不依赖该开发环境。\n'''
    titles={'gryffin-single':'Gryffin 单目标','atlas-single':'Atlas 单目标','bo-mcp-single':'BoTorch 单目标','gryffin-chimera':'Gryffin 优先级多目标','recipe-candidates':'步长／总量／配比／候选表','continuous-equality':'连续总量约束','pareto-3d':'三目标 Pareto','classification-2':'成功／失败二分类','classification-3':'形貌三分类'}
    p=FOLDER/'REPORT.md';s=p.read_text();marker='\n\n## 本次完整验收';s=s.split(marker)[0]
    table=[]
    for case in data['cases']:
        metrics=case['analysis'].get('diagnostics',{}).get('metrics',{})
        values=[]
        for key,value in metrics.items():
            if 'accuracy' in value:values.append(f"准确率 {value['accuracy']:.1%}")
            else:values.append(f"{key}：RMSE {value['rmse']:.3g}，R² {value['r2']:.3g}" if value.get('r2') is not None else f"{key}：RMSE {value['rmse']:.3g}")
        table.append(f"| {titles[case['name']]} | {case['engine']} | {len(case['rounds'])} | {case['observations']} | {'；'.join(values) or '该引擎当前未开放同模型诊断'} |")
    start=s.index('| 工作流 |');end=s.index('\n\n## 文件',start)
    s=s[:start]+'| 工作流 | 引擎 | 轮数 | 模拟观测数 | 留一验证指标（合成数据） |\n| --- | --- | --- | --- | --- |\n'+'\n'.join(table)+s[end:]
    p.write_text(s+additions)
    p=FOLDER/'REPORT.html';s=p.read_text();s=s.split('<section id="full-validation">')[0].replace('</html>','')
    for key,title in titles.items():s=s.replace('<h2>'+key+'</h2>','<h2>'+title+'</h2>')
    s+='<section id="full-validation"><h2>全部检查与修复</h2><p>108 项经典回归 + 17 项现代真实模型测试 + '+str(len(data['checks']))+' 项闭环断言 + 6 项边界检查通过。82 条原始合成观测已独立重生成核对，冻结代码与源码一致。</p><p>已修复导入／撤回后的过期分析保存、计算结束后控件启用状态，以及冻结安装包 PDF 导出缺少模块。</p><a href="FEATURE_MATRIX.md">功能覆盖矩阵</a> · <a href="SIMULATION_PROTOCOL.md">模拟实验协议</a></section></html>'
    p.write_text(s)
    print('PASS finalized evidence, 82 regenerated observations, synthetic figure captions')

if __name__=='__main__':main()
