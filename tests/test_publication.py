"""Source releases retain citation files and omit local metadata."""
import importlib.util
from pathlib import Path
import zipfile
import pytest


def load_script(name):
    path=Path(__file__).resolve().parents[1]/'scripts'/(name+'.py')
    spec=importlib.util.spec_from_file_location('nanobo_'+name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_source_archive_keeps_citations_and_excludes_private_metadata(tmp_path,monkeypatch):
    script=load_script('source_archive')
    for name in ['LICENSE','.gitignore','CITATION.cff','REFERENCES.bib','ACKNOWLEDGMENTS.md','src/chembo/app.py','docs/project-inventory/private.txt','src/.DS_Store','src/._app.py','upstream/gryffin/src/gryffin/kernel.pyxbldc']:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
    try:
        (tmp_path/'src/link.py').symlink_to(tmp_path/'LICENSE')
    except OSError as exc:
        if getattr(exc, 'winerror', None) == 1314:
            pytest.skip('The Windows test user cannot create symbolic links')
        raise
    monkeypatch.setattr(script,'ROOT',tmp_path)
    target=script.main()
    with zipfile.ZipFile(target) as archive:
        names=set(archive.namelist())
        assert {'NaNoBO/CITATION.cff','NaNoBO/REFERENCES.bib','NaNoBO/ACKNOWLEDGMENTS.md'}<=names
        assert not any('project-inventory' in name or name.endswith(('.DS_Store','._app.py','link.py','.pyxbldc')) for name in names)


def test_upstream_marker_accepts_recorded_url_and_sha(tmp_path,monkeypatch):
    script=load_script('bootstrap');target=tmp_path/'upstream/bo-mcp';target.mkdir(parents=True)
    commit=script.PINS['bo-mcp'][1]
    (target/'UPSTREAM_REVISION').write_text('https://github.com/AccelerationConsortium/bo-mcp\n'+commit+'\n2026-09-18\n')
    monkeypatch.setattr(script,'ROOT',tmp_path)
    def should_not_download(url):raise AssertionError('A recorded matching SHA should not be downloaded again')
    monkeypatch.setattr(script,'retrieve',should_not_download)
    assert script.fetch('bo-mcp')==target
