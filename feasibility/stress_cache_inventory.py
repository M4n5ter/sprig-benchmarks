#!/usr/bin/env python3
"""Explicit inventory-only reverse confirmation; old admission gates stay separate."""
import json
from pathlib import Path
import re
import subprocess
from stress_cache_ablation import (require, digest, regular, canonical, validate_sample,
    validate_canary as base_canary, shared_budget)

SCHEMA='sprig-stress-cache-inventory-confirmation-v1'
PINS={'main':'b300693e01c652c1a9631c61b7a439892d8f75cd',
      'inventory':'c392d45079314cdcf9813371ec9120d78be7bcd6',
      'portable':'4eb0f4d7afdb19bf22d9667dc520ede8b162c737'}
CELL='cache-large-64k-1024'
FILE_HASHES={'inventory':'9a6bc355f288e5741e018d7548839049345d3d32492c422ce51b4ed4f86a0fee',
             'portable':'bba4074614af5aea89d1ab1292e4ad17003b4c991d6979eb8cad2feedd2d763b'}
PRODUCTION_PREFIX_SHA256='95fa75c3ee270cbff96b3dd5d8cc3cec6a5d48ba059839608609f0e2917ace49'
BUNDLE_HASHES={
 'run40302159760.json':'565c23d3d97b6996e05ad362072dad4dd43343a0233effe477f85b2c7bafb6f8',
 'recomputed-summary.json':'936b398fcc3f0de95d8b04ee94467fc515fad8cf0fc9516ff99a9d59c0023e2d',
 'provenance-audit.json':'441231760cc88f4ea536ba5470315205eebfb850827dacf816bc0106f81506fd',
 'artifact-files.json':'ecc570528a151aeb7156164d79eb6573d93d59f39c821fe7c87e41e73d0ba830'}
BUNDLE=Path(__file__).with_name('cache-inventory-prerequisite')


def prerequisite(directory=BUNDLE):
    """Hash-bound prior root-reviewed attestation, NOT a fresh raw-artifact audit."""
    loaded={}
    for name,sha in BUNDLE_HASHES.items():
        body=regular(Path(directory)/name).read_bytes()
        require(digest(body)==sha,'reviewed inventory prerequisite bytes changed: '+name)
        loaded[name]=json.loads(body)
    run=loaded['run40302159760.json'];audit=loaded['provenance-audit.json'];summary=loaded['recomputed-summary.json'];manifest=loaded['artifact-files.json']
    require(run['headSha']=='93ce3366204a34eeefdd95ebc92aad1b2d976468' and run['status']=='completed' and run['conclusion']=='success' and run['url'].endswith('/40302159760'),'wrong prerequisite run/head')
    require(audit['ok'] is True and audit['complete'] is True and audit['run']==40302159760 and audit['head']==run['headSha'] and audit['errors']==[] and audit['serverSummaryMatches'] is True,'prior audit failed')
    require(audit['canarySamples']==3 and audit['screenSamples']==9 and audit['artifactFiles']==len(manifest)==217 and audit['artifactBytes']==sum(r['bytes'] for r in manifest)==22776206,'prior evidence cardinality mismatch')
    require(summary['complete'] is True and summary['status']=='passed' and summary['cell']==CELL and len(summary['records'])==9 and summary['errors']==[],'prior eligible-cell screen incomplete')
    require({p['label']:p['sha'] for p in summary['products']}=={**{k:PINS[k] for k in ('main','inventory')},'admission':'f481aaba987d960bf119e95b68f5b38da56e1581'},'prior source pins changed')
    edge=summary['comparisons']['main-to-inventory']
    require(edge['restore_seconds']['medianPairedRatio']<=0.90 and edge['wholeSampleSeconds']['medianPairedRatio']<=1.05 and len(edge['restore_seconds']['pairs'])==3 and all(p['candidateOverBaseline']<1 for p in edge['restore_seconds']['pairs']),'prior inventory screen is not eligible')
    return dict(kind='root-reviewed-prior-audit-attestation-not-fresh-raw-reaudit',run=40302159760,head=run['headSha'],artifactId=12641212210,cell=CELL,bundleFileSha256=dict(BUNDLE_HASHES),artifactFiles=217,artifactBytes=22776206,restoreMedianPairedRatio=edge['restore_seconds']['medianPairedRatio'],wholeMedianPairedRatio=edge['wholeSampleSeconds']['medianPairedRatio'])


def validate_product_identity(products):
    require(isinstance(products,list) and len(products)==3 and all(isinstance(p,dict) for p in products) and [p.get('label') for p in products]==list(PINS),'fixed inventory confirmation labels required')
    for p in products:
        require(set(p)=={'label','type','sha','binary','binarySha256','sourcePath'} and p['type']=='sprig' and p['sha']==PINS[p['label']],'fixed inventory confirmation product required')
        require(isinstance(p['binarySha256'],str) and re.fullmatch('[a-f0-9]{64}',p['binarySha256']),'invalid inventory binary hash')
    for name in ('binary','sourcePath'):
        require(len({p[name] for p in products})==3,'distinct inventory '+name+' required')
    require(products[0]['binarySha256'] not in {p['binarySha256'] for p in products[1:]},'main binary must remain distinct')
    return products


def source_equivalence(products):
    """Known cfg(test)-only repair; compare every tracked tree entry, not a claim flag."""
    validate_product_identity(products);trees=[]
    for product in products[1:]:
        source=Path(product['sourcePath'])
        lines=subprocess.check_output(['git','-C',str(source),'ls-tree','-r','--full-tree','HEAD'],text=True).splitlines()
        trees.append({line.split('\t',1)[1]:line.split('\t',1)[0] for line in lines})
        body=regular(source/'src/file_cache.rs').read_bytes()
        require(digest(body)==FILE_HASHES[product['label']],'known test-only file bytes changed')
        require(body.count(b'#[cfg(test)]\nmod tests {')==1,'test-module boundary changed')
        prefix=body.split(b'#[cfg(test)]\nmod tests {',1)[0]
        seam=b'    #[cfg(test)]\n    tests::inject_fill_fault()?;\n'
        require(prefix.count(seam)==(1 if product['label']=='portable' else 0),'test-only seam changed')
        require(digest(prefix.replace(seam,b''))==PRODUCTION_PREFIX_SHA256,'release production prefix differs')
    require(set(trees[0])==set(trees[1]) and [name for name in trees[0] if trees[0][name]!=trees[1][name]]==['src/file_cache.rs'],'other tracked release/build/source files changed')
    return equivalence_identity(products)


def equivalence_identity(products):
    validate_product_identity(products)
    return dict(kind='exact-known-cfg-test-only-source-repair',sourcePins={k:PINS[k] for k in FILE_HASHES},fileSha256=dict(FILE_HASHES),releaseProductionPrefixSha256=PRODUCTION_PREFIX_SHA256,onlyChangedTrackedFile='src/file_cache.rs',binaryHashesEqual=products[1]['binarySha256']==products[2]['binarySha256'],interpretation='inventory-to-portable is a no-runtime-source-change/noise control, not an additional optimization')


def verify_products(products):
    validate_product_identity(products)
    for p in products:
        binary=regular(p['binary'],True);require(digest(binary.read_bytes())==p['binarySha256'],'inventory binary identity changed')
        source=Path(p['sourcePath']);require(source.is_absolute() and source.resolve(strict=True)==source and source.is_dir() and not source.is_symlink(),'canonical inventory source required')
        require(subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==p['sha'],'inventory checkout pin changed')
        require(subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip()=='','inventory checkout changed')
    source_equivalence(products);prerequisite()
    return products


def identity(products):
    return dict(series='inventory-only-reverse-v1',prerequisite=prerequisite(),releaseSourceEquivalence=equivalence_identity(products))


def validate_report_identity(report,products):
    require(report.get('schema')==SCHEMA and report.get('inventoryConfirmation')==identity(products),'inventory confirmation proof missing or changed')


def validate_selection(stage,backend,rounds,cell,pair_order):
    require(stage in ('canary','reverse-latin') and backend=='native' and pair_order=='forward','inventory confirmation is explicit native-only reverse Latin')
    require(type(rounds) is int and rounds==(1 if stage=='canary' else 3),'inventory requires three canaries or nine confirmation samples')
    require(cell==('canary' if stage=='canary' else CELL),'inventory confirmation cell changed')


def order(products,round_no,stage):
    require(stage in ('canary','reverse-latin') and type(round_no) is int and 0<=round_no<(1 if stage=='canary' else 3),'invalid inventory confirmation order')
    labels=list(PINS) if stage=='canary' else list(reversed(PINS))
    labels=labels[round_no:]+labels[:round_no];indexed={p['label']:p for p in products}
    return [indexed[label] for label in labels]


def validate_canary(path,products,budget):
    report=json.loads(regular(path).read_bytes());validate_report_identity(report,products)
    return base_canary(path,products,budget,schema=SCHEMA)
