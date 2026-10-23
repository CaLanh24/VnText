import unittest

from tests.tools.renpy_owner_rar_gate import wait_native_process


class FakeClock:
    def __init__(self):
        self.value=0.0

    def monotonic(self):
        return self.value

    def sleep(self,seconds):
        self.value+=seconds


class FakeProcess:
    def __init__(self, exit_after=None):
        self.exit_after=exit_after
        self.poll_count=0
        self.returncode=None
        self.terminated=False

    def poll(self):
        self.poll_count+=1
        if self.exit_after is not None and self.poll_count>self.exit_after:
            self.returncode=0
        return self.returncode

    def terminate(self):
        self.terminated=True
        self.returncode=1

    def wait(self,timeout=None):
        return self.returncode

    def kill(self):
        self.returncode=-9


class NativeLifecycleTests(unittest.TestCase):
    def run_wait(self,process,*,timeout,finish=lambda:False):
        clock=FakeClock()
        result=wait_native_process(process,started_monotonic=0.0,deadline_monotonic=timeout,timeout_seconds=timeout,
            finish_requested=finish,clock=clock.monotonic,sleep=clock.sleep,
            utc_now=lambda:'2026-10-23T00:00:00Z')
        return result,clock

    def test_natural_exit_is_not_reported_as_harness_termination(self):
        process=FakeProcess(exit_after=1)
        result,_=self.run_wait(process,timeout=5)
        self.assertEqual(result['termination_reason'],'PROCESS_EXITED')
        self.assertFalse(result['terminated_by_harness'])
        self.assertEqual(result['exit_code'],0)

    def test_finish_signal_terminates_owned_process(self):
        process=FakeProcess()
        result,_=self.run_wait(process,timeout=5,finish=lambda:True)
        self.assertEqual(result['termination_reason'],'FINISH_SIGNAL')
        self.assertTrue(result['terminated_by_harness'])
        self.assertTrue(process.terminated)

    def test_deadline_terminates_owned_process_at_bound(self):
        process=FakeProcess()
        result,clock=self.run_wait(process,timeout=3)
        self.assertEqual(result['termination_reason'],'DEADLINE')
        self.assertTrue(result['terminated_by_harness'])
        self.assertEqual(result['elapsed_seconds'],3)
        self.assertEqual(clock.value,3)

    def test_observation_error_still_terminates_owned_process(self):
        process=FakeProcess()
        clock=FakeClock()
        with self.assertRaisesRegex(RuntimeError,'observation failed'):
            wait_native_process(process,started_monotonic=0,deadline_monotonic=5,timeout_seconds=5,
                finish_requested=lambda:(_ for _ in ()).throw(RuntimeError('observation failed')),
                clock=clock.monotonic,sleep=clock.sleep)
        self.assertTrue(process.terminated)


if __name__=='__main__':
    unittest.main()
