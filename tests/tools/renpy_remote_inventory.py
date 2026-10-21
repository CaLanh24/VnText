"""Bounded public ZIP metadata survey; no payload extraction or execution."""
import io
import json
from pathlib import Path
import urllib.request
import urllib.error
import zipfile


class PublicRangeReader(io.RawIOBase):
    def __init__(self,url):
        self.url=url
        try:
            with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as r:
                self.size=int(r.headers['Content-Length'])
        except urllib.error.HTTPError as error:
            if error.code not in (403,405):raise
            # Some public download CDNs support GET but reject HEAD.
            with urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=0-0'}),timeout=30) as r:
                if r.status!=206:raise ValueError('HEAD unsupported and bounded GET metadata unavailable')
                self.size=int(r.headers['Content-Range'].split('/')[-1])
                if len(r.read(2))!=1:raise ValueError('invalid GET metadata range')
        self.position=0
        self.bytes_read=0

    def seek(self,offset,whence=0):
        self.position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset
        return self.position

    def tell(self):return self.position

    def read(self,size=-1):
        size=self.size-self.position if size<0 else min(size,self.size-self.position)
        if size<=0:return b''
        if size>512*1024 or self.bytes_read+size>2*1024*1024:raise ValueError('remote metadata read budget exceeded')
        request=urllib.request.Request(self.url,headers={'Range':f'bytes={self.position}-{self.position+size-1}'})
        with urllib.request.urlopen(request,timeout=30) as r:
            if r.status!=206:raise ValueError('server did not honor bounded metadata Range; no full download')
            data=r.read(size+1)
        if len(data)!=size:raise ValueError('remote metadata range size mismatch')
        self.position+=len(data);self.bytes_read+=len(data)
        return data


def survey(url):
    reader=PublicRangeReader(url)
    with zipfile.ZipFile(reader) as archive:
        records=[{'path':i.filename,'bytes':i.file_size,'compressed_bytes':i.compress_size,'crc32':f'{i.CRC:08x}'} for i in archive.infolist()]
        versions={}
        for info in archive.infolist():
            if info.filename.endswith(('renpy/__init__.py','renpy/vc_version.py','renpy/vc_version.pyc')) and info.file_size<=65536:
                raw=archive.read(info)
                versions[info.filename]=raw.decode('utf-8',errors='replace') if info.filename.endswith('.py') else 'compiled metadata only'
    return {'archive_bytes':reader.size,'remote_read_bytes':reader.bytes_read,'inventory':records,'version_sources':versions,
            'qualification':'Remote central-directory inventory/CRC only; archive SHA256 requires bounded acquisition, no runtime proof'}


if __name__=='__main__':
    root=Path('C:/Users/VNTextDev/Downloads/VM-Acceptance')
    for candidate,url in [('psych','https://github.com/remarkablegames/psych-101/releases/download/v1.1.0/pc.zip'),
                          ('namhur',json.loads((root/'renpy-namhur-download-private.json').read_text(encoding='utf-8-sig'))['url'])]:
        try:result=survey(url)
        except Exception as error:result={'error':str(error),'outcome':'SURVEY_BLOCKED_NO_PAYLOAD_DOWNLOADED'}
        (root/f'renpy-{candidate}-remote-inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        game=[r for r in result.get('inventory',[]) if '/game/' in r['path']]
        print(candidate,json.dumps({'archive_bytes':result.get('archive_bytes'),'error':result.get('error'),
              'game_surface':{s:sum(r['path'].endswith(s)for r in game)for s in ('.rpy','.rpyc','.rpa')},
              'game_bytes':sum(r['bytes']for r in game)}))
