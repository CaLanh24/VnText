"""Default-off disposable-VM Vietnamese font trial, never product integration."""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
FONT=ROOT/'.dev-env/tools/renpy-8.5.3/renpy/common/DejaVuSans.ttf'
NOTICE=FONT.with_suffix('.txt')
FONT_SHA='3fdf69cabf06049ea70a00b5919340e2ce1e6d02b0cc3c4b44fb6801bd1e0d22'
NOTICE_SHA='d75938dec098f06f0ac3c00853065d94f020be1c3c62ef1dc2975ba15b4d9b0e'
FONT_PATH='tl/vietnamese/_vntext_font/DejaVuSans.ttf'
PROFILE_PATH='game/tl/vietnamese/zzz_vntext_font_profile.rpy'
PROFILE=('''# Disposable VM trial only; production integration is not authorized.
translate vietnamese python:
    gui.text_font = "'''+FONT_PATH+'''"
    gui.name_text_font = "'''+FONT_PATH+'''"
    gui.interface_text_font = "'''+FONT_PATH+'''"
    gui.button_text_font = "'''+FONT_PATH+'''"
    gui.choice_button_text_font = "'''+FONT_PATH+'''"

translate vietnamese style default:
    font "'''+FONT_PATH+'''"
''').encode('utf-8')


def digest(raw):return hashlib.sha256(raw).hexdigest()


def checked_root(game):
    game=Path(game).absolute()
    for path in (game,*game.parents):
        if path.exists()and(path.is_symlink()or getattr(path.lstat(),'st_file_attributes',0)&0x400):raise ValueError('trial root passes a reparse/link')
    game=game.resolve()
    if not game.is_relative_to((ROOT/'TEST_RUN').resolve())or not(game/'game').is_dir():raise ValueError('trial only permits registered TEST_RUN game copy')
    return game


def install_trial(game,*,enabled=False,font=FONT,notice=NOTICE):
    if not enabled:return {'scope':'DISABLED','owned_files':{}}
    game=checked_root(game);font_bytes=Path(font).read_bytes();notice_bytes=Path(notice).read_bytes()
    if digest(font_bytes)!=FONT_SHA or digest(notice_bytes)!=NOTICE_SHA:raise ValueError('font/notice pinned identity mismatch')
    artifacts={PROFILE_PATH:PROFILE,'game/'+FONT_PATH:font_bytes,'game/tl/vietnamese/_vntext_font/DejaVuSans.txt':notice_bytes}
    for name in (*artifacts,PROFILE_PATH+'c'):
        target=game/name
        for parent in (target,*target.parents):
            if parent.exists()and(parent.is_symlink()or getattr(parent.lstat(),'st_file_attributes',0)&0x400):raise ValueError('trial output reparse/link')
        if target.exists():raise ValueError('trial output already exists; no overwrite')
    written={}
    try:
        for name,raw in artifacts.items():
            path=game/name;path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb')as stream:stream.write(raw)
            written[name]=digest(raw)
    except Exception:
        for name,expected in written.items():
            if digest((game/name).read_bytes())==expected:(game/name).unlink()
        raise
    return {'scope':'DISPOSABLE_VM_TRIAL_ONLY','language':'vietnamese','root':str(game),'owned_files':written,
            'bytes':sum(len(raw)for raw in artifacts.values()),'profile_utf8':PROFILE.decode(),'font_sha256':FONT_SHA,'notice_sha256':NOTICE_SHA}


def own_generated_bytecode(receipt):
    game=checked_root(receipt['root']);name=PROFILE_PATH+'c';path=game/name
    if path.is_file()and not path.is_symlink():receipt['owned_files'][name]=digest(path.read_bytes())


def rollback_trial(receipt):
    game=checked_root(receipt['root'])
    names=receipt['owned_files']
    for name,expected in names.items():
        path=game/name
        if not path.resolve().is_relative_to(game)or path.is_symlink()or not path.is_file()or digest(path.read_bytes())!=expected:raise ValueError('foreign trial bytes; refusing rollback')
    if (game/(PROFILE_PATH+'c')).exists()and PROFILE_PATH+'c'not in names:raise ValueError('unowned compiled profile; refusing rollback')
    for name in names:(game/name).unlink()
    return {'status':'PASS_EXACT_OWNED_FILES_REMOVED','files':list(names)}
