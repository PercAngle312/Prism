"""Publish pinned, tested PRISM binaries; never rebuild or replace release assets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = 'PercAngle312/Swiss-CA'
API = 'https://api.github.com/repos/' + REPO


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def api(path, data=None, method=None):
    headers = {'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
               'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    body = None if data is None else json.dumps(data).encode()
    if body is not None:
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(API + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download_artifact(run, name, expected_commit, cache):
    evidence = api('/actions/runs/' + str(run))
    if evidence['head_sha'] != expected_commit or evidence['conclusion'] != 'success':
        raise ValueError('Pinned workflow is not successful at the expected commit')
    artifacts = api(f'/actions/runs/{run}/artifacts?per_page=100')['artifacts']
    matches = [a for a in artifacts if a['name'] == name and not a['expired']]
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous pinned artifact: ' + name)
    artifact = matches[0]
    path = cache / (str(artifact['id']) + '.zip')
    for attempt in range(3):
        request = urllib.request.Request(API + f"/actions/artifacts/{artifact['id']}/zip",
            headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN']})
        try:
            urllib.request.build_opener(NoRedirect).open(request, timeout=120)
            raise ValueError('Expected GitHub artifact redirect')
        except urllib.error.HTTPError as error:
            if error.code not in (301, 302, 303, 307, 308):
                raise
            location = error.headers['Location']
        if urllib.parse.urlparse(location).scheme != 'https':
            raise ValueError('Artifact redirect must be HTTPS')
        # Signed bytes are fetched without forwarding the GitHub credential.
        with urllib.request.urlopen(location, timeout=240) as source, path.open('wb') as target:
            shutil.copyfileobj(source, target)
        good = path.stat().st_size == artifact['size_in_bytes']
        expected = artifact.get('digest')
        if expected:
            good = good and expected == 'sha256:' + digest(path)
        if good:
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is None:
                    return path
        path.unlink(missing_ok=True)
        time.sleep(2)
    raise ValueError('Artifact size, checksum or ZIP validation failed: ' + name)


def validate_dol(raw, expected):
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Executable differs from the hardware-test build')
    if len(raw) < 256:
        raise ValueError('Truncated DOL')
    offsets, sizes = struct.unpack_from('>18I', raw, 0), struct.unpack_from('>18I', raw, 0x90)
    if not any(sizes):
        raise ValueError('Empty DOL')
    for offset, size in zip(offsets, sizes):
        if size and (offset < 256 or offset + size > len(raw)):
            raise ValueError('DOL section out of bounds')


def write_zip(path, files, directories=()):
    with zipfile.ZipFile(path, 'w') as archive:
        for name in sorted(directories):
            info = zipfile.ZipInfo(name)
            info.external_attr = 0o40755 << 16 | 0x10
            archive.writestr(info, b'')
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('Release ZIP CRC validation failed')


def core_assets(output, config, ui, native, source_files):
    validate_dol(ui, config['ui_sha256'])
    files = {'ipl.dol': ui, 'PRISM.dol': ui,
             'README-FIRST.md': (ROOT / 'docs/releases/prism-v1.0.md').read_bytes()}
    sources = dict(source_files)
    for system, (raw, code, record, extra) in native.items():
        validate_dol(raw, config['emulators'][system])
        if hashlib.sha256(raw).hexdigest() != record['sha256'] or hashlib.sha256(code).hexdigest() != record['source_sha256']:
            raise ValueError('Emulator source/executable provenance mismatch')
        files[f'swiss/prism/emulators/{system}.dol'] = raw
        sources[system + '-source.zip'] = code
        sources[system + '-provenance.json'] = (json.dumps(record, indent=2) + '\n').encode()
        for name, content in extra.items():
            if name in sources and sources[name] != content:
                raise ValueError('Supporting source mismatch')
            sources[name] = content
    if set(native) != set(config['emulators']):
        raise ValueError('All seven tested native emulators are required')
    files.update({'SOURCE-AND-LICENSES/' + name: content for name, content in sources.items()})
    directories = ['roms/', 'saves/', 'swiss/prism/settings/']
    for system in native:
        directories.extend([f'roms/{system}/', f'saves/{system}/', f'swiss/prism/settings/{system}/'])
    write_zip(output / 'PRISM-v1.0-SD-Update.zip', files, directories)
    write_zip(output / 'PRISM-v1.0-Source.zip', sources)
    (output / 'ipl.dol').write_bytes(ui)
    shutil.copyfile(ROOT / 'docs/releases/prism-v1.0.md', output / 'PRISM-v1.0-Release-Notes.md')
    shutil.copyfile(ROOT / 'assets/prism/release-v1.0.json', output / 'RELEASE-MANIFEST.json')


def assemble(args, config):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    native = {}
    if args.from_tested_update:
        with zipfile.ZipFile(args.from_tested_update) as archive:
            if archive.testzip() is not None:
                raise ValueError('Invalid tested ZIP')
            ui = archive.read('ipl.dol')
            sources = {Path(n).name: archive.read(n) for n in archive.namelist()
                if n.startswith('SOURCE-AND-LICENSES/') and not any(Path(n).name.startswith(s + '-') for s in config['emulators'])}
            for system in config['emulators']:
                native[system] = (archive.read(f'swiss/prism/emulators/{system}.dol'),
                    archive.read(f'SOURCE-AND-LICENSES/{system}-source.zip'),
                    json.loads(archive.read(f'SOURCE-AND-LICENSES/{system}-provenance.json')), {})
    else:
        cache = output.parent / 'release-cache'
        cache.mkdir(exist_ok=True)
        sha = config['tested_commit']
        ui_artifact = download_artifact(config['ui_run'], config['ui_artifact'], sha, cache)
        with zipfile.ZipFile(ui_artifact) as archive:
            ui = archive.read('PRISM-UI-' + sha[:12] + '.dol')
        for system in config['emulators']:
            artifact = download_artifact(config['native_run'], 'PRISM-Native-Emulator-' + system, sha, cache)
            with zipfile.ZipFile(artifact) as archive:
                extra = {n: archive.read(n) for n in archive.namelist() if n == 'libsmb2-source.zip'}
                native[system] = (archive.read(system + '.dol'), archive.read(system + '-source.zip'),
                    json.loads(archive.read(system + '-provenance.json')), extra)
        tested = args.tested_source.resolve()
        if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=tested, text=True).strip() != sha:
            raise ValueError('Wrong corresponding PRISM source')
        littlefs = tested / 'cube/swiss/source/littlefs'
        if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=littlefs, text=True).strip() != config['littlefs_commit']:
            raise ValueError('Wrong littlefs source')
        sources = {'PRISM-bd2d2aad-source.zip': subprocess.check_output(['git', 'archive', '--format=zip', 'HEAD'], cwd=tested),
            'littlefs-6cb4e86540ec-source.zip': subprocess.check_output(['git', 'archive', '--format=zip', 'HEAD'], cwd=littlefs),
            'GNU-GPL-v2.txt': (tested / 'LICENSE').read_bytes()}
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-o', str(cache / 'catalog-reader'),
            str(tested / 'tests/prism_catalog_verify.c'), str(tested / 'cube/swiss/source/gui/prism_pack.c')], check=True)
        for system, run in config['catalog_runs'].items():
            artifact = download_artifact(run, 'PRISM-' + system + '-Catalog', config['catalog_commits'][str(run)], cache)
            name = 'PRISM-' + system.upper() + '-Catalog.zip'
            with zipfile.ZipFile(artifact) as archive, archive.open(name) as stream, (output / name).open('wb') as target:
                shutil.copyfileobj(stream, target)
            pack_path = cache / (system + '.prism')
            with zipfile.ZipFile(output / name) as archive:
                if archive.testzip() is not None:
                    raise ValueError('Catalog ZIP CRC failure')
                with archive.open('swiss/prism/emulators/' + system + '.prism') as stream, pack_path.open('wb') as target:
                    shutil.copyfileobj(stream, target)
            subprocess.run([str(cache / 'catalog-reader'), str(pack_path)], check=True)
            pack_path.unlink()
    core_assets(output, config, ui, native, sources)
    assets = sorted(p for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS.txt')
    (output / 'SHA256SUMS.txt').write_text(''.join(digest(p) + '  ' + p.name + '\n' for p in assets))
    return output


def publish(output, config):
    tag = urllib.parse.quote(config['tag'], safe='')
    try:
        reference = api('/git/ref/tags/' + tag)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    else:
        if reference['object']['sha'] != config['tested_commit']:
            raise ValueError('Existing release tag points to a different commit')
    body = (ROOT / 'docs/releases/prism-v1.0.md').read_text()
    try:
        release = api('/releases/tags/' + tag)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        drafts = [r for r in api('/releases?per_page=100') if r['tag_name'] == config['tag']]
        if len(drafts) > 1:
            raise ValueError('Multiple releases use the requested tag')
        release = drafts[0] if drafts else api('/releases', {'tag_name': config['tag'],
            'target_commitish': config['tested_commit'], 'name': config['name'], 'body': body,
            'draft': True, 'prerelease': False})
    if release['target_commitish'] != config['tested_commit'] or release['body'] != body:
        raise ValueError('Existing release metadata differs; refusing to overwrite it')
    assets = {a['name']: a for a in api(f"/releases/{release['id']}/assets?per_page=100")}
    for path in sorted(output.iterdir()):
        if not path.is_file():
            continue
        expected = 'sha256:' + digest(path)
        if path.name in assets:
            if assets[path.name].get('digest') != expected:
                raise ValueError('Existing release asset differs: ' + path.name)
            continue
        if not release['draft']:
            raise ValueError('Published release is missing assets; refusing to mutate it')
        url = f"https://uploads.github.com/repos/{REPO}/releases/{release['id']}/assets?" + urllib.parse.urlencode({'name': path.name})
        with path.open('rb') as stream:
            request = urllib.request.Request(url, data=stream, method='POST', headers={
                'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Content-Type': 'application/octet-stream',
                'Content-Length': str(path.stat().st_size)})
            with urllib.request.urlopen(request, timeout=300) as response:
                asset = json.load(response)
        if asset.get('digest') != expected or asset['size'] != path.stat().st_size or asset['state'] != 'uploaded':
            raise ValueError('Uploaded release asset failed verification')
    if release['draft']:
        release = api(f"/releases/{release['id']}", {'draft': False, 'prerelease': False, 'make_latest': 'true'}, method='PATCH')
    reference = api('/git/ref/tags/' + tag)
    if release['draft'] or reference['object']['sha'] != config['tested_commit']:
        raise ValueError('Published release/tag verification failed')
    print('Published ' + release['html_url'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tested-source', type=Path, default=Path('tested-source'))
    parser.add_argument('--output', type=Path, default=Path('release-output'))
    parser.add_argument('--from-tested-update', type=Path)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    if args.publish and args.from_tested_update:
        parser.error('Published builds must verify pinned successful CI evidence and all catalog assets')
    config = json.loads((ROOT / 'assets/prism/release-v1.0.json').read_text())
    output = assemble(args, config)
    if args.publish:
        publish(output, config)
