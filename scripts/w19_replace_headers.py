#!/usr/bin/env python3
"""
W19-2: Replace the inline `<header class="app-header app-container">...</header>`
blocks across all view files with `<AppHeader scope="X" />`, and add the
import. Also clean up the now-dead `.app-header__brand` / `.app-header__right`
scoped CSS rules that lived inside the views (they live in AppHeader.vue now).
"""
import re
import sys
from pathlib import Path

VIEW_DIR = Path('frontend/web/src/views')

# Files to process. scope name follows the file's role, used for e2e testids.
FILES = {
    'Home.vue':            'home',
    'Profile.vue':         'profile',
    'Orders.vue':          'orders',
    'Destinations.vue':    'destinations',
    'Materials.vue':       'materials',
    'MaterialsValidate.vue': 'materials-validate',
    'MaterialsDiagnose.vue': 'materials-diagnose',
    'OrderNew.vue':        'order-new',
    'OrderDetail.vue':     'order-detail',
    'PaymentResult.vue':   'payment-result',
    'RpaStatus.vue':       'rpa-status',
    'RpaSubmit.vue':       'rpa-submit',
    'Agreement.vue':       'agreement',
    'Login.vue':           'login',
    'Register.vue':        'register',
    'ForgotPassword.vue':  'forgot-password',
}

# Match the old header block (greedy on inner newlines).
HEADER_RE = re.compile(
    r'[ \t]*<header class="app-header app-container">.*?</header>\s*\n',
    re.DOTALL,
)

# Match the dead scoped-style blocks we want to remove
DEAD_STYLE_RE = re.compile(
    r'\s*\.app-header__brand \{ display: flex; align-items: center; gap: 8px; text-decoration: none; color: var\(--ink, #1A1D29\); font-weight: 600; \}\n'
    r'\s*\.app-header__right \{ display: flex; align-items: center; gap: 12px; \}\n',
)


def add_import(content: str) -> str:
    """Insert `import AppHeader from '@/components/AppHeader.vue'` after the
    last `import` line in the <script setup> block. Idempotent: skip if already
    imported."""
    if "from '@/components/AppHeader.vue'" in content:
        return content
    # Find the script setup block
    m = re.search(r'(<script setup>)(.*?)(</script>)', content, re.DOTALL)
    if not m:
        return content
    inner = m.group(2)
    # Find the last `import ... from` line and insert after it
    import_lines = list(re.finditer(r'^[ \t]*import .*?$', inner, re.MULTILINE))
    if not import_lines:
        return content
    last = import_lines[-1]
    new_inner = (
        inner[:last.end()]
        + "\nimport AppHeader from '@/components/AppHeader.vue'"
        + inner[last.end():]
    )
    return content.replace(m.group(0), m.group(1) + new_inner + m.group(3), 1)


def remove_dup_imports(content: str) -> str:
    """Some views had their own AppButton or HtexLogo imports; we keep those.
    But if the view no longer uses HtexLogo inline (now inside AppHeader), drop
    the unused import."""
    # Heuristic: count `<HtexLogo` occurrences in template. If 0, drop import.
    if content.count('<HtexLogo') == 0 and "import HtexLogo from" in content:
        content = re.sub(
            r"\nimport HtexLogo from '@/components/HtexLogo\.vue'\n",
            "\n",
            content,
        )
    return content


def transform_file(path: Path, scope: str) -> bool:
    content = path.read_text(encoding='utf-8')
    orig = content
    # 1. Replace header block
    new_block = f'    <AppHeader scope="{scope}" />\n'
    content = HEADER_RE.sub(new_block, content, count=1)
    # 2. Add AppHeader import
    content = add_import(content)
    # 3. Drop dead scoped styles
    content = DEAD_STYLE_RE.sub('', content)
    # 4. Drop unused HtexLogo import
    content = remove_dup_imports(content)
    if content == orig:
        print(f'  (no change) {path.name}')
        return False
    path.write_text(content, encoding='utf-8')
    print(f'  ✓ {path.name}')
    return True


def main():
    changed = 0
    for name, scope in FILES.items():
        path = VIEW_DIR / name
        if not path.exists():
            print(f'  MISSING: {path}', file=sys.stderr)
            continue
        if transform_file(path, scope):
            changed += 1
    # Also process admin views (different pattern — they may have their own header)
    # Skip for now: admin pages have sidebar layout, not app-header.
    print(f'\nDone. {changed} files updated.')


if __name__ == '__main__':
    main()
