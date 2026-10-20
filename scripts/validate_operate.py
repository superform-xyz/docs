#!/usr/bin/env python3
"""Validate final MDX; optionally run the real engine in a fresh pinned archive.

Public mode uses only repository fixtures and Python's standard library. Engine
mode requires an explicitly supplied private local checkout and cached Go
prerequisites. Never fetches source, calls production, or writes to the checkout.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone

REV = 'fc50b3ca5f1d66294e7476b1ff1088e92b126fbd'
HERE = Path(__file__).resolve().parent
DEFAULT_DOCS = HERE.parent
CAPTURE = HERE / 'fixtures/operate-public-2026-10-19.json'
OWNED = ['strategy/'+x for x in ['dsl','quickstart','action-config','anti-patterns','troubleshooting','variables','lifecycle']] + ['playbooks/'+x for x in ['reserves','carry','deleverage','redemptions']] + ['ui/'+x for x in ['strategy','simulation','intent-history','dashboard']] + ['automation/monitoring','automation/webhooks']
P='position_0xacaa6ee9de7631b927242d42fb8c256860545fa457560f550b653a925bc6cb3b'
U='0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
Y='ys_0x91c056b6d4311a743614fbc03ac32d4e6a2d3a3c'
D=P+'_debt_'+U+'_amount'; V=P+'_risk_debt_value_e18'; C=P+'_risk_collateral_value_e18'; I='token_'+U+'_amount'
IDS=['5db21999-c05c-4af3-8824-9f7ecc746576','a8d25935-9f6d-4046-a87a-82048af0cc1c','7166275b-5f8d-4b61-b79e-bddca00f3884','b72f1db5-0956-4b9e-bb5a-e80591e34699']
GATES = [
    'TestRiskGate_CooldownActive',
    'TestShard_MaxConcurrent_BlocksSecondIntent',
    'TestEngine_Update_VersionConflict_ReturnsDomainError',
    'TestUpdateStrategy_VersionConflict',
    'TestUpdateStrategy_VersionConflict_Returns409',
]


def blocks(text):
    result = []
    fence = None
    language = ''
    body = []
    for line in text.splitlines(keepends=True):
        if fence is None:
            match = re.match(r'^ {0,3}(`{3,}|~{3,})([^\n]*)\n?$', line)
            if match:
                fence, language = match[1], match[2].strip()
                body = []
        elif re.match(r'^ {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*$', line):
            result.append((language, ''.join(body)))
            fence = None
        else:
            body.append(line)
    assert fence is None, 'snippet inventory: unterminated fence'
    return result


def inventory_docs(docs):
    """Fail closed on new/changed fences, including pages with no prior code."""
    expected = json.loads((HERE / 'fixtures/operate-snippet-inventory.json').read_text())
    paths = [docs / 'operate.mdx', *sorted((docs / 'operate').rglob('*.mdx'))]
    assert {p.relative_to(docs).as_posix() for p in paths} == set(expected), 'snippet inventory page set changed'
    result = {}
    allowed = {'engine', 'python-tested', 'public-read-command', 'api-route-notation', 'illustrative-json', 'illustrative-text'}
    for path in paths:
        route = path.relative_to(docs).as_posix()
        fences = blocks(path.read_text())
        entries = expected[route]
        assert len(fences) == len(entries), f'snippet inventory: unclassified/missing fence in {route}'
        for index, ((language, body), entry) in enumerate(zip(fences, entries)):
            label = f'snippet inventory {route}:{index}'
            assert language == entry['language'] and entry['classification'] in allowed, label
            assert hashlib.sha256(body.encode()).hexdigest() == entry['sha256'], label + ': changed fence needs review and fixtures'
            if entry['classification'] == 'illustrative-json':
                json.loads(body)
            if entry['classification'] == 'public-read-command':
                subprocess.run(['bash', '-n'], input=body, text=True, check=True, capture_output=True)
        result[route] = entries
    return result


def validate_capture_consistency(docs):
    """Bind repeated deployment IDs, policy thresholds and plans to dated data."""
    capture = json.loads(CAPTURE.read_text())
    configs = capture['strategies']
    by_label = {cfg['name'].split()[0]: cfg for cfg in configs}
    ap0, ap1 = by_label['AP0'], by_label['AP1']
    loan = ap0['action_config']['execution_params']['plan']['steps'][0]
    source = ap1['action_config']['execution_params']['plan']['steps'][0]
    params = loan['params']
    from decimal import Decimal
    expressions = ' '.join(node['expr'] for node in ap0['rules']['children'])
    def matched(pattern, text):
        match = re.search(pattern, text)
        assert match is not None, 'capture consistency: expected source field missing'
        return match[1]
    lower = str(int(Decimal(matched(r'>= (0\.\d+) \*', expressions)) * 100))
    upper = str(int(Decimal(matched(r'< (0\.\d+) \*', expressions)) * 100))
    target = str(int(Decimal(matched(r' - (0\.\d+) \*', ap0['action_config']['size_expr'])) * 100))
    position = matched(r'position_(0x[0-9a-f]{64})', expressions)
    capture_text = json.dumps(capture)
    hex_pattern = r'0x[0-9a-fA-F]{40,}'
    uuid_pattern = r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}'
    known_hex = {x.lower() for x in re.findall(hex_pattern, capture_text)}
    known_ids = set(re.findall(uuid_pattern, capture_text))
    # Historical receipt identifiers are not strategy-config fields. Scope their
    # exception to the trace page; never silently add unknown deployment values.
    trace_hex = {'0x100e0ae81927d2141d2a9d65b342c8e900fedd37e8c32eea195117e2681a8a2f'}
    trace_ids = {'967eb2f7-f8f9-4eff-82cc-a933e9bb3f95', '99a5081e-9975-4cc9-82ec-fac97f355bc5', 'ea9eb763-469d-5a10-a6d7-11f50e665079'}
    pages = {p.relative_to(docs).as_posix(): p.read_text() for p in [docs / 'operate.mdx', *sorted((docs / 'operate').rglob('*.mdx'))]}
    for route, text in pages.items():
        trace = route == 'operate/ui/intent-history.mdx'
        # Separate pinned source-test example, not an NVDA deployment address.
        source_example_hex = {'0xe8dd6a1e13244a27bdaa19ccbf33013647c675d1'} if route == 'operate/strategy/variables.mdx' else set()
        assert {x.lower() for x in re.findall(hex_pattern, text)} <= known_hex | source_example_hex | (trace_hex if trace else set()), f'capture consistency: unknown deployment/position in {route}'
        assert set(re.findall(uuid_pattern, text)) <= known_ids | (trace_ids if trace else set()), f'capture consistency: unknown strategy/trace ID in {route}'
        for lo, hi in re.findall(r'(\d+)% <= LTV < (\d+)%', text):
            assert (lo, hi) == (lower, upper), f'capture consistency: AP window in {route}'
        for label, value in re.findall(r"(AF(?:0/AF2|0|2|'s)?|AP(?:0/AP1|0|1|'s)?)[^\n.]*?`LTV >= (\d+)%`", text):
            assert value == (upper if label.startswith('AF') else lower), f'capture consistency: threshold in {route}'
    variables = pages['operate/strategy/variables.mdx']
    alias_rows = {parts[1].strip(): parts[2].strip() for line in variables.splitlines() if line.startswith('|') and len(parts := line.split('|')) > 3}
    prefix = 'position_' + position
    source_prefix = 'ys_' + source['params']['yieldSource'].lower()
    aliases = {
        'Idle USDC': 'token_' + params['loanToken'].lower() + '_amount',
        'USDC debt': prefix + '_debt_' + params['loanToken'].lower() + '_amount',
        'Collateral risk value': prefix + '_risk_collateral_value_e18',
        'Debt risk value': prefix + '_risk_debt_value_e18',
        'NVDAc collateral': prefix + '_collateral_' + params['collateralToken'].lower() + '_amount',
        'Clearstar shares': source_prefix + '_shares', 'Clearstar assets': source_prefix + '_amount',
        'Clearstar PPS': source_prefix + '_pps', 'Asset exit liquidity': source_prefix + '_liquidity',
        'Share exit liquidity': source_prefix + '_liquidity_shares',
    }
    for label, alias in aliases.items():
        assert alias_rows.get(label) == f'`{alias}`', f'capture consistency: alias mapping {label}'
    history = pages['operate/ui/intent-history.mdx']
    for pattern in [r'istr=([0-9a-f-]+)', r'strategy_id=([0-9a-f-]+)', r'\| Strategy \| `([^`]+)`']:
        found = re.findall(pattern, history)
        assert found and set(found) == {ap1['id']}, 'capture consistency: AP1 trace strategy identity'
    carry = pages['operate/playbooks/carry.mdx']
    rows = {parts[1].strip(): parts[2:] for line in carry.splitlines() if line.startswith('|') and len(parts := line.split('|')) > 3}
    mapping = {
        'Chain': str(loan['chain_id']), 'Vault': loan['vault_address'],
        'Engine vault ID': ap0['vault_id'],
        'Execution strategy': ap0['action_config']['execution_params']['strategy_address'],
        'NVDAc collateral': params['collateralToken'], 'USDC debt/source asset': params['loanToken'],
        'Aave V4 Spoke': params['spoke'], 'Loan yield-source identity': params['yieldSource'],
        'Loan source oracle': params['yieldSourceOracleId'], 'Normalized position ID': position,
        'Clearstar cbAssets source': source['params']['yieldSource'],
        'Source PPS oracle': source['params']['yieldSourceOracleId'],
    }
    for label, value in mapping.items():
        assert f'`{value.lower()}`' in '|'.join(rows.get(label, [])).lower(), f'capture consistency: mapping {label}'
    assert f"`{params['supplyReserveId']}` / `{params['borrowReserveId']}`" in '|'.join(rows['Supply / borrow reserve IDs']), 'capture consistency: reserve IDs'
    for label, cfg in by_label.items():
        row = '|'.join(rows.get(label, []))
        assert f"`{cfg['id']}`" in row and f"{cfg['version']} / {cfg['state']}" in row, f'capture consistency: {label} ID/version/state'
    for cfg in capture['reference_definitions']:
        candidates = [line for line in carry.splitlines() if line.startswith('|') and cfg['id'] in line]
        assert len(candidates) == 1 and cfg['label'] in candidates[0] and cfg['state'] in candidates[0], f"capture consistency: reference {cfg['label']}"
    assert f'`{lower}% <= LTV < {upper}%` and size toward {target}%' in carry, 'capture consistency: AP target'
    assert f'`LTV >= {upper}%`' in carry, 'capture consistency: AF trigger'
    deleverage = pages['operate/playbooks/deleverage.mdx']
    assert f'with a {target}% repayment target' in deleverage, 'capture consistency: repeated target'
    assert f"AF's `LTV >= {upper}%`" in deleverage and f"AP's `LTV >= {lower}%`" in deleverage, 'capture consistency: disarming thresholds'
    # Schema/plan equality is exact, not a substring check.
    plans = [json.loads(body) for lang, body in blocks(pages['operate/strategy/action-config.mdx']) if lang == 'json']
    assert plans[0] == capture['borrow_action_config'], 'capture consistency: borrow plan differs from capture'
    assert plans[1] == ap1['action_config']['execution_params'], 'capture consistency: AP1 plan differs from capture'
    return len(pages)


def extract_docs(docs):
    capture=json.loads(CAPTURE.read_text())
    assert capture['provenance']['engine_revision']==REV, 'capture engine revision mismatch'
    live=capture['strategies']
    byid={s['id']:s for s in live}
    assert len(live)==len(byid)==4 and set(byid)==set(IDS), 'unexpected capture projection'
    snippets=[]; pageblocks={}; manifest={}
    for route in OWNED:
        p=docs/'operate'/(route+'.mdx'); text=p.read_text()
        manifest['operate/'+route+'.mdx']=hashlib.sha256(text.encode()).hexdigest()
        pageblocks[route]=blocks(text)
        for index,(language,body) in enumerate(pageblocks[route]):
            lang=language.split()[0] if language else ''
            name=f'{route}:{index}'
            if lang=='json':
                obj=json.loads(body)
                if 'type' in obj: kind='rule'
                elif 'action_config' in obj: kind='config'
                elif 'action' in obj: kind='action'
                elif 'plan' in obj: kind='params'
                elif 'mode' in obj: kind='conviction'
                else: raise AssertionError('Unclassified JSON: '+name)
                snippets.append(dict(name=name,kind=kind,data=obj))
            elif lang=='text':
                if route=='ui/simulation' and body.strip()=='liquidity observations are not supported by simulation replay': continue
                snippets.append(dict(name=name,kind='numeric',data=body.strip()))
    def first(route,language):
        return next(body.strip() for lang,body in pageblocks[route] if lang.split()[0]==language)
    def nums(route): return [body.strip() for lang,body in pageblocks[route] if lang.split()[0]=='text']
    cases=[]
    def case(name,node,size,snap,want,amount='',runtime_error=False):
        cases.append(dict(name=name,rule=node,size=size,snapshot={k:str(v) for k,v in snap.items()},want=want,amount=amount,runtime_error=runtime_error))
    def leaf(expression): return {'type':'EXPR','expr':expression}
    reserve=json.loads(first('strategy/quickstart','json')); size=first('strategy/quickstart','text')
    for name,tvl,idle,want,amount in [('normal',100000000,20000000,True,'12500000'),('boundary10',100000000,10000000,False,''),('above10',100000000,10000001,True,'2500001'),('post_action',100000000,7500000,False,''),('zero',0,0,False,'')]:
        case('reserve_'+name,reserve,size,{'vault_tvl':tvl,'vault_free_assets':idle},want,amount)
    case('reserve_missing',reserve,size,{},False)
    refill_rules=[json.loads(body) for lang,body in pageblocks['playbooks/reserves'] if lang=='json']
    refill=refill_rules[1]; refillsize=nums('playbooks/reserves')[1]
    case('refill_normal',refill,refillsize,{'vault_tvl':100000000,'vault_free_assets':4000000},True,'3500000')
    case('refill_boundary5',refill,refillsize,{'vault_tvl':100000000,'vault_free_assets':5000000},False)
    case('refill_post_action',refill,refillsize,{'vault_tvl':100000000,'vault_free_assets':7500000},False)
    full_refill = refill_rules[2]
    full_size = nums('playbooks/reserves')[3]
    full_snap = {'vault_tvl': 100000000, 'vault_free_assets': 4000000,
                 Y+'_pps': '1.25', Y+'_shares': 80*10**18,
                 Y+'_liquidity_shares': 80*10**18, Y+'_liquidity': 100000000}
    case('complete_refill_normal', full_refill, full_size, full_snap, True, '2800000000000000000')
    case('complete_refill_liquidity_cap', full_refill, full_size,
         dict(full_snap, **{Y+'_liquidity': 2000000}), True, '1584000000000000000')
    for key in [Y+'_pps', Y+'_shares', Y+'_liquidity', Y+'_liquidity_shares', 'vault_tvl']:
        case('complete_refill_zero_'+key, full_refill, full_size, dict(full_snap, **{key: 0}), False)
    for idle in [5000000, 5980000, 7500000]:
        case('complete_refill_post_or_boundary_'+str(idle), full_refill, full_size,
             dict(full_snap, vault_free_assets=idle), False)
    case('complete_refill_missing', full_refill, full_size, {}, False)
    case('complete_refill_dust', full_refill, full_size,
         dict(full_snap, **{Y+'_shares': 1, Y+'_liquidity_shares': 1}), True, '0')
    case('refill_zero',refill,refillsize,{},False)
    queue=json.loads(first('playbooks/redemptions','json')); queue_size=first('playbooks/redemptions','text')
    case('queue_shortfall',queue,queue_size,{'vault_redeem_queue_count':2,'vault_redeem_queue_value':10000000,'vault_free_assets':3000000},True,'7000000')
    case('queue_funded',queue,queue_size,{'vault_redeem_queue_count':2,'vault_redeem_queue_value':10000000,'vault_free_assets':10000000},False)
    case('queue_missing',queue,queue_size,{},False)
    def loan(ltv,idle=10000000,liquidity=100000000,pps='1',shares=100*10**18,qs=100*10**18):
        return {D:ltv*10**6,V:ltv*10**18,C:100*10**18,I:idle,Y+'_pps':pps,Y+'_shares':shares,Y+'_liquidity':liquidity,Y+'_liquidity_shares':qs}
    simple_rule=json.loads(first('playbooks/deleverage','json')); simple_size=first('playbooks/deleverage','text')
    for ltv,want,amount in [(51,False,''),(52,True,'2000000'),(54,True,'4000000'),(55,False,'')]:
        case('simplified_'+str(ltv),simple_rule,simple_size,loan(ltv),want,amount)
    case('simplified_idle_cap',simple_rule,simple_size,loan(54,idle=1000000),True,'1000000')
    case('simplified_missing',simple_rule,simple_size,{},False)
    for key in [D,V,C]:
        snap=loan(54);snap[key]=0;case('simplified_zero_'+key,simple_rule,simple_size,snap,False)
    for id in IDS:
        cfg=byid[id]
        case('captured_missing_'+id,cfg['rules'],cfg['action_config']['size_expr'],{},False)
        case('post_unwind_51_'+id,cfg['rules'],cfg['action_config']['size_expr'],loan(51,idle=0),False)
    fixtures=[('AP0_52',IDS[0],loan(52),True,'2002001'),('AP0_54',IDS[0],loan(54),True,'4004001'),('AP0_55',IDS[0],loan(55),False,''),('AP0_dust',IDS[0],loan(54,idle=1),True,'1'),('AP1_54',IDS[1],loan(54,idle=0),True,'4004801960392078416'),('AP1_55',IDS[1],loan(55,idle=0),False,''),('AF0_55',IDS[2],loan(55),True,'10000000'),('AF2_55',IDS[3],loan(55,idle=0),True,'55066014202840568114'),('AF2_liquidity',IDS[3],loan(56,idle=0,liquidity=2000000),True,'1980000000000000000'),('AP1_share_liquidity',IDS[1],loan(54,idle=0,qs=2*10**18),True,'1980000000000000000'),('AF2_zero_liquidity',IDS[3],loan(56,idle=0,liquidity=0),False,''),('AF2_zero_pps',IDS[3],loan(56,idle=0,pps='0'),False,''),('AP1_dust_disarms',IDS[1],loan(54,idle=1),False,'')]
    for name,id,snap,want,amount in fixtures: case(name,byid[id]['rules'],byid[id]['action_config']['size_expr'],snap,want,amount)
    cap=nums('playbooks/reserves')[2]
    case('documented_share_cap_liquidity',leaf(Y+'_pps > 0'),cap,loan(54,idle=0,liquidity=2000000),True,'1980000000000000000')
    case('documented_share_cap_zero_pps',leaf(Y+'_pps > 0'),cap,loan(54,idle=0,pps='0'),False)
    case('documented_share_cap_zero_liquidity',leaf(Y+'_pps > 0'),cap,loan(54,idle=0,liquidity=0),True,'0')
    zero_collateral=loan(56); zero_collateral[C]=0
    case('captured_AF0_zero_collateral',byid[IDS[2]]['rules'],byid[IDS[2]]['action_config']['size_expr'],zero_collateral,True,'10000000')
    case('documented_min_max',leaf('true'),first('strategy/dsl','text'),{},True,'2')
    case('conversion',leaf('true'),first('strategy/variables','text'),{},True,'1600000000000000000')
    case('integer_truncation',leaf('true'),'1.9',{},True,'1')
    case('dust_truncation',leaf('true'),'0.9',{},True,'0')
    case('static_valid_runtime_division',leaf('vault_free_assets / vault_tvl > 0.1'),'',{},False,runtime_error=True)
    case('guarded_division',leaf('vault_tvl > 0 && vault_free_assets / vault_tvl > 0.1'),'',{},False)
    for lang,body in pageblocks['strategy/dsl']:
        if lang=='json':
            node=json.loads(body)
            if node.get('type') in ['VOTE','NOT']: case('grammar_'+node['type'],node,'',{},True)
    action=json.loads(first('strategy/action-config','json'))
    assert action==capture['borrow_action_config'], 'borrow plan differs from capture'
    params=[json.loads(body) for lang,body in pageblocks['strategy/action-config'] if lang=='json'][1]
    assert params==byid[IDS[1]]['action_config']['execution_params'], 'AP1 params differ from capture'
    fixture=dict(snippets=snippets,cases=cases,live=[byid[x] for x in IDS])
    return fixture, manifest, pageblocks


def test_python_snippets(pageblocks):
    contexts={}
    for route in ['automation/monitoring','automation/webhooks']:
        ctx={}
        for lang,body in pageblocks[route]:
            if lang=='python': exec(compile(body,route,'exec'),ctx)
        contexts[route]=ctx
    classify=contexts['automation/monitoring']['classify_success_ratio']
    now=datetime(2026,10,20,tzinfo=timezone.utc)
    cases=[(None,'UNKNOWN'),({},'UNKNOWN'),({'value':1},'UNKNOWN'),({'value':float('nan'),'observed_at':now},'UNKNOWN'),({'value':1.01,'observed_at':now},'UNKNOWN'),({'value':1,'observed_at':now-timedelta(seconds=61)},'UNKNOWN'),({'value':1,'observed_at':now+timedelta(seconds=1)},'UNKNOWN'),({'value':.79,'observed_at':now},'CRITICAL'),({'value':.80,'observed_at':now},'WARNING'),({'value':.95,'observed_at':now},'HEALTHY')]
    for record,want in cases: assert classify(record,now,60)==want
    collect=contexts['automation/webhooks']['collect_audit_window']
    mark=now-timedelta(seconds=60)
    rows=[{'id':str(i),'created_at':(mark+timedelta(seconds=i)).isoformat()} for i in range(5)]
    calls=[]
    def fetch(params):
        calls.append(params);return list(reversed(rows))[params['offset']:params['offset']+params['limit']]
    output,high=collect(fetch,mark,now,{'1'},page_size=2)
    assert len(calls)==3 and [r['id'] for r in output]==['0','2','3','4'] and high==mark+timedelta(seconds=4)
    assert len({p['end_time'] for p in calls})==1
    output,high2=collect(lambda p:[],high,now,set());assert not output and high2==high
    delayed={'id':'delayed','created_at':(mark-timedelta(seconds=10)).isoformat()}
    output,high2=collect(lambda p:[delayed],high,now,set());assert len(output)==1 and high2==high
    output,high2=collect(lambda p:[rows[4],rows[4]],high,now,set(),page_size=3);assert len(output)==1
    def failure(p):
        if p['offset']>0:raise OSError('page failed')
        return rows[:2]
    try:collect(failure,mark,now,set(),page_size=2)
    except OSError:pass
    else:raise AssertionError('page failure swallowed')
    try:collect(lambda p:rows[:2],mark,now,set(),page_size=2,max_pages=1)
    except RuntimeError:pass
    else:raise AssertionError('page bound ignored')
    print('PASS Python final-MDX classifier (10 cases) and polling (6 scenarios)')


def run_engine(source, fixture, manifest):
    # Archive the immutable revision, not HEAD or the possibly dirty working tree.
    source=source.resolve()
    actual=subprocess.check_output(['git','-C',str(source),'rev-parse',REV+'^{commit}'],text=True).strip()
    if actual!=REV:
        raise RuntimeError('source does not contain the exact pinned engine commit')
    data=subprocess.check_output(['git','-C',str(source),'archive','--format=tar',REV])
    with tempfile.TemporaryDirectory(prefix='operate-docs-') as temp:
        work=Path(temp).resolve()
        if work.is_relative_to(source):
            raise RuntimeError('TMPDIR must be outside the read-only source checkout')
        archive=work/'engine'
        archive.mkdir()
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            tf.extractall(archive,filter='data')
        fixture_path=work/'final-mdx-fixtures.json'
        fixture_path.write_text(json.dumps(fixture,indent=2)+'\n')
        (work/'final-mdx-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        shutil.copyfile(HERE/'operate_docs_test.go',archive/'internal/rule/operate_docs_test.go')
        # No downloads, no live service config. Go's cached toolchain may satisfy
        # the pinned module's version without changing the system Go install.
        env={key:value for key,value in os.environ.items() if key in {
            'PATH','HOME','TMPDIR','TMP','TEMP','SYSTEMROOT','GOCACHE','GOMODCACHE','GOPATH',
        }}
        env.update(OPERATE_DOCS_FIXTURE=str(fixture_path),GOPROXY='off',GOSUMDB='off',
                   GOTOOLCHAIN='auto',GOWORK='off',GOFLAGS='-mod=readonly')
        commands=[
            (['go','test','./internal/rule','-run','^TestOperateDocs','-count=1','-v'],
             ['TestOperateDocsSnippets','TestOperateDocsEvaluator','TestOperateDocsCapturedConfigsAndSimulation','TestOperateDocsRejectedSyntax']),
            (['go','test','./internal/engine','./internal/api','-run','^('+'|'.join(GATES)+')$','-count=1','-v'],GATES),
        ]
        for command,required in commands:
            result=subprocess.run(command,cwd=archive,env=env,text=True,stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,timeout=300)
            print(result.stdout,end='')
            if result.returncode:
                raise RuntimeError('engine tests failed; install/cache pinned Go toolchain and modules separately if missing')
            passed=set(re.findall(r'^--- PASS: (\w+) ',result.stdout,re.M))
            if not set(required)<=passed:
                raise RuntimeError('expected tests did not run: '+', '.join(sorted(set(required)-passed)))
    print(f'PASS real engine {REV}: {len(fixture["snippets"])} compiler/schema snippets; '
          f'{len(fixture["cases"])} evaluator cases; {len(fixture["live"])} captured configs; {len(GATES)} gates')


def main():
    if not __debug__:
        raise SystemExit('Run without -O/PYTHONOPTIMIZE: assertions are verification checks')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docs',type=Path,default=DEFAULT_DOCS,help='final docs repository root')
    parser.add_argument('--source',type=Path,help='optional local superman-strategy checkout containing the pinned commit')
    args=parser.parse_args()
    inventory = inventory_docs(args.docs.resolve())
    consistent_pages = validate_capture_consistency(args.docs.resolve())
    fixture,manifest,pages=extract_docs(args.docs.resolve())
    tested = {'operate/' + snippet['name'] for snippet in fixture['snippets']}
    classified = {route + ':' + str(i) for route, entries in inventory.items() for i, entry in enumerate(entries) if entry['classification'] == 'engine'}
    assert {name.replace('.mdx:', ':') for name in classified} == tested, 'snippet inventory: engine fence without compiler/schema fixture'
    print(f'PASS inventory: {len(inventory)} pages; {sum(map(len, inventory.values()))} classified fences; capture consistency across {consistent_pages} pages')
    test_python_snippets(pages)
    print(f'PASS public extraction: {len(manifest)} MDX pages; {len(fixture["snippets"])} snippets; '
          f'{len(fixture["cases"])} prepared evaluator cases; captured plan parity')
    if args.source is None:
        print('SKIP real engine compiler/schema/evaluator/simulation/gates: supply --source; public checks are not engine validation')
    else:
        run_engine(args.source,fixture,manifest)


if __name__=='__main__':
    main()
