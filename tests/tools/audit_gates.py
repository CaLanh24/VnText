"""Finite public/installed/native gate router. A missing prerequisite never counts as PASS."""
from pathlib import Path
import argparse,json,os,re,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[2]
GROUPS={
 'public-csv':['tests.unit.test_csv_editor_api','tests.unit.test_csv_transaction_regressions','tests.unit.test_audit_regressions'],
 'public-mt':['tests.unit.test_mt_vietnamese_homographs','tests.unit.test_mt_ct2_long_input','tests.unit.test_mt_ct2_status','tests.unit.test_user_glossary','tests.unit.test_glossary_context_v2','tests.unit.test_glossary_masking','tests.unit.test_mt_real_game_fixes'],
 'public-patch':['tests.unit.test_patch_input_safety','tests.unit.test_patch_bundle.PatchBundleFormatTests','tests.unit.test_patch_bundle.PatchInstallerUiSourceTests','tests.unit.test_patch_readback','tests.unit.test_audit_seams'],
 'public-maintenance':['tests.unit.test_registry_storage','tests.unit.test_cleanup_verification_memory','tests.unit.test_dev_bootstrap','tests.unit.test_dependency_profiles'],
}
def main():
 p=argparse.ArgumentParser();p.add_argument('--group',choices=['public','installed-runtime',*GROUPS],default='public');p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 results={}
 if a.group=='installed-runtime':
  stub=Path(os.environ.get('VNTEXT_PATCH_INSTALLER') or ROOT/'release/patch_installer_publish/VNTextPatchInstaller.exe')
  selected={'installed-runtime':['tests.unit.test_patch_bundle.PatchBundleRuntimeTests']} if stub.is_file() else {}
  if not selected:results['installed-runtime']={'outcome':'BLOCKED','reason':'Set VNTEXT_PATCH_INSTALLER to the exact built installer; no build/download is implicit.'}
 else:selected=GROUPS if a.group=='public' else {a.group:GROUPS[a.group]}
 for name,modules in selected.items():
  start=time.monotonic();run=subprocess.run([sys.executable,'-B','-m','unittest',*modules],cwd=ROOT,encoding='utf8',errors='replace',capture_output=True)
  log=a.report.with_name(a.report.stem+'-'+name+'.log');log.write_text(run.stdout+run.stderr,encoding='utf8')
  counts=re.search(r'Ran (\d+) tests?',run.stderr);skips=re.search(r'skipped=(\d+)',run.stderr)
  results[name]={'tests_run':int(counts[1]) if counts else None,'skipped_tests':int(skips[1]) if skips else 0,'outcome':'PASS' if run.returncode==0 else 'FAIL','exit_code':run.returncode,'elapsed_seconds':round(time.monotonic()-start,2),'log':str(log),'modules':modules}
 results['installed-model']={'outcome':'SKIP','reason':'Run offline MT corpus separately with an explicitly acquired model; public tests do not download models.'}
 results['native']={'outcome':'SKIP','reason':'Requires unlocked Windows desktop, exact candidate/hash and independent agent-desktop checklist; harness is not live acceptance.'}
 result={'groups':results,'outcome':'FAIL' if any(r['outcome']=='FAIL' for r in results.values()) else ('BLOCKED' if any(r['outcome']=='BLOCKED' for r in results.values()) else 'PASS'),'boundary':'PASS applies only to selected public deterministic groups; installed/native remain SKIP'}
 a.report.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result));return 0 if result['outcome']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
