import pickle
import struct
import unittest
import zlib
from unittest.mock import patch

from vntext.renpy_compiled import Symbol, static_pickle, inspect_rpyc, compiled_dialogues


class CompiledInspectionTests(unittest.TestCase):
    def test_reduce_is_inert_and_never_calls_callable(self):
        payload=b'cbuiltins\neval\n(V1/0\ntR.'
        with patch('builtins.eval',side_effect=AssertionError('executed pickle')):
            result=static_pickle(payload.replace(b'V1/0\n',b'X\x03\x00\x00\x001/0'))
        self.assertIsInstance(result,Symbol)
        self.assertEqual(result.kind,'REDUCE')

    def test_cyclic_graph_preserves_identity_without_execution(self):
        value=[];value.append(value)
        result=static_pickle(pickle.dumps(value,protocol=4))
        self.assertIs(result,result[0])

    def test_rejects_external_buffers_persistent_ids_trailing_and_malformed(self):
        for payload in [b'\x80\x05\x97.',b'Psecret\n.',b'N.junk',b'h\x05.',b'0.']:
            with self.subTest(payload=payload),self.assertRaises(ValueError): static_pickle(payload)

    def test_slot_requires_valid_bounded_identity_payload(self):
        compressed=zlib.compress(pickle.dumps(({'version':1},[]),protocol=4))
        data=b'RENPY RPC2'+struct.pack('<III',2,34,len(compressed))+bytes(12)+compressed
        self.assertEqual(inspect_rpyc(data),({'version':1},[]))
        for bad in [data[:-1],b'bad',data[:14]+struct.pack('<I',10)+data[18:]]:
            with self.subTest(data=bad[:34]),self.assertRaises(ValueError): inspect_rpyc(bad)
        with self.assertRaisesRegex(ValueError,'version'): compiled_dialogues(data)
