"""meta.py - merge _meta_*.json (written by props/fx/ui) into the art manifest."""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '../../Assets/AquaScape/Art/sprite_meta_art.json')

meta = {}
for f in sorted(glob.glob(os.path.join(HERE, '_meta_*.json'))):
    meta.update(json.load(open(f)))
json.dump(meta, open(OUT, 'w'), indent=2, sort_keys=True)
print('wrote', len(meta), 'entries ->', os.path.normpath(OUT))
