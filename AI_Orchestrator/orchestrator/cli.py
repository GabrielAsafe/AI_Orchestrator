"""CLI principal. Executa: python3 -m orchestrator ..."""
import argparse, json, os, signal, sys, time
from pathlib import Path
from .config import load_config
from .registry import WorkerRegistry
from .store import Store
from .engine import Engine
from .models import ActionProposal, new_id
from .iot import PolicyGate, process_proposal
from .coding import parse_patch, preview_edits, apply_edits, verify, create_worktree, repo_allowed
from .intelligence import analyze_project, markdown_report
from .automation import tick

def build(config_file='config/orchestrator.toml', workers_file='config/workers.json'):
    conf=load_config(config_file)
    store=Store(conf['storage']['db_path'])
    registry=WorkerRegistry.from_json(workers_file)
    return Engine(store,registry),conf

def output(data):
    print(json.dumps(data,indent=2,ensure_ascii=False,default=str))

def main(argv=None):
    parser=argparse.ArgumentParser(prog='orchestrator',description='Control plane SQLite / Raspberry Pi')
    parser.add_argument('--config',default='config/orchestrator.toml')
    parser.add_argument('--workers',default='config/workers.json')
    subs=parser.add_subparsers(dest='cmd',required=True)
    subs.add_parser('doctor')
    subs.add_parser('workers')
    subs.add_parser('health')
    submit=subs.add_parser('submit');submit.add_argument('type');submit.add_argument('text')
    submit.add_argument('--key');submit.add_argument('--priority',type=int,default=0)
    submit.add_argument('--worker');submit.add_argument('--attempts',type=int,default=2)
    subs.add_parser('run-once');subs.add_parser('run');subs.add_parser('jobs')
    for command in ('status','result','history','explain','cancel'):
        p=subs.add_parser(command);p.add_argument('job_id')
    subs.add_parser('metrics')
    p=subs.add_parser('backup');p.add_argument('path')
    p=subs.add_parser('serve')
    p=subs.add_parser('fake-worker');p.add_argument('--port',type=int,default=8089)
    p=subs.add_parser('iot');p.add_argument('action');p.add_argument('resource')
    p.add_argument('--key');p.add_argument('--mode',choices=['shadow','fake'],default='shadow')
    p.add_argument('--enable-fake',action='store_true')
    p=subs.add_parser('coding-preview');p.add_argument('repo');p.add_argument('patch')
    p=subs.add_parser('coding-apply');p.add_argument('repo');p.add_argument('patch');p.add_argument('--approve',action='store_true')
    p=subs.add_parser('coding-check');p.add_argument('repo');p.add_argument('--check',choices=['unit_tests','syntax_check'],default='syntax_check')
    p=subs.add_parser('worktree');p.add_argument('repo');p.add_argument('destination');p.add_argument('branch')
    p=subs.add_parser('analyze');p.add_argument('repo')
    p=subs.add_parser('schedule-add');p.add_argument('type');p.add_argument('text');p.add_argument('--every',type=int,required=True)
    subs.add_parser('schedule-tick')
    args=parser.parse_args(argv)
    if args.cmd == 'fake-worker':
        from .fake_worker import run
        return run(port=args.port)
    if args.cmd == 'doctor':
        import platform, sqlite3
        output({'python':sys.version.split()[0],'platform':platform.machine(),
                'sqlite':sqlite3.sqlite_version,'cwd':os.getcwd(),
                'config_file':args.config,'workers_file':args.workers})
        return 0
    if args.cmd in ('coding-preview','coding-apply','coding-check','worktree','analyze'):
        # As ações de coding têm de ser permitidas explicitamente pelo proprietário.
        if args.cmd == 'analyze':
            print(markdown_report(analyze_project(args.repo)))
            return 0
        allow=[p for p in os.getenv('ORCH_ALLOWED_REPOS','').split(os.pathsep) if p]
        if not allow or not repo_allowed(args.repo,allow):
            raise PermissionError('Configura ORCH_ALLOWED_REPOS com caminhos de repositórios permitidos')
        if args.cmd == 'worktree':
            output({'worktree':create_worktree(args.repo,args.destination,args.branch)});return 0
        if args.cmd == 'coding-check':
            output(vars(verify(args.repo,[args.check])));return 0
        edits=parse_patch(Path(args.patch).read_text(encoding='utf-8'))
        diff=preview_edits(args.repo,edits)
        print(diff or '(sem alterações)')
        if args.cmd=='coding-apply':
            if not args.approve:
                raise PermissionError('Falta --approve')
            # exige explicitamente worktree, não a branch principal
            import subprocess
            branch=subprocess.run(['git','-C',args.repo,'branch','--show-current'],capture_output=True,text=True,check=True).stdout.strip()
            if not branch.startswith('lesson/'):
                raise PermissionError('Apenas branch lesson/*, idealmente num git worktree')
            output({'applied_files':apply_edits(args.repo,edits,approved=True)})
        return 0
    engine,conf=build(args.config,args.workers)
    try:
        if args.cmd == 'workers':output(engine.registry.as_rows())
        elif args.cmd == 'health':
            for spec in engine.registry.specs.values():engine.registry.probe(spec.id)
            output(engine.registry.as_rows())
        elif args.cmd == 'submit':
            output({'job_id':engine.submit(args.type,args.text,args.priority,args.key,args.attempts,args.worker)})
        elif args.cmd == 'jobs':output(engine.store.list_jobs())
        elif args.cmd in ('status','result'):
            job=engine.store.get(args.job_id)
            if not job:output({'error':'not_found'});return 1
            if args.cmd=='result':
                output(json.loads(job['result_json']) if job['result_json'] else {'state':job['state'],'error':job['error_type']})
            else:output(job)
        elif args.cmd=='history':output({'events':engine.store.history(args.job_id),'attempts':engine.store.attempts(args.job_id)})
        elif args.cmd=='explain':
            job=engine.store.get(args.job_id)
            if not job:output({'error':'not_found'});return 1
            output({'state':job['state'],'error':job['error_type'],'events':engine.store.history(args.job_id),
                    'attempts':engine.store.attempts(args.job_id)})
        elif args.cmd=='cancel':output({'cancelled':engine.store.cancel(args.job_id)})
        elif args.cmd=='metrics':output(engine.store.metrics())
        elif args.cmd=='backup':engine.store.backup(args.path);output({'backup':args.path})
        elif args.cmd=='run-once':
            for spec in engine.registry.specs.values():engine.registry.probe(spec.id)
            output(engine.step())
        elif args.cmd=='run':
            should_stop=[False]
            def stop(*_):should_stop[0]=True
            signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
            engine.store.reconcile()
            while not should_stop[0]:
                for spec in engine.registry.specs.values():engine.registry.probe(spec.id)
                tick(engine.store,engine)
                outcome=engine.step()
                if outcome['status'] in ('idle','queued'):
                    time.sleep(conf['scheduler']['idle_seconds'])
        elif args.cmd=='serve':
            from .server import run
            run(engine,conf['server']['host'],conf['server']['port'])
        elif args.cmd=='iot':
            proposal=ActionProposal(args.action,args.resource,{})
            output(process_proposal(engine.store,proposal,PolicyGate(),mode=args.mode,
                                    autonomy_enabled=args.enable_fake,idempotency_key=args.key))
        elif args.cmd=='schedule-add':
            sid=new_id('sched')
            engine.store.add_schedule(sid,args.type,{'text':args.text},args.every,int(time.time())+args.every)
            output({'schedule_id':sid})
        elif args.cmd=='schedule-tick':output({'submitted':tick(engine.store,engine)})
        return 0
    finally:
        engine.store.close()

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError,PermissionError,FileNotFoundError,RuntimeError,KeyError) as exc:
        print('%s: %s' % (type(exc).__name__,exc),file=sys.stderr)
        sys.exit(2)
