"""GUI regressions for task persistence, imports and analysis-only handoff."""
import copy
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import typing_extensions
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog
from chembo.app import Window, ENGINE_NAMES
from chembo.examples import workflow_example
from chembo.engine import validate_project

@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app):
    w=Window()
    yield w
    w.dirty=False
    w.close()
    app.processEvents()

@pytest.mark.parametrize('mode',['recipe','pareto','classification'])
def test_task_and_domain_survive_gui_roundtrip(window,mode):
    p=validate_project(workflow_example(mode))
    window.set_project(p)
    assert window.collect()==p
    assert window.analyze.isEnabled()
    if mode=='recipe':
        assert window.params.item(0,6).text()=='0.1'
    elif mode=='classification':
        assert not window.trend.isVisible()
        assert window.labels.text()=='成功 | 失败'

def test_task_selects_visible_modern_engine(window):
    window.engine.setCurrentText(next(k for k,v in ENGINE_NAMES.items() if v=='gryffin'))
    assert not window.analyze.isEnabled()
    window.task.setCurrentText('分类主动学习')
    assert ENGINE_NAMES[window.engine.currentText()]=='bo-mcp'
    assert window.analyze.isEnabled()

def test_excel_import_reconciles_pending(window,tmp_path,monkeypatch):
    from openpyxl import Workbook
    p=workflow_example('recipe')
    p['pending']=[{'A':.2,'B':.8}]
    window.set_project(p)
    f=tmp_path/'measured.xlsx'
    book=Workbook(); sheet=book.active
    sheet.append(['A','B','response']);sheet.append([.2,.8,.45]);book.save(f)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:(str(f),''))
    window.import_csv()
    assert not window.project['pending']
    assert window.project['observations'][-1]['response']==.45

def test_analyze_does_not_add_pending(window,tmp_path):
    p=workflow_example('classification')
    p['pending']=[{'x':.6,'category':'A'}]
    window.set_project(p)
    window.operation='analyze'
    window.result_path=tmp_path/'result.json'
    payload={'ok':True,'recommendations':[],'analysis':{'task':'classification','model':'GaussianProcessClassifier','status':'trained','predictions':[]}}
    window.result_path.write_text(json.dumps(payload))
    window.process=object()
    window.read_log=lambda:None
    window.finished(0,0)
    assert window.project['pending']==p['pending']
    assert window.project['history'][-1]['operation']=='analyze'
    assert window.tabs.currentIndex()==window.analysis_tab
    window.seed.setValue(19)
    assert 'analysis' not in window.collect()
