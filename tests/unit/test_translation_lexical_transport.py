import unittest
from tests.tools import translation_lexical_transport as t
from tests.tools.translation_quality_guard import protect

class TransportTests(unittest.TestCase):
    def row(self,source,domain='engineering measurement'):
        return dict(source_en=source,domain_context=domain)
    def test_domain_and_part_of_speech_controls(self):
        self.assertTrue(t.prepare(self.row('The temperature switch stops the heater.')).bindings)
        for source,domain in [('Switch to another screen.','engineering control'),('I am reading the manual.','engineering measurement'),('Invoice the client.','business'),('Roll back the carpet.','household'),('The sensor is ready.','ordinary conversation')]:
            self.assertFalse(t.prepare(self.row(source,domain)).bindings)
    def test_opaque_and_quoted_identity(self):
        r=t.prepare(self.row('The sensor sends {VALUE} to <b>sensor</b>.'))
        p=protect(r.working_source)
        raw=p.masked.replace('The ','').replace('sends','gửi').replace('to','tới')
        value=t.restore(r,p,raw)
        self.assertIn('cảm biến',value.lower());self.assertIn('{VALUE}',value);self.assertIn('<b>cảm biến</b>',value)
        self.assertFalse(t.prepare(self.row('Open "sensor".')).bindings)
        r=t.prepare(self.row('Read {sensor} now.'));self.assertFalse(r.bindings)
    def test_corrupt_carriers_fail_closed(self):
        r=t.prepare(self.row('The sensor reports {VALUE}.'));p=protect(r.working_source)
        for raw in [p.masked.replace(p.markers[0],''),p.masked+p.markers[0],p.masked.replace(p.markers[0],'[VNT999]')]:
            with self.assertRaises(ValueError):t.restore(r,p,raw)
        with self.assertRaises(ValueError):t.prepare(self.row('Read [LEX000].'))
    def test_counterfactual_scope(self):
        r=t.prepare(self.row('I would have waited if I had heard you.','conversation'))
        self.assertEqual(r.working_source,'[LEX000] waited [LEX001] heard you.')
        self.assertEqual(r.bindings, (('[LEX000]','tôi hẳn đã'),('[LEX001]','nếu trước đó tôi đã')))
        self.assertFalse(r.reordered)
        for source in ['I will wait if I hear you.','I would have waited if I had heard {NAME}.','She would have waited if she had heard you.','I would have waited if I had heard you and seen him.']:
            self.assertFalse(t.prepare(self.row(source,'conversation')).reordered)

    def test_longest_compound_and_exact_once(self):
        r=t.prepare(self.row('The temperature sensor and safety switch are ready.'))
        self.assertEqual(r.bindings,(('[LEX000]','cảm biến nhiệt độ'),('[LEX001]','công tắc an toàn')))
        self.assertEqual(r.working_source,'The [LEX000] and [LEX001] are ready.')
        p=protect(r.working_source)
        self.assertIn('cảm biến nhiệt độ',t.restore(r,p,p.masked))
