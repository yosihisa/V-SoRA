"""Write only the installed scientific/test dependency closure, no local paths."""
import argparse
from importlib.metadata import distribution
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    todo=['numpy','scipy','astropy','matplotlib','baseband','pytest'];seen={}
    while todo:
        name=canonicalize_name(todo.pop())
        if name in seen: continue
        d=distribution(name);seen[name]=d.version
        for value in d.requires or []:
            r=Requirement(value)
            if r.marker is None or r.marker.evaluate({'extra':''}): todo.append(r.name)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('# Scientific/test versions verified on Linux Python 3.12.\n'+
                    '\n'.join(f'{name}=={version}' for name,version in sorted(seen.items()))+'\n')
    print(f'{len(seen)} pinned scientific/test dependencies')


if __name__=='__main__': main()
