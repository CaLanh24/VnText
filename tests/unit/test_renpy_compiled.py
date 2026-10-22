import pickle
import struct
import unittest
import zlib
from unittest.mock import patch

from vntext.renpy_compiled import Symbol, static_pickle, inspect_rpyc, compiled_dialogues, ast_nodes


class CompiledInspectionTests(unittest.TestCase):
    def test_known_revertable_dict_stays_inert_preserves_cycle_and_build_state(self):
        prefix=b'\x80\x02crenpy.revertable\nRevertableDict\n)\x81q\x00'
        result=static_pickle(prefix+b'(X\x04\x00\x00\x00selfh\x00u}X\x04\x00\x00\x00metaK\x07sb.')
        self.assertIsInstance(result,Symbol)
        self.assertEqual(result.args[0].args,'renpy.revertable.RevertableDict')
        self.assertIs(result.mapping['self'],result)
        self.assertEqual(result.state,{'meta':7})
        self.assertEqual(ast_nodes(result,('renpy.ast.',)),[])

    def test_ast_values_in_inert_mapping_are_visited_without_constructing_class(self):
        prefix=b'\x80\x02crenpy.revertable\nRevertableDict\n)\x81'
        node=b'crenpy.ast\nSay\n)\x81}X\x04\x00\x00\x00whatX\x05\x00\x00\x00Hellosb'
        result=static_pickle(prefix+b'X\x05\x00\x00\x00child'+node+b's.')
        self.assertEqual(ast_nodes(result,('renpy.ast.',)),[('renpy.ast.Say',{'what':'Hello'})])

    def test_mapping_subclasses_unknown_reducers_arguments_and_duplicates_refuse(self):
        fill=b'(X\x01\x00\x00\x00aK\x01u.'
        for constructor in [b'cevil\nRevertableDict\n)\x81',
                            b'crenpy.revertable\nRevertableDict\n)R',
                            b'ccollections\ndefaultdict\n)R',
                            b'ccollections\nOrderedDict\nK\x01\x85R',
                            b'crenpy.revertable\nRevertableDict\nK\x01\x85\x81']:
            with self.subTest(constructor=constructor),self.assertRaisesRegex(ValueError,'Malformed mapping'):
                static_pickle(b'\x80\x02'+constructor+fill)
        with self.assertRaisesRegex(ValueError,'Duplicate mapping key'):
            static_pickle(b'\x80\x02crenpy.revertable\nRevertableDict\n)\x81(X\x01\x00\x00\x00aK\x01X\x01\x00\x00\x00aK\x02u.')

    def test_exact_empty_ordered_dict_reducer_is_inert_and_keeps_order(self):
        payload=b'\x80\x02ccollections\nOrderedDict\n)R(X\x01\x00\x00\x00zK\x01X\x01\x00\x00\x00aK\x02u.'
        with patch('collections.OrderedDict',side_effect=AssertionError('reducer executed')):
            result=static_pickle(payload)
        self.assertEqual(result.kind,'REDUCE')
        self.assertEqual(list(result.mapping.items()),[('z',1),('a',2)])

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
