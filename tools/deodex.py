#!/usr/bin/env python3
"""Deodex a donor in place using its own framework, not the HD2 framework."""
import argparse
import concurrent.futures
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('system', type=Path)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    system = args.system.resolve()
    # Keep original framework odexes for resolving all later app dependencies.
    framework = ROOT / 'work/donor-framework-original'
    if not framework.exists():
        shutil.copytree(system / 'framework', framework)
    odexes = sorted(system.rglob('*.odex'))
    logs = ROOT / 'logs/deodex'
    logs.mkdir(parents=True, exist_ok=True)
    java = ['java','-Xmx1024m','-cp',str(ROOT / 'sources/smali-jars/*')]

    def process(odex):
        package = odex.with_suffix('.jar' if odex.parent.name == 'framework' else '.apk')
        if not package.exists():
            raise ValueError('Missing APK/JAR for ' + str(odex))
        label = str(odex.relative_to(system)).replace('/','_')
        # This Smartisan full OTA includes the original dex as well as odex.
        # Keep the original bytecode and let the target regenerate its cache.
        with zipfile.ZipFile(package) as z:
            if 'classes.dex' in z.namelist():
                if not z.read('classes.dex').startswith(b'dex\n035\0'):
                    raise ValueError('Unexpected original dex: ' + label)
                odex.unlink()
                return label + ' (original classes.dex preserved)'
        temp = ROOT / 'work/deodex' / label
        temp.mkdir(parents=True, exist_ok=True)
        with (logs / (label + '.log')).open('w') as log:
            subprocess.run(java + ['org.jf.baksmali.Main','deodex','-a','19','-j','2',
                                  '-d',str(framework),'-o',str(temp/'smali'),str(odex)],
                           stdout=log,stderr=log,check=True)
            subprocess.run(java + ['org.jf.smali.Main','assemble','-a','19','-j','2',
                                  '-o',str(temp/'classes.dex'),str(temp/'smali')],
                           stdout=log,stderr=log,check=True)
        dex = (temp / 'classes.dex').read_bytes()
        if not dex.startswith(b'dex\n035\0'):
            raise ValueError('Invalid assembled dex: ' + label)
        with zipfile.ZipFile(package) as z:
            if 'classes.dex' in z.namelist():
                raise ValueError('Already contains classes.dex: ' + str(package))
        with zipfile.ZipFile(package, 'a', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('classes.dex', dex)
        odex.unlink()
        shutil.rmtree(temp)
        return label

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, label in enumerate(pool.map(process,odexes),1):
            print(f'{index}/{len(odexes)} {label}',flush=True)

if __name__ == '__main__':
    main()
