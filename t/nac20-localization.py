"""Check Vietnamese catalog coverage and interpolation safety using Python stdlib."""
import collections
import gettext
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = re.compile(
    r'\$?\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|'
    r'%\d*\$?[-+0 #]*\d*(?:\.\d+)?[sdfixXouegc]|'
    r'</?[A-Za-z][^>]*>|\[[^\]]*\]'
)


def catalog(path):
    entries = []
    entry, field = {}, None
    for line in (ROOT / path).read_text(encoding='utf-8').splitlines() + ['']:
        if not line.strip():
            if entry.get('msgid'):
                entries.append(entry)
            entry, field = {}, None
        elif line.startswith(('msgid ', 'msgstr ', 'msgid_plural ', 'msgstr[0] ')):
            field, value = line.split(' ', 1)
            entry[field] = unquote(value)
        elif line.startswith('"') and field:
            entry[field] += unquote(line)
    return entries


def unquote(value):
    # Gettext only interprets these C escapes; literal \u in identifiers is valid.
    escapes = {'n': '\n', 'r': '\r', 't': '\t', '"': '"', '\\': '\\'}
    return re.sub(r'\\([nrt"\\])', lambda match: escapes[match[1]], value[1:-1])


total = 0
for source, target in [
    ('conf/I18N/api/en.po', 'conf/I18N/api/vi.po'),
    ('html/pfappserver/lib/pfappserver/I18N/en.po', 'html/pfappserver/lib/pfappserver/I18N/vi.po'),
    ('conf/locale/en/LC_MESSAGES/packetfence.po', 'conf/locale/vi/LC_MESSAGES/packetfence.po'),
]:
    original, vietnamese = catalog(source), catalog(target)
    assert len(original) == len(vietnamese), target
    for before, after in zip(original, vietnamese):
        assert before['msgid'] == after['msgid'], target
        translated = after.get('msgstr') or after.get('msgstr[0]')
        assert translated, before['msgid']
        assert '▁' not in translated, before['msgid']
        assert collections.Counter(TOKENS.findall(before['msgid'])) == collections.Counter(TOKENS.findall(translated)), before['msgid']
    total += len(vietnamese)

binary = ROOT / 'conf/locale/vi/LC_MESSAGES/packetfence.mo'
if binary.exists():
    with binary.open('rb') as file:
        translations = gettext.GNUTranslations(file)
    assert translations.gettext('Username') == 'Tên đăng nhập'
    assert translations.gettext('PacketFence Registration system') == 'Hệ thống đăng ký truy cập NAC20'
print(f'PASS: {total} Vietnamese messages; interpolation and HTML tokens preserved.')
