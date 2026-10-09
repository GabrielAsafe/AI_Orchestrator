from orchestrator.intelligence import analyze_project,markdown_report
from orchestrator.automation import tick
from orchestrator.registry import WorkerRegistry
from orchestrator.engine import Engine
from orchestrator.store import Store


def test_graph(tmp_path):
    (tmp_path/'example.py').write_text('import os\nfrom pathlib import Path\n')
    report=analyze_project(tmp_path)
    assert 'os' in report['imports']['example.py']
    assert 'example.py' in markdown_report(report)

def test_schedule_tick_idempotent(tmp_path):
    store=Store(tmp_path/'data.sqlite');eng=Engine(store,WorkerRegistry())
    try:
        store.add_schedule('scheduled','summarize',{'text':'hello'},60,100)
        one=tick(store,eng,now=100)
        two=tick(store,eng,now=100)
        assert len(one)==1 and two==[]
        assert len(store.list_jobs())==1
    finally:store.close()
