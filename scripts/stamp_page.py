#!/usr/bin/env python3
"""Write the version of each script and style file of the page into index.html.

A browser keeps a file of the page for a while: GitHub Pages lets it keep the file for 10 minutes,
and a normal reload gets only the HTML again. A version in the address of a file, such as
app.js?v=1a2b3c4d, changes when the file changes, so the browser gets the new file with the new HTML.
The version is the start of the SHA-256 hash of the file.

Run from the project directory after a change of a page file:
    python3 scripts/stamp_page.py

The test scripts/test_page_files.py gives an error when index.html is not current.
"""
import hashlib
import os
import re

PAGE_FILES = ['styles.css', 'ui.js', 'app.js', 'us.js']
VERSION_LENGTH = 8


def version(content):
    """The version of a file: the first characters of its SHA-256 hash."""
    return hashlib.sha256(content).hexdigest()[:VERSION_LENGTH]


def versions(root):
    """{file name: version} for each page file in `root`."""
    found = {}
    for name in PAGE_FILES:
        with open(os.path.join(root, name), 'rb') as f:
            found[name] = version(f.read())
    return found


def stamp(html, found):
    """index.html with the version of each file in `found` in its src or href."""
    for name, value in found.items():
        pattern = re.compile(r'((?:src|href)=")' + re.escape(name) + r'(?:\?v=[0-9a-f]+)?(")')
        html = pattern.sub(lambda m: f'{m.group(1)}{name}?v={value}{m.group(2)}', html)
    return html


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, 'index.html')
    with open(path, encoding='utf-8') as f:
        html = f.read()
    stamped = stamp(html, versions(root))
    if stamped == html:
        print('index.html is current')
        return
    with open(path, 'w', encoding='utf-8') as f:
        f.write(stamped)
    print('wrote the versions into index.html')


if __name__ == '__main__':
    main()
