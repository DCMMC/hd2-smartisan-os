#!/usr/bin/env python3
"""Reduce the CM boot animation decode rate to something the HD2 can sustain."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def optimize(source, destination):
    source, destination = Path(source), Path(destination)
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        parts = sorted({
            name.split('/', 1)[0]
            for name in names
            if '/' in name and name.split('/', 1)[0]
        })
        selected = {}
        for part in parts:
            frames = sorted(
                name for name in names
                if name.startswith(part + '/') and not name.endswith('/')
            )
            selected[part] = frames[::3]
        with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_STORED) as output:
            output.writestr('desc.txt', '480 480 16\np 1 0 part0\np 0 0 part1\n')
            for part in parts:
                output.writestr(part + '/', b'')
                for index, name in enumerate(selected[part], 1):
                    output.writestr(
                        f'{part}/{index:05d}{Path(name).suffix}',
                        archive.read(name),
                    )
    return {part: len(frames) for part, frames in selected.items()}


def main():
    source = ROOT/'work/hd2-base/system/media/bootanimation.zip'
    destination = ROOT/'work/smartisan-stage/system/media/bootanimation.zip'
    counts = optimize(source, destination)
    print(destination, destination.stat().st_size, counts)


if __name__ == '__main__':
    main()
