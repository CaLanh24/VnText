"""Project immutable local campaign evidence into a compact public receipt.

Run with python -B -m tests.tools.translation_goal_receipt. No inference,
approval, training, or artifact cleanup is performed by this projection.
"""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'DEV_RUN/translation-quality-goal'
EXTERNAL = Path.home() / 'Downloads/VM-Acceptance'
OUTPUT = ROOT / 'evaluation/translation_quality_goal_v1/receipt.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def reference(path):
    return dict(name=path.name, sha256=sha(path), size_bytes=path.stat().st_size)


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    baseline = read(RAW / 'baseline.json')
    final = read(RAW / 'final-headwords.json')
    workflow = read(RAW / 'workflow-headwords.json')
    longtext = read(RAW / 'longtext-before.json')
    build = read(ROOT / 'DEV_RUN/bootstrap-build/build-identity.json')
    smoke = read(ROOT / 'DEV_RUN/bootstrap-build/smoke.json')
    affected_path = EXTERNAL / 'translation-goal-final-affected.json'
    affected = read(affected_path)
    skip_path = EXTERNAL / 'translation-goal-qa-skip-details.json'
    skips = read(skip_path)
    build_path = EXTERNAL / 'translation-goal-dev-final-wrapper.json'
    build_gate = read(build_path)
    workflow_path = EXTERNAL / 'translation-goal-workflow-headwords-module-wrapper.json'
    workflow_gate = read(workflow_path)
    assert baseline['status'] == final['status'] == 'COMPLETED'
    assert baseline['dataset_sha256'] == final['dataset_sha256']
    assert baseline['model']['tree_sha256'] == final['model']['tree_sha256']
    assert final['model_unchanged'] and workflow['status'] == 'PASS'
    assert smoke['ok'] and smoke['exit_code'] == 0 and smoke['cleanup_error'] is None
    assert workflow['worker_exit_code'] is not None and workflow['input_unchanged']
    for gate in (affected, skips, build_gate, workflow_gate):
        assert gate['status'] == 'PASS' and gate['child_exit_code'] == 0
        assert gate['cleanup']['status'] == 'PASS'
    for name, digest in final['code_hashes'].items():
        assert sha(ROOT / name) == digest, name
    assert sha(ROOT / 'vntext/mt_check.py') == longtext['code_hashes']['vntext/mt_check.py']
    assert sha(Path(build['executable'])) == build['sha256']
    files = subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT, text=True).splitlines()
    files += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    source_files = sorted({n for n in files if n.startswith(('vntext/', 'tests/'))})
    receipt = dict(
        schema_version=1, outcome='IMPLEMENTED_PENDING_BRAIN_ACCEPTANCE',
        base_source_sha=final['source_sha'], dirty_runtime=True,
        exact_commit_build=False, final_commit_does_not_relabel_run_provenance=True,
        model=dict(repository=final['model']['repository'],
                   declared_revision=final['model']['declared_revision'],
                   tree_sha256=final['model']['tree_sha256'], unchanged=True),
        dataset=dict(sha256=final['dataset_sha256'], rows=100,
                     previously_seen=True, human_gold=False, generalization_claim=False),
        arms=[], changed_rows=final['changed_rows'],
        runtime_and_test_file_hashes={n:sha(ROOT/n) for n in source_files},
        provenance_caveat='Original final audit omitted mt_check from code_hashes; separate owner identity and later longtext capture retain its hash. Supplement is not an original audit field.',
        source_identity_supplement=reference(RAW/'headwords-owner-identity.json'),
        workflow=dict(status=workflow['status'], branches=workflow['branches'],
                      worker_exit_code=workflow['worker_exit_code'], input_unchanged=True,
                      worker_lifecycle='Existing _stop_worker explicitly terminates idle child after task completion; native exit1 retained, helper/wrapper exit0 is separate.',
                      donor='agent-authored controlled fixture; not human gold or approved product memory'),
        affected_tests=affected['test_summary'], skip_details=skips['test_summary'],
        build=dict(configuration=build['configuration'], source_sha=build['source_sha'],
                   source_diff_sha256=build['source_diff_sha256'], executable='DEV_RUN/bootstrap-build/VNText.Studio.App.exe',
                   sha256=build['sha256'], assembly_sha256=build['assembly_sha256']),
        worker_smoke=dict(ok=smoke['ok'], exit_code=smoke['exit_code'],
                          steps=[s['step'] for s in smoke['steps']],
                          installer_acceptance=False, caveat='Payload read-back succeeds; patch installer absent.'),
        semantic_disposition='docs/TRANSLATION_QUALITY_PLAN.md: Current measured semantic disposition and remaining acceptance',
        training='NOT_TRIGGERED/DEFERRED', silver_imported=False,
        remaining=['Brain whole-goal acceptance including explicit residual semantic limits',
                   'human semantic acceptance is not established by agent audit'],
        raw_references=[reference(RAW/n) for n in ('baseline.json','final.json','final-headwords.json',
                        'workflow.json','workflow-headwords.json','longtext-before.json',
                        'sentence-probe.json','sentence-probe-numeric.json')]
                       + [reference(p) for p in (affected_path,skip_path,build_path,workflow_path)],
    )
    for old, new in zip(baseline['arms'], final['arms']):
        assert old['name'] == new['name']
        assert old['fields'] == new['fields'] and new['source_order_schema_unchanged']
        assert [(r['id'],r['source']) for r in old['rows']] == [(r['id'],r['source']) for r in new['rows']]
        assert not any(r['structural_reasons'] for r in new['rows'])
        receipt['arms'].append(dict(name=new['name'], before_written=old['result']['translated'],
                                    before_blocked=old['result']['blocked'], after_written=new['result']['translated'],
                                    after_blocked=new['result']['blocked'], new_written_structural_failures=0))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(outcome=receipt['outcome'], receipt=str(OUTPUT), sha256=sha(OUTPUT))))


if __name__ == '__main__':
    main()
