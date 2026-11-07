"""Record compiler inputs without proprietary SDK content or private paths."""
import hashlib
import json
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sources = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted([*(root / "agent").glob("*"),*(root/"examples/telemetry-service").glob("*")]) if p.suffix in (".c", ".h")}
manifest = {"variant": "gcc_ntox86_64", "flags": "-std=c11 -D_QNX_SOURCE -Wall -Wextra -Werror -O2 -g",
            "binary_sha256": hashlib.sha256((root / "build/pp-agent").read_bytes()).hexdigest(),
            "sources": sources}
manifest['applications']={variant:{'binary_sha256':hashlib.sha256((root/'build'/('telemetry-'+variant)).read_bytes()).hexdigest(),
                                  'build_id':index,'delay_us':delay}
                          for variant,index,delay in [('baseline',1,0),('regressed',2,5000)]}
(root / "build/manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
