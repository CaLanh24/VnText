"""Shared constants and standard-library imports for extraction families."""

from __future__ import annotations


from collections import Counter


import array


import concurrent.futures


import mmap


import os


import re


import struct


import threading


import time


import unicodedata


from pathlib import Path


from typing import Any, Callable, Iterable


from vntext.entry import Entry, make_key


TEXT_EXTS = {".txt", ".json", ".csv", ".xml", ".yaml", ".yml", ".nani", ".scenario", ".bytes"}


UNITY_EXTS = {".assets", ".bundle", ".unity3d", ".sharedassets"}


UNITY_DATA_BLOB_EXTS = {".resource", ".ress", ".resS"}


SKIP_DEEP_EXTS = {
    ".png", ".jpg", ".jpeg", ".ogg", ".mp3", ".wav", ".wem", ".bank", ".mp4",
    ".dll", ".exe", ".pdb", ".dat", ".resource", ".ress", ".resS",
    ".config", ".info", ".ini", ".log", ".sys",
}


MAX_TEXT_LINE_CHARS = 20000


MAX_RAW_GROUP_BYTES = 262144


MAX_RAW_SCAN_FILE_BYTES = 16 * 1024 * 1024


UNITY_UI_SCAN_MAX_FILE_BYTES = 24 * 1024 * 1024


NANINOVEL_WINDOW_BEFORE = 2048


NANINOVEL_WINDOW_AFTER = 4096


ASSET_INDEX_FIELDS = ["file_path", "path_id", "type", "name", "size", "container"]


PRINTABLE_UTF8 = re.compile(rb"[\x09\x0a\x0d\x20-\x7e\xc2-\xf4][\x09\x0a\x0d\x20-\x7e\x80-\xbf\xc2-\xf4]{3,}")


UTF16LE_ASCII = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")


ASCII_WINDOW_TEXT = re.compile(rb"[\x20-\x7e]{2,240}")


QUOTED = re.compile(r'"([^"\r\n]{2,})"')


GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


HEX_RE = re.compile(r"^(?:0x)?[0-9a-fA-F]{8,}$")


CODE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")


PATH_RE = re.compile(r"(^[A-Za-z]:\\|[\\/]|(?:\.(?:png|jpg|jpeg|dds|tga|psd|wav|ogg|mp3|prefab|mat|shader|anim|controller|asset|bundle|dll|cs|json|xml|bytes))$)", re.IGNORECASE)


UNITY_NOISE_WORDS = {
    "unityengine", "monobehaviour", "scriptableobject", "transform", "gameobject",
    "meshfilter", "meshrenderer", "material", "shader", "texture2d", "sprite",
    "audioclip", "animationclip", "assetbundle", "resources", "assembly-csharp",
    "system.collections", "mscorlib", "serializedfile", "typetree",
}


TECH_FIELD_WORDS = {
    "script", "methodname", "assemblytypename", "trigger", "sprite", "font",
    "material", "shader", "target", "objectargument", "assetguid", "address",
    "path", "key", "id", "guid",
}


TEXT_FIELD_WORDS = {
    "text", "title", "description", "desc", "message", "dialogue", "dialog",
    "line", "content", "label", "caption", "tooltip", "choice", "question",
    "answer", "displayname", "display_name", "body", "summary",
}


UI_SHORT_TEXT = {
    "ok", "yes", "no", "on", "off", "new", "load", "save", "start", "exit",
    "back", "next", "skip", "auto", "menu", "close", "open", "retry", "resume",
    "continue", "settings", "options", "language", "gallery", "extra", "help",
    "agree", "disagree", "warning", "return", "tips", "tip",
}


_UI_TITLE_LABEL_RE = re.compile(r"^[A-Z][A-Za-z']*(?:[ ][A-Z][A-Za-z']*){0,4}$")


_CAMEL_TYPE_RE = re.compile(r"[a-z][A-Z]")


DEMO_OR_PLACEHOLDER_RE = re.compile(
    r"(lorem\s+ipsum|asdf(?:[a-z]{3,})|logged\s+text|sample\s+choice|block\s*info(?:block\s*info){2,})",
    re.IGNORECASE,
)


ASSIGNMENT_OR_CODE_RE = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_.]+)\s*(?:=|<=|>=|==|!=)",
)


CONTROL_JUNK_RE = re.compile(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]")


_VIETNAMESE_CHARS = frozenset(
    "ăâđêôơưĂÂĐÊÔƠƯ"
    "áàảãạÁÀẢÃẠấầẩẫậẤẦẨẪẬắằẳẵặẮẰẲẴẶ"
    "éèẻẽẹÉÈẺẼẸếềểễệẾỀỂỄỆ"
    "íìỉĩịÍÌỈĨỊ"
    "óòỏõọÓÒỎÕỌốồổỗộỐỒỔỖỘớờởỡợỚỜỞỠỢ"
    "úùủũụÚÙỦŨỤứừửữựỨỪỬỮỰ"
    "ýỳỷỹỵÝỲỶỸỴ"
)


_STAGE_DIRECTION_PREFIX_RE = re.compile(
    r"^\*(?P<label>[^\W\d_][\w' -]{1,31})\*[!?.…]*\s+(?P<body>\S.*)$",
    re.UNICODE,
)


_SHORT_DIALOGUE_WORDS = {
    "ah", "aha", "ahh", "ahhh", "ahaha", "ahahaha",
    "oh", "ohh", "ooh", "oohh", "ow", "oww", "ouch", "oaw", "owet", "ous", "pous",
    "uh", "uhh", "um", "umm", "ummh", "mm", "mmm", "ng", "nng", "nngh", "ngh", "nghh",
    "eek", "eeek", "kya", "kkya", "gyah", "haa", "ha", "haha", "hehe", "oish",
    "no", "yes", "yeah", "yep", "ok", "okay", "hey", "wait", "stop", "help", "sorry",
    "wow", "whoa", "huh", "eh", "ehh", "ugh", "ew", "eww", "shh",
}


_COMMON_DIALOGUE_WORDS = {
    "i", "you", "he", "she", "it", "we", "they", "me", "my", "your", "her", "his", "our", "their",
    "a", "an", "the", "this", "that", "these", "those", "is", "are", "am", "was", "were", "be", "been",
    "to", "of", "in", "on", "at", "for", "with", "from", "by", "as", "and", "but", "or", "if", "so",
    "not", "no", "yes", "do", "does", "did", "can", "could", "will", "would", "should", "have", "has", "had",
    "what", "why", "who", "how", "when", "where", "really", "very", "just", "now", "then", "here", "there",
    "like", "want", "need", "feel", "go", "come", "get", "take", "make", "see", "look", "know", "think", "try",
    "good", "bad", "sorry", "please", "thanks", "thank", "well", "oh", "ah", "hey", "wow", "ugh",
    "girl", "man", "boy", "woman", "body", "hand", "face", "breasts", "pussy", "cock", "sex", "cum", "fuck",
    "slut", "bitch", "whore", "fucking", "damn", "damnit", "love", "hate", "fine", "right", "wrong",
    "ok", "okay", "sure", "nice", "play", "baby", "god", "dear", "house", "tips", "clean", "princess",
    "funny", "joke", "golden", "island", "stay", "strong", "probably", "criminals", "hurt", "hurts", "public", "punish", "hii",
}


NANINOVEL_SCRIPT_TOKENS = (
    b"PrintText",
    b"AddChoice",
    b"WaitForInput",
    b"Naninovel.Commands.PrintText",
    b"Naninovel.Commands.AddChoice",
    b"nScripts/",
    b"@choice",
    b"@print",
)


NANINOVEL_SKIP_WORDS = {
    "m_name", "m_script", "script", "printtext", "addchoice", "waitforinput",
    "waitfortext", "commands", "command", "naninovel", "nscript", "nscripts",
    "unityengine", "system.string", "system.boolean", "system.int32",
}


TECH_PATH_PARTS = {
    "monobleedingedge", "managed", "plugins", "backups", "backup", "crashpad",
    "addressableslink", "app.info", "boot.config", "globalgamemanagers",
}


TECH_FILE_NAMES = {
    "config.xml", "link.xml", "boot.config", "app.info", "settings.xml",
    "projectsettings.asset", "globalgamemanagers",
}


GAME_TEXT_HINT_PARTS = {
    "streamingassets", "text", "texts", "script", "scripts", "scenario", "scenarios",
    "naninovel", "localization", "localisation", "language", "languages", "dialogue", "dialogues",
}


BAD_RAW_EDGE_RE = re.compile(r"(^[^A-Za-z0-9'\"(<\[{¿¡…]+|[^A-Za-z0-9.!?…♡>'\")\]}]+$)")


XML_TAG_LINE_RE = re.compile(r"^<[^>]+>$")


XML_CONFIG_RE = re.compile(r"(<configuration|<dllmap|<probing|<assemblyBinding|xmlns=|publicKeyToken=)", re.I)


LANGUAGE_COLUMN_NAMES = {
    "english", "en", "en-us", "en_us", "eng",
    "japanese", "ja", "jp", "chinese", "zh", "cn", "korean", "ko",
    "german", "de", "spanish", "es", "french", "fr", "russian", "ru",
    "italian", "it", "portuguese", "pt", "thai", "th", "vietnamese", "vi",
}


PREFERRED_SOURCE_LANGUAGE_COLUMNS = ["English", "en", "EN", "Eng", "english"]


_NANINOVEL_TEXT_CMD_RE = re.compile(
    r"^@(?P<cmd>choice|print|format|toast|showUI|hideUI|setText|:)\b(?P<rest>.*)$",
    re.I | re.S,
)


_NANINOVEL_NAMED_TEXT_RE = re.compile(
    r'\b(?:text|choice|summary|label|value|name)\s*:\s*"([^"]*)"',
    re.I,
)


_RANDPICK_RE = re.compile(r'RandPick\d*\(\s*"([^"]*)"', re.I)


_ALIGNED_PRINTABLE = re.compile(
    rb"(?:@print|@choice|@:|<[A-Za-z][A-Za-z0-9]{0,16}|[A-Z][A-Za-z']{0,20}[.,!?]{0,3}[ ({\x80-\xff]|[a-z][A-Za-z']{0,24}[.,!?]{0,3}[ ({\x80-\xff]|[A-Z][A-Za-z']{0,12}\.{2,}[A-Z]|[A-Z][\xc2-\xf4]|\*[A-Za-z]|\([A-Za-z.]|\{[A-Za-z]|[\"'][A-Za-z]|[!?][A-Za-z]|[\xc2-\xf4][\x80-\xbf]{1,3}[A-Za-z ])"
)


NANINOVEL_SCRIPT_RAW_HINTS = (
    b"@print",
    b"@choice",
    b"@:",
    b"nScripts/",
    b"PrintText",
    b"AddChoice",
)


MIN_NANINOVEL_SCRIPT_OBJECT_BYTES = 2048


_NANINOVEL_CHOICE_QUOTED_RE = re.compile(
    rb'@choice\s+"((?:\\.|[^"\\]){1,240})"',
    re.IGNORECASE,
)


_NANINOVEL_SCRIPT_TECH_WORDS = (
    "naninovel.", "unityengine", "system.", "mscorlib", "assembly-csharp",
    "serializedfile", "typetree", "mono.behaviour", "managedtextprovider",
)


_NANINOVEL_SCRIPT_TECH_EXACT = frozenset(
    {
        "naninovel",
        "naninovel.commands",
        "opening",
        "labelscriptline",
        "commandscriptline",
        "generictextscriptline",
        "commentscriptline",
        "printtext",
        "addchoice",
    }
)


_NANINOVEL_SCRIPT_TECH_RE = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9]*_+[A-Za-z0-9_]*|[A-Za-z][A-Za-z0-9]*\.[A-Za-z0-9_.]+)$"
)


_NANINOVEL_STAGE_ONLY_RE = re.compile(r"^\*[^*\r\n]{1,80}\*$")


UI_MONO_CLASSES = {
    "Text",
    "TextMeshPro",
    "TextMeshProUGUI",
    "TMP_Text",
}


RAW_LOWER_DIALOGUE_WORDS = {
    "ah", "aha", "ahaha", "eh", "heh", "hehe", "ha", "haha", "huh",
    "hm", "hmm", "hmmm", "mm", "mmm", "mmmm", "mn", "umm", "um",
    "ugh", "ughh", "oof", "ooh", "oooh", "oh", "ouch", "ow", "oww",
    "eek", "eeek", "kya", "kkya", "okay", "ok", "yes", "yeah", "yep",
    "no", "nope", "sorry", "thanks", "thank", "help", "wait", "stop",
}


DEFAULT_FILE_EXTRACT_TIMEOUT = float(os.environ.get("VNTEXT_FILE_EXTRACT_TIMEOUT", "900"))
DEFAULT_EXTRACT_STEP_TIMEOUT = float(os.environ.get("VNTEXT_EXTRACT_STEP_TIMEOUT", "600"))


_UNITY_OBJ_PROGRESS_RX = re.compile(r"Unity object (\d+)/(\d+)")
