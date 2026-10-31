"""State and recovery defects found by complete simulated-lab workflows."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import typing_extensions
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog
from chembo.app import Window
from chembo.examples import workflow_example

@pytest.fixture(scope='module')
def app(): return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app):
    w=Window();p=workflow_example('recipe')
    p['analysis']={'model':'old analysis','status':'trained','predictions':[]}
    w.set_project(p)
    yield w
    w.dirty=False;w.close();app.processEvents()

def test_new_import_invalidates_stored_analysis(window,tmp_path,monkeypatch):
    f=tmp_path/'new.csv';f.write_text('A,B,response\n0.2,0.8,0.4\n')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:(str(f),''))
    window.import_csv()
    assert 'analysis' not in window.collect()

def test_pending_withdraw_invalidates_stored_analysis(window):
    p=copy.deepcopy(window.project);p['pending']=[{'A':.2,'B':.8}]
    window.set_project(p);window.pending.selectRow(0);window.withdraw_pending()
    assert 'analysis' not in window.collect()

def test_busy_restore_keeps_nonclassification_labels_disabled(window):
    window.busy(True);window.busy(False)
    assert not window.labels.isEnabled()

def test_busy_restore_preserves_classification_goal_disabled(window):
    window.set_project(workflow_example('classification'))
    window.busy(True);window.busy(False)
    assert not window.objectives.cellWidget(0,1).isEnabled()

def test_bad_import_keeps_data_and_analysis(window,tmp_path,monkeypatch):
    before=copy.deepcopy(window.project);errors=[];window.error=lambda e:errors.append(str(e))
    f=tmp_path/'bad.csv';f.write_text('A,B,response\n0.2,0.8,\n')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:(str(f),''))
    window.import_csv()
    assert errors and window.project==before

def test_manual_pending_transfer_and_fill(window):
    p=copy.deepcopy(window.project);p['pending']=[{'A':.2,'B':.8}]
    window.set_project(p);window.pending.selectRow(0);window.pending_to_observed()
    row=window.observed.rowCount()-1
    window.observed.item(row,2).setText('0.45')
    collected=window.collect()
    assert not collected['pending']
    assert collected['observations'][-1]=={'A':.2,'B':.8,'response':.45}
    assert 'analysis' not in collected

def test_new_project_cancel_and_discard(window,monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    before=copy.deepcopy(window.project);window.changed()
    monkeypatch.setattr(QMessageBox,'question',lambda *a:QMessageBox.Cancel)
    window.new_project();assert window.project==before
    monkeypatch.setattr(QMessageBox,'question',lambda *a:QMessageBox.Discard)
    window.new_project()
    assert not window.project['observations'] and not window.project['pending']
    assert not window.project.get('constraints') and not window.project.get('analysis')

def test_open_project_cancel_then_valid_then_invalid(window,tmp_path,monkeypatch):
    from chembo.storage import save_project
    before=copy.deepcopy(window.project)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:('',''))
    window.open_project();assert window.project==before
    f=tmp_path/'classification.json';p=workflow_example('classification');save_project(f,p)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:(str(f),''))
    window.open_project();assert window.project['task']=='classification'
    previous=copy.deepcopy(window.project);f.write_text('{broken')
    errors=[];window.error=lambda e:errors.append(str(e))
    window.open_project();assert errors and window.project==previous

def test_all_four_example_loaders(window,monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    for title,task,mode in [('数值优化','optimization','hierarchical'),('总量与步长','optimization','hierarchical'),('Pareto 多目标','optimization','pareto'),('分类主动学习','classification','hierarchical')]:
        monkeypatch.setattr(QInputDialog,'getItem',lambda *a,v=title:(v,True))
        window.load_example()
        assert (window.project['task'],window.project['objective_mode'])==(task,mode)

def test_add_remove_definitions_and_clear_constraints(window):
    p=workflow_example('optimization');p['observations']=[]
    window.set_project(p);window.add_parameter();window.params.selectRow(2);window.remove_rows(window.params)
    window.add_objective();window.objectives.selectRow(1);window.remove_rows(window.objectives)
    assert len(window.collect()['parameters'])==2 and len(window.collect()['objectives'])==1
    window.set_project(workflow_example('recipe'));window.clear_recipe()
    assert not window.collect().get('constraints') and window.params.item(0,6).text()=='0.1'

def test_recipe_editor_linear_ratio_remove_and_apply(window,monkeypatch):
    from chembo.recipe_dialog import RecipeDialog
    from PySide6.QtWidgets import QDialog
    p=workflow_example('recipe');p.update(observations=[],constraints=[])
    dialog=RecipeDialog(p,window)
    monkeypatch.setattr(QDialog,'exec',lambda self:QDialog.Accepted)
    dialog.add_linear();dialog.add_ratio()
    assert [r['kind'] for r in dialog.project['constraints']]==['linear','ratio']
    dialog.table.selectRow(1);dialog.remove()
    dialog.accept_checked()
    assert dialog.result()==QDialog.Accepted and len(dialog.project['constraints'])==1
    dialog.close()

def test_workbook_sheet_selection_and_cancel(window,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    from openpyxl import Workbook
    f=tmp_path/'sheets.xlsx';book=Workbook();book.active.title='first';book.create_sheet('second');book.save(f)
    monkeypatch.setattr(QInputDialog,'getItem',lambda *a:('second',True))
    assert window.choose_sheet(f)=='second'
    monkeypatch.setattr(QInputDialog,'getItem',lambda *a:('',False))
    assert window.choose_sheet(f) is False

def test_about_dialog_and_busy_menus(window,monkeypatch):
    from PySide6.QtWidgets import QDialog
    monkeypatch.setattr(QDialog,'exec',lambda self:QDialog.Rejected)
    window.about()
    window.busy(True)
    assert not window.menuBar().isEnabled() and all(not b.isEnabled() for b in window.action_buttons)
    window.busy(False);assert window.menuBar().isEnabled()
