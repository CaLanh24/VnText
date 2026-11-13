"""Bounded string-expression inspection; never evaluate code or names."""
import ast
import re


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


# ---------------------------------------------------------------------------------------------------------------------------
# Display-purpose classification of a STATIC screen string.  This separates "what the player reads" from machine syntax so a user never has
# to triage syntax: HUMAN rows are translated and written back; TECHNICAL rows are excluded automatically and kept in an internal audit.
# It looks at the visible content (markup and interpolations removed), never at a word blacklist, so real prose with tags stays HUMAN.
_ESCAPED_BRACKET = "\x00"
_INTERPOLATION = re.compile(r"\[[^\[\]]+\]")
_MARKUP_TAG = re.compile(r"\{/?[A-Za-z#!][^{}]*\}|\{\}")
_ENGINE_INTERPOLATION = re.compile(r"\[(?:renpy\.(?:version|license|copyright)\w*|config\.(?:renpy_version|engine_version))\b")
_RESOURCE_NAME = re.compile(r"[\w./\\-]+\.(?:png|jpe?g|webp|gif|ogg|mp3|wav|opus|ttf|otf|webm|mp4|rpy|rpyc)", re.IGNORECASE)
_WORD = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


def visible_ui_text(value):
    """The text a player can read: translator markers ({#x}), markup tags and [interpolations] removed (link labels are kept)."""
    text = value.replace("[[", _ESCAPED_BRACKET)
    text = _INTERPOLATION.sub(" ", text)
    text = _MARKUP_TAG.sub("", text)
    return text.replace(_ESCAPED_BRACKET, "[")


def classify_ui_text(value):
    """('HUMAN', '') for player-readable text, else ('TECHNICAL', reason).  Context-free on purpose: only the string's own visible content decides."""
    if not isinstance(value, str) or not value.strip():
        return "TECHNICAL", "empty"
    raw = value.replace("[[", _ESCAPED_BRACKET)
    if _ENGINE_INTERPOLATION.search(raw):
        return "TECHNICAL", "engine_metadata"          # Ren'Py version/licence credit boilerplate: engine-owned, not game text
    visible = visible_ui_text(value)
    stripped = visible.strip()
    if _RESOURCE_NAME.fullmatch(stripped):
        return "TECHNICAL", "resource_name"
    if not _WORD.search(stripped):
        return "TECHNICAL", "no_visible_words"         # glyphs ("<", ">"), single letters ("A"), numbers, interpolation-only ("[page]")
    return "HUMAN", ""
