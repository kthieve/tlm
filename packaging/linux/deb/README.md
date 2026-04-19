# Debian package (optional)

Build with `stdeb` or `dh_virtualenv` from a tagged release. Example (local):

```bash
pip install stdeb
python3 setup.py --command-packages=stdeb.command bdist_deb
```

Wire into CI when release artifacts need `.deb`.
