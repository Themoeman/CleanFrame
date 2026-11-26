"""Build and sign on Windows through an existing official Tizen SDK profile.

Same flow as package.py, without the POSIX terminal handling. The profile must
already hold its certificate passwords (Certificate Manager saves them); any
password prompt fails immediately because stdin is closed. SDK output is never
printed, since it can include profile credentials.
"""
from pathlib import Path
import subprocess
import tempfile
import zipfile

from font_assets import write_widget_archive
from local_config import ROOT, load_settings
from private_files import check_signed_widget


def main(root=ROOT):
    settings = load_settings(root)
    if settings['password_file']:
        raise ValueError('password_file is not supported on Windows; let the SDK profile hold the passwords.')
    cli = settings['sdk_path'] / 'tools/ide/bin/tizen.bat'
    if not cli.is_file():
        raise ValueError('Tizen CLI missing. Set sdk_path in .local/signing.json; see docs/development.md.')
    dist = root / 'dist'
    dist.mkdir(exist_ok=True)
    unsigned = dist / 'CleanFrame-unsigned.wgt'
    write_widget_archive(unsigned, root=root, identity=settings['identity'])
    # A fresh folder prevents a previous signed widget masking a failed build.
    signed_dir = Path(tempfile.mkdtemp(prefix='signed-', dir=dist))
    command = [str(cli), 'package', '-t', 'wgt', '-s', settings['profile'], '-o', str(signed_dir), '--', str(unsigned)]
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise ValueError('SDK signing timed out.') from None
    output = (result.stdout + result.stderr).lower()
    if b'password' in output and b'package file location' not in output:
        raise ValueError('SDK requested a password. Re-save the passwords in Certificate Manager.')
    signed = signed_dir / unsigned.name
    if result.returncode or not signed.is_file():
        raise ValueError('SDK signing failed. Check the selected profile in Certificate Manager.')
    check_signed_widget(signed, settings['identity'])
    target = dist / 'CleanFrame.wgt'
    ready = signed_dir / 'validated.wgt'
    ready.write_bytes(signed.read_bytes())
    ready.replace(target)
    print('Signed widget created: ' + str(target))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        message = str(error) if isinstance(error, ValueError) else 'Cannot complete packaging. Check SDK/profile setup and local file permissions.'
        raise SystemExit(message) from None
