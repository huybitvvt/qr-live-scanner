import importlib.metadata as metadata
from pathlib import Path
import shutil
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def main():
    assets = ROOT / 'assets'
    licenses = assets / 'licenses'
    licenses.mkdir(parents=True, exist_ok=True)
    for name in ('opencv-contrib-python-headless', 'zxing-cpp', 'numpy', 'pillow', 'psutil', 'pyinstaller'):
        dist = metadata.distribution(name)
        target = licenses / name
        target.mkdir(exist_ok=True)
        for file in dist.files or []:
            if any(word in file.name.lower() for word in ('license', 'copyright', 'notice')):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    relative = str(file).replace('..', '_').replace('/', '__').replace('\\', '__')
                    shutil.copyfile(source, target / relative)
    for source in [Path(sys.base_prefix) / 'LICENSE.txt', *Path(sys.base_prefix).glob('tcl/*/license.terms')]:
        if source.is_file():
            shutil.copyfile(source, licenses / f'{source.parent.name}-{source.name}')
    # Code-drawn geometric application mark; no third-party artwork.
    icon = Image.new('RGB', (256, 256), '#155DE9')
    draw = ImageDraw.Draw(icon)
    for x, y in ((40, 40), (144, 40), (40, 144)):
        draw.rectangle((x, y, x+72, y+72), fill='white')
        draw.rectangle((x+14, y+14, x+58, y+58), fill='#155DE9')
        draw.rectangle((x+27, y+27, x+45, y+45), fill='white')
    for x, y in ((144, 144), (188, 144), (144, 188), (188, 188)):
        draw.rectangle((x, y, x+26, y+26), fill='white')
    icon.save(assets / 'app.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print('Prepared application icon and third-party notices')


if __name__ == '__main__':
    main()
