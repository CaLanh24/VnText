"""Frozen, single-candidate OPUS search feasibility; never changes product policy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / 'evaluation/translation_semantic_campaign_v1/frozen.json'
EVIDENCE = Path.home() / 'Downloads/VM-Acceptance'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['development', 'fresh'])
    stage = parser.parse_args().stage
    from tests.lib.work_paths import work_temp_dir
    from tests.tools import translation_quality_phase1 as provenance
    from vntext.mt_ct2_model import Ct2Translator
    from vntext.mt_ct2_io import _batch_translate_chunk
    from vntext.mt_check import structural_problems
    import ctranslate2
    frozen_bytes = FROZEN.read_bytes()
    frozen_sha = hashlib.sha256(frozen_bytes).hexdigest()
    frozen = json.loads(frozen_bytes)
    if stage == 'fresh':
        review = json.loads((ROOT / 'evaluation/translation_semantic_campaign_v1/development-review.json').read_text(encoding='utf-8'))
        assert review['admitted'] is True and review['frozen_sha256'] == frozen_sha
    output = EVIDENCE / f'semantic-beam-{stage}.json'
    assert not output.exists(), output
    work = work_temp_dir('semantic-beam-' + stage)
    for name in ('TEMP', 'TMP', 'TMPDIR'):
        os.environ[name] = str(work)
    provenance._configure_offline_cache()
    os.environ['VNTEXT_CT2_NO_DOWNLOAD'] = '1'
    os.environ['VNTEXT_CT2_INTER_THREADS'] = '1'
    os.environ['VNTEXT_CT2_INTRA_THREADS'] = '1'
    samples = frozen[stage]
    report = dict(status='RUN_STARTED', stage=stage, frozen_sha256=frozen_sha,
                  source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  source_hashes={n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                      ['vntext/mt_ct2_model.py', 'vntext/mt_ct2_io.py', 'vntext/mt_check.py',
                       'tests/tools/translation_semantic_beam_probe.py']},
                  model=provenance._model_identity(), runtime=ctranslate2.__version__,
                  installed_signature=ctranslate2.Translator.translate_batch.__doc__.splitlines()[0],
                  limits=frozen['budget'], rows=[], calls=[], memory=[],
                  authority='First product batch/preprocessing seam only, not final pipeline/cache/patch or semantic acceptance')
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    def memory_guard():
        sample = provenance._windows_process_memory()
        report['memory'].append(sample)
        assert sample['available'], sample
        assert sample['peak_working_set_bytes'] < frozen['budget']['memory_peak_bytes_max'], sample
        assert time.monotonic()-started < 170, 'Internal time guard'
    started = time.monotonic()
    save()
    try:
        memory_guard()
        translator = Ct2Translator(provenance.MODEL_DIR)
        backend = translator._translator
        memory_guard()
        report['translator_config'] = translator.config
        for profile, beam in [('baseline', 2), ('candidate', 4)]:
            class Capture:
                def translate_batch(self, tokens, **kwargs):
                    memory_guard()
                    count = sum(len(x['input_lengths']) for x in report['calls'])
                    assert count + len(tokens) <= len(samples)*2, 'Output budget exceeded'
                    kwargs['beam_size'] = beam
                    call_start = time.monotonic()
                    results = backend.translate_batch(tokens, **kwargs)
                    report['calls'].append(dict(profile=profile, kwargs=kwargs,
                        input_lengths=[len(t) for t in tokens],
                        output_lengths=[len(r.hypotheses[0]) for r in results],
                        elapsed_seconds=time.monotonic()-call_start))
                    save()
                    return results
            translator._translator = Capture()
            for row in samples:
                memory_guard()
                record = dict(key=row['id'], source_text=row['source'], file_path='semantic-fixture.txt',
                              context='semantic:' + row['id'], import_method='plain_text_line')
                begin = time.monotonic()
                text = _batch_translate_chunk(translator, [record])[record['key']]
                issues = structural_problems(record, text) if text else ['empty']
                report['rows'].append(dict(id=row['id'], profile=profile, source=row['source'],
                    translation=text, structural_issues=issues, elapsed_seconds=time.monotonic()-begin))
                memory_guard()
                save()
        assert FROZEN.read_bytes() == frozen_bytes
        assert provenance._model_identity()['tree_sha256'] == report['model']['tree_sha256']
        report.update(status='COMPLETED_FOR_SOURCE_ALIGNED_REVIEW', elapsed_seconds=time.monotonic()-started)
    except BaseException as error:
        report.update(status='FAILED', error=repr(error), elapsed_seconds=time.monotonic()-started)
        raise
    finally:
        save()
    print(json.dumps(dict(status=report['status'], rows=len(report['rows']), elapsed_seconds=report['elapsed_seconds'])))


if __name__ == '__main__':
    main()
