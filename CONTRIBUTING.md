# Contributing

Maintainer: **Marcin Kowalik <mkowalik@agh.edu.pl>**

Contributions are welcome. Please keep changes compatible with GPL-3.0-or-later and preserve the attribution to the original wFrog authors.

For chart changes, document whether the behavior is:

1. source-faithful to classic wFrog,
2. a WeeWX adaptation, or
3. a deliberate ENVMON enhancement.

Before submitting changes, run:

```bash
python3 -m py_compile bin/*.py extras/envmon/*.py
bash -n install.sh uninstall.sh
```
