#!/usr/bin/env python3
"""One fixed identical-binary calibration; never relaxes legacy product guards."""
import json
from pathlib import Path
import re
import subprocess
from stress_cache_ablation import require,regular,digest,validate_sample,validate_canary as base_canary
from stress_cache_inventory import prerequisite,CELL

SCHEMA='sprig-stress-cache-identical-calibration-v1'
PINS={'main':'b300693e01c652c1a9631c61b7a439892d8f75cd','copy1':'4eb0f4d7afdb19bf22d9667dc520ede8b162c737','copy2':'4eb0f4d7afdb19bf22d9667dc520ede8b162c737'}
PROOF_SCHEMA='sprig-single-release-build-copy-proof-v1'
THRESHOLDS=dict(noiseMedianLower=.95,noiseMedianUpper=1.05,eachArmRestoreMedianMaximum=.90,eachArmWholeMedianMaximum=1.05,sharedBaseline=True,automaticRerun=False,automaticPromotion=False)


def canonical_path(value):
    require(isinstance(value,str) and Path(value).is_absolute() and str(Path(value))==value and '..' not in Path(value).parts,'canonical absolute path required')


def validate_product_identity(products):
    require(isinstance(products,list) and len(products)==3 and all(isinstance(p,dict) for p in products) and [p.get('label') for p in products]==list(PINS),'fixed calibration labels required')
    for p in products:
        require(set(p)=={'label','type','sha','binary','binarySha256','sourcePath'} and p['type']=='sprig' and p['sha']==PINS[p['label']],'fixed calibration source required')
        require(isinstance(p['binarySha256'],str) and re.fullmatch('[a-f0-9]{64}',p['binarySha256']),'invalid calibration binary hash')
        canonical_path(p['binary']);canonical_path(p['sourcePath'])
    require(len({p['binary'] for p in products})==3,'three separate executable copies required')
    require(products[1]['sourcePath']==products[2]['sourcePath']!=products[0]['sourcePath'],'candidate copies must share ONE source checkout, distinct from main')
    require(products[1]['binarySha256']==products[2]['binarySha256']!=products[0]['binarySha256'],'candidate copies must be byte-identical and distinct from main')
    return products


def validate_build_proof(proof,products):
    validate_product_identity(products)
    require(isinstance(proof,dict) and set(proof)=={'schema','source','builtBinary','releaseBuildLog','copies','releaseBuildCount','copyMethod'} and proof['schema']==PROOF_SCHEMA,'single-build proof schema mismatch')
    require(proof['source']==dict(sha=PINS['copy1'],path=products[1]['sourcePath']),'single-build source mismatch')
    require(type(proof['releaseBuildCount']) is int and proof['releaseBuildCount']==1 and proof['copyMethod']=='install -m 0755 from one built binary','not exactly one candidate build/copy protocol')
    origin=proof['builtBinary'];require(isinstance(origin,dict) and set(origin)=={'path','sha256'} and origin['sha256']==products[1]['binarySha256'],'single-build origin hash mismatch');canonical_path(origin['path'])
    require(Path(origin['path']).name=='portable-sprig' and origin['path'] not in {p['binary'] for p in products},'original built binary must be distinct from measured copies')
    require(proof['copies']==[dict(label=p['label'],path=p['binary'],sha256=p['binarySha256']) for p in products[1:]],'candidate copy proof differs')
    log=proof['releaseBuildLog'];require(isinstance(log,dict) and set(log)=={'path','bytes','sha256'} and type(log['bytes']) is int and log['bytes']>0 and isinstance(log['sha256'],str) and re.fullmatch('[a-f0-9]{64}',log['sha256']),'invalid release build log identity');canonical_path(log['path'])
    require(Path(log['path']).name=='portable-release-build.log','wrong candidate release log')
    return proof


def load_build_evidence(path,products,*,live=False):
    path=regular(path);raw=path.read_bytes();proof=validate_build_proof(json.loads(raw),products)
    # Local same-directory evidence works after archive relocation too. Original
    # absolute source/build paths remain recorded, never rewritten into raw data.
    log=regular(path.parent/'portable-release-build.log').read_bytes()
    require(len(log)==proof['releaseBuildLog']['bytes'] and digest(log)==proof['releaseBuildLog']['sha256'],'release build log bytes changed')
    text=log.decode('utf-8',errors='strict')
    require(len(re.findall(r'^\s*Compiling sprig ',text,re.M))==1 and products[1]['sourcePath'] in text,'exactly one recorded candidate package release compilation required')
    if live:
        origin=regular(proof['builtBinary']['path'],True)
        origin_bytes=origin.read_bytes()
        require(digest(origin_bytes)==products[1]['binarySha256'],'original release binary changed')
        copies=[regular(p['binary'],True) for p in products[1:]]
        require(all(p.read_bytes()==origin_bytes for p in copies),'candidate copies differ byte-for-byte from the single built binary')
        require(len({(p.stat().st_dev,p.stat().st_ino) for p in [origin,*copies]})==3,'candidate executables must be independent copies, not hardlink aliases')
        require(Path(proof['releaseBuildLog']['path'])==path.parent/'portable-release-build.log','live build-log path changed')
    return dict(sha256=digest(raw),proof=proof)


def verify_products(products,proof_path):
    validate_product_identity(products);seen_sources=set()
    for p in products:
        require(digest(regular(p['binary'],True).read_bytes())==p['binarySha256'],'calibration executable bytes changed')
        if p['sourcePath'] in seen_sources:continue
        seen_sources.add(p['sourcePath']);source=Path(p['sourcePath'])
        require(source.resolve(strict=True)==source and source.is_dir() and not source.is_symlink(),'canonical calibration source required')
        require(subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==p['sha'],'calibration checkout pin mismatch')
        require(subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip()=='','calibration source changed')
    load_build_evidence(proof_path,products,live=True);prerequisite()
    return products


def identity(products,evidence):
    require(isinstance(evidence,dict) and set(evidence)=={'sha256','proof'} and isinstance(evidence['sha256'],str) and re.fullmatch('[a-f0-9]{64}',evidence['sha256']),'missing build evidence identity')
    validate_build_proof(evidence['proof'],products)
    return dict(series='inventory-identical-binary-v1',purpose='one finite measurement calibration, not trace instrumentation or promotion',instrumentation='off',singleBuildEvidence=evidence,priorInventoryScreen=prerequisite(),thresholds=dict(THRESHOLDS),order='C2C1A/C1AC2/AC2C1',sharedBaselineCaveat='both main-to-copy arms reuse the same three main observations; not six independent pairs')


def validate_report_identity(report,products,evidence):
    require(report.get('schema')==SCHEMA and report.get('inventoryCalibration')==identity(products,evidence),'calibration identity/proof missing or changed')


def validate_selection(stage,backend,rounds,cell,pair_order):
    require(stage in ('canary','reverse-latin') and backend=='native' and pair_order=='forward','calibration is explicit native-only reverse Latin')
    require(type(rounds) is int and rounds==(1 if stage=='canary' else 3),'fixed calibration sample count required')
    require(cell==('canary' if stage=='canary' else CELL),'calibration only permits eligible64KiB cell')


def order(products,round_no,stage):
    require(stage in ('canary','reverse-latin') and type(round_no) is int and 0<=round_no<(1 if stage=='canary' else 3),'invalid calibration order')
    labels=list(PINS) if stage=='canary' else list(reversed(PINS));labels=labels[round_no:]+labels[:round_no];by_label={p['label']:p for p in products};return [by_label[label] for label in labels]


def validate_canary(path,products,budget,evidence):
    validate_report_identity(json.loads(regular(path).read_bytes()),products,evidence)
    return base_canary(path,products,budget,schema=SCHEMA)
