"""Check repository-local Markdown links without network access."""
from pathlib import Path
import re
from urllib.parse import unquote,urlsplit


def check(root):
    problems=[];links=0
    for path in root.rglob('*.md'):
        relative=path.relative_to(root)
        if any(x.startswith('.') for x in relative.parts) or relative.parts[0] in ('outputs','build','dist'):
            continue
        text=path.read_text()
        for match in re.finditer(r'\]\(([^)]+)\)',text):
            target=match.group(1).strip().strip('<>')
            if urlsplit(target).scheme or target.startswith('#'): continue
            target=unquote(target.split('#')[0])
            if not target: continue
            links+=1
            if not (path.parent/target).exists():
                problems.append(f'{relative}: missing {target}')
    return links,problems


if __name__=='__main__':
    links,problems=check(Path(__file__).resolve().parents[1])
    for line in problems: print(line)
    print(f'Local Markdown links: {links}, missing: {len(problems)}')
    raise SystemExit(bool(problems))
