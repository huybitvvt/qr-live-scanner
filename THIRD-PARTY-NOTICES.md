# Third-party components

This application's MIT license does not replace the licenses of its dependencies.
The Windows distribution includes notices in `_internal/assets/licenses` and
the WeChat model license in `_internal/assets/models/LICENSE`.

| Component | Source | License |
| --- | --- | --- |
| ZXing-C++ | https://github.com/zxing-cpp/zxing-cpp | Apache-2.0 |
| OpenCV / WeChatQRCode | https://github.com/opencv/opencv_contrib/tree/4.x/modules/wechat_qrcode | Apache-2.0 and bundled third-party notices |
| WeChat models | https://huggingface.co/opencv/qrcode_wechatqrcode | Apache-2.0; revision and SHA-256 in assets/models/manifest.json |
| NumPy | https://numpy.org | BSD and bundled third-party notices |
| Pillow | https://python-pillow.org | HPND and bundled third-party notices |
| psutil | https://github.com/giampaolo/psutil | BSD-3-Clause |
| Python | https://python.org | PSF and bundled notices |
| Tcl/Tk | https://www.tcl-lang.org | Tcl/Tk license |
| PyInstaller bootloader | https://pyinstaller.org | GPL with bootloader distribution exception |

`qrcode` and `pytest` are development/test dependencies, not runtime engines.
No source, database, configuration, camera image, or credential from the weighing
application is included in this standalone application.
