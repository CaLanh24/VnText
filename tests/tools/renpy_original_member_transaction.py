"""Exact Owner RPYC member-derived transaction; never a full-game claim."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from tests.lib.work_paths import work_temp_dir
from tests.tools.renpy_owner_font_audit import original_members, EVIDENCE
from tests.tools.renpy_declared_sample import create_declared_sample
from tests.tools.renpy_real_game_gate import identity
from vntext.renpy_compiled import extract_compiled_source
from vntext.package_io import write_package
from vntext.patch_pipeline import apply_translation_package
from vntext.renpy_toolchain import validate_sdk

ROOT = Path(__file__).resolve().parents[2]
REPORT = EVIDENCE / 'renpy-original-member-transaction-20261022.json'
EXPECTED = 'fadc20d18f3ca4613a65885c4f5299491ca9f756d2b9bbf6fb9dcb5d1a7782ae'


def save(report):
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    if REPORT.exists():
        raise ValueError('prior receipt exists')
    report = {'outcome': 'STARTED', 'scope': 'EXACT_ORIGINAL_COMPILED_MEMBER_DERIVED_TRANSACTION_NOT_FULL_GAME',
              'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    save(report)
    try:
        members, pre = original_members()
        raw = members['screens.rpyc']
        assert len(raw) == 240759 and hashlib.sha256(raw).hexdigest() == EXPECTED
        report['origin'] = {'rar_sha256': pre['source_sha256'], 'rpa_sha256': pre['rpa_sha256'],
                            'member': 'screens.rpyc', 'bytes': len(raw), 'sha256': EXPECTED,
                            'distribution': 'Original RPA mixed source/compiled; unchanged member copied directly, no deletion/repack'}
        pairs = json.loads((EVIDENCE / 'renpy-owner-rar-run4-translations.json').read_text(encoding='utf-8-sig'))[:2]
        del members
        sdk = validate_sdk(ROOT / '.dev-env/tools/renpy-8.5.3')
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-original-member')) as temp:
            work = Path(temp); game = work / 'member-derived'; (game / 'game').mkdir(parents=True)
            compiled = game / 'game/screens.rpyc'; compiled.write_bytes(raw)

            def extract(output):
                main, review, stats = extract_compiled_source(game)
                write_package(str(output), main, review, stats, True)
                status = {'status': 'PARTIAL' if stats['errors'] or review else 'COMPLETE',
                          'errors': stats['errors'], 'review': len(review), 'main': len(main), 'scope': report['scope']}
                (output / 'extract_status.json').write_text(json.dumps(status), encoding='utf-8')
                return json.loads((output / 'manifest.json').read_text(encoding='utf-8')), status

            first, status = extract(work / 'full')
            selected = []
            for native_id, pair in zip(('start_a4a14dc7', 'start_20ab3953'), pairs):
                entry = next(e for e in first['entries'] if e['locator'].get('native_id') == native_id)
                assert entry['source_text'] == pair['source_text'] and entry['backend'] == 'renpy_compiled_static'
                selected.append({**pair, 'key': entry['key']})
            report['full_status'] = status
            report['declared_provenance'] = create_declared_sample(work / 'full', work / 'sample', selected)
            for stage, package in [('patch', work / 'sample'), ('repatch', work / 'repeat-sample')]:
                apply_translation_package(str(package / 'translation.csv'), str(package / 'manifest.json'), str(game), str(work / stage))
                report[stage + '_verification'] = json.loads((work / stage / 'patch_verification.json').read_text(encoding='utf-8'))
                shutil.copytree(work / stage / 'COPY_TO_GAME_ROOT', game, dirs_exist_ok=True)
                probe = 'init 999 python:\n    import json, os\n    renpy.game.preferences.language = "vietnamese"\n    result = {}\n'
                for native_id, pair in zip(('start_a4a14dc7', 'start_20ab3953'), selected):
                    probe += f'    node, translated = renpy.game.script.translator.lookup_translate({native_id!r})\n    result[{native_id!r}] = [node.what, translated]\n'
                probe += '    with open(os.path.join(config.basedir, "readback.json"), "w", encoding="utf-8") as stream:\n        json.dump(result, stream, ensure_ascii=False)\n'
                (game / 'game/member_probe.rpy').write_text(probe, encoding='utf-8')
                run = subprocess.run([str(sdk.python), str(sdk.renpy_py), str(game), 'lint'], cwd=sdk.root,
                                     capture_output=True, text=True, encoding='utf-8', timeout=60)
                report[stage + '_sdk'] = {'exit': run.returncode, 'stdout': run.stdout[-6000:], 'stderr': run.stderr[-3000:]}
                save(report)
                assert run.returncode == 0, report[stage + '_sdk']
                rb = json.loads((game / 'readback.json').read_text(encoding='utf-8'))
                assert rb == {key: [pair['translation'], True] for key, pair in zip(('start_a4a14dc7', 'start_20ab3953'), selected)}, rb
                report[stage + '_readback'] = rb
                assert compiled.read_bytes() == raw
                # Remove only this helper's probe/SDK-generated counterpart before re-extract.
                (game / 'game/member_probe.rpy').unlink()
                (game / 'game/member_probe.rpyc').unlink(missing_ok=True)
                if stage == 'patch':
                    second, repeat_status = extract(work / 'repeat')
                    assert identity(first) == identity(second)
                    report['reextract_identity'] = True
                    report['repeat_status'] = repeat_status
                    create_declared_sample(work / 'repeat', work / 'repeat-sample', selected)
            report['original_member_preserved'] = hashlib.sha256(compiled.read_bytes()).hexdigest() == EXPECTED
        report['outcome'] = 'PASS_MEMBER_DERIVED_TRANSACTION'
    except Exception as error:
        report.update(outcome='FAIL', error=repr(error))
        raise
    finally:
        save(report)


if __name__ == '__main__':
    main()
