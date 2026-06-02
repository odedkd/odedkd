#!/usr/bin/env python3
"""
Reads a markdown file, detects reversed Hebrew lines from PDF extraction,
reverses them back to correct logical reading order, and saves the result.

Usage:
    python3 fix_rtl.py input.md [output.md]
    If output.md is omitted, overwrites the input file.
"""

import sys
import re


HEBREW_RANGE = ('֐', '׿')


def hebrew_char_count(text):
    return sum(1 for c in text if HEBREW_RANGE[0] <= c <= HEBREW_RANGE[1])


def is_hebrew_dominant(line):
    """Return True if the line has enough Hebrew to be treated as RTL."""
    stripped = line.strip()
    if not stripped:
        return False
    heb = hebrew_char_count(stripped)
    if heb == 0:
        return False
    alpha = sum(1 for c in stripped if c.isalpha())
    return alpha > 0 and (heb / alpha) >= 0.3


def is_markdown_structure(line):
    """Lines that must never be reversed: headings, horizontal rules."""
    stripped = line.strip()
    return stripped.startswith('#') or stripped == '---'


def reverse_rtl_line(line):
    """
    Reverse a visually-reversed RTL line back to logical order.

    PDF extraction stores RTL text in visual order (right-to-left characters
    written left-to-right). A full string reversal restores logical order for
    Hebrew-dominant lines. Leading/trailing whitespace is preserved.
    """
    leading  = len(line) - len(line.lstrip())
    trailing = len(line) - len(line.rstrip())

    content = line[leading: len(line) - trailing if trailing else None]
    reversed_content = content[::-1]

    return line[:leading] + reversed_content + line[len(line) - trailing:]


def fix_rtl(text):
    result = []
    for line in text.splitlines(keepends=True):
        if is_markdown_structure(line) or not is_hebrew_dominant(line):
            result.append(line)
        else:
            result.append(reverse_rtl_line(line))
    return ''.join(result)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.md [output.md]", file=sys.stderr)
        sys.exit(1)

    input_path  = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path

    with open(input_path, 'r', encoding='utf-8') as f:
        original = f.read()

    fixed = fix_rtl(original)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(fixed)

    changed = sum(1 for a, b in zip(original.splitlines(), fixed.splitlines()) if a != b)
    print(f"Fixed {changed} line(s). Saved to: {output_path}")


if __name__ == '__main__':
    main()
