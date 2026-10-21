"""Bounded string-expression inspection; never evaluate code or names."""
import ast


def static_string(source):
    if not isinstance(source,str)or len(source)>65536:return None
    try:tree=ast.parse(source.strip(),mode='eval')
    except (SyntaxError,ValueError,RecursionError):return None
    if sum(1 for _ in ast.walk(tree))>256:return None
    def read(node,depth=0):
        if depth>32:return None
        if isinstance(node,ast.Constant)and isinstance(node.value,str):return node.value
        if isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id=='_'and len(node.args)==1 and not node.keywords:
            return read(node.args[0],depth+1)
        if isinstance(node,ast.BinOp)and isinstance(node.op,ast.Add):
            left=read(node.left,depth+1);right=read(node.right,depth+1)
            if left is not None and right is not None and len(left)+len(right)<=65536:return left+right
        return None
    value=read(tree.body)
    return value if value is not None and len(value)<=65536 else None


def string_classification(value):
    return 'TEMPLATE_WITH_INTERPOLATION'if '['in value.replace('[[','')else 'STATIC_RECOVERABLE'
