#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import statistics
from collections import defaultdict

from common import TZ, load_json, save_json
import build_decision_scores as bds
import build_decision_engine_v2 as de2

ALL_DIMS = ('cycle','growth_persistence','domestic_demand','financial_conditions','ai_concentration')
DIRECTIONAL = ('growth_persistence','domestic_demand','financial_conditions')
HORIZONS = (3,6,12)

SOURCE_STATUS_SCORE = {
    'ok': 100.0,
    'degraded': 70.0,
    'blocked': 0.0,
    'missing': 50.0,
    'unknown': 50.0,
}
SOURCE_TOKEN_MAP = {
    'MOEA': 'moea',
    'Customs': 'decision',
    'DGBAS': 'decision_supplements',
    'DGBAS/MOL': 'decision_supplements',
    'CBC': 'decision',
    'NDC/CBC': 'decision',
    'FSC/NCCC': 'decision',
    'MOF': 'ai_concentration_inputs',
    'NDC': 'ndc',
}
CYCLE_COMPONENT_SOURCE = {
    'manufacturing_yoy': 'moea',
    'breadth': 'moea',
    'sales_yoy': 'moea',
    'leading_3m': 'ndc',
    'pmi': 'ndc',
    'policy_score': 'ndc',
}


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(v)))


def month_shift(period, delta):
    return de2.month_shift(period, delta)


def month_lag(newer, older):
    try:
        y1,m1=map(int,str(newer).split('-')); y0,m0=map(int,str(older).split('-'))
    except Exception:
        return None
    return max(0,(y1-y0)*12+(m1-m0))


def finite(v):
    try:
        return math.isfinite(float(v))
    except Exception:
        return False


def pearson(xs, ys):
    pairs=[(float(x),float(y)) for x,y in zip(xs,ys) if finite(x) and finite(y)]
    if len(pairs)<3:
        return None
    mx=sum(x for x,_ in pairs)/len(pairs); my=sum(y for _,y in pairs)/len(pairs)
    dx=[x-mx for x,_ in pairs]; dy=[y-my for _,y in pairs]
    den=math.sqrt(sum(x*x for x in dx)*sum(y*y for y in dy))
    return None if den<=1e-12 else sum(x*y for x,y in zip(dx,dy))/den


def weighted_geometric(values):
    usable=[(clamp(v),float(w)) for v,w in values if v is not None and float(w)>0]
    if not usable:
        return None
    if any(v<=0 for v,_ in usable):
        return 0.0
    den=sum(w for _,w in usable)
    return 100.0*math.exp(sum(w*math.log(v/100.0) for v,w in usable)/den)


def parse_iso(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except Exception:
        return None


def source_score(source_id, status):
    row=(status.get('sources') or {}).get(source_id)
    if not row:
        return SOURCE_STATUS_SCORE['missing']
    return SOURCE_STATUS_SCORE.get(str(row.get('status','unknown')).lower(), SOURCE_STATUS_SCORE['unknown'])


def source_for_component(dim, part):
    key=str(part.get('key') or '')
    if dim=='cycle':
        return CYCLE_COMPONENT_SOURCE.get(key,'unknown')
    if dim=='growth_persistence' and key=='inventory_balance':
        return 'inventory_manufacturing'
    src=str(part.get('source') or '')
    if src in SOURCE_TOKEN_MAP:
        return SOURCE_TOKEN_MAP[src]
    for token,sid in SOURCE_TOKEN_MAP.items():
        if token in src:
            return sid
    return 'unknown'


def current_dimensions():
    decisions=load_json('decision_scores.json', {'current':{}})
    summary=load_json('summary.json', {})
    current=dict(decisions.get('current') or {})
    cyc=summary.get('cycle') or {}
    if cyc:
        current['cycle']={
            'period':cyc.get('as_of'),'score':cyc.get('score'),'label':cyc.get('label'),
            'confidence':(summary.get('confidence') or {}).get('score'),
            'components':cyc.get('components') or [],
        }
    return current


def histories():
    decisions=load_json('decision_scores.json', {'history':{}})
    intel=load_json('intelligence_history.json', {'cycle_history':[]})
    out={'cycle':intel.get('cycle_history') or []}
    for key in ('growth_persistence','domestic_demand','financial_conditions','ai_concentration'):
        out[key]=(decisions.get('history') or {}).get(key) or []
    return out


def vintage_evidence_maturity(now=None):
    now=now or dt.datetime.now(TZ)
    manifest=load_json('vintage_manifest.json', {})
    revisions=load_json('revisions.json', {})
    first=parse_iso(manifest.get('first_observed_at'))
    days=0.0 if not first else max(0.0,(now-first.astimezone(TZ)).total_seconds()/86400.0)
    maturity=60.0+40.0*min(1.0,days/180.0)
    rev_hist=revisions.get('history') or []
    revision_observations=int(manifest.get('revision_observations') or 0)
    revision_events=max(revision_observations,len(rev_hist))
    if revision_events:
        maturity*=max(0.65,1.0-min(0.35,revision_events/100.0))
    return {
        'score':round(clamp(maturity),1),
        'prospective_days':round(days,1),
        'first_observed_at':manifest.get('first_observed_at'),
        'revision_observations':revision_observations,
        'revision_events_recorded':len(rev_hist),
        'maturity_target_days':180,
        'note':'Evidence-maturity factor, not a claim that official data never revise. No prospective history means confidence cannot start at 100.',
    }


def freshness_score(cur):
    parts=cur.get('components') or []
    base=cur.get('period')
    if not parts or not base:
        return None
    den=sum(float(p.get('weight',0)) for p in parts)
    if den<=0:
        return None
    penalty=0.0
    for part in parts:
        lag=month_lag(base,part.get('period'))
        if lag is None: lag=6
        penalty+=float(part.get('weight',0))*min(100.0,lag*15.0)
    return round(clamp(100.0-penalty/den),1)


def source_reliability(dim,cur,status):
    parts=cur.get('components') or []
    if not parts:
        return None,[]
    den=sum(float(p.get('weight',0)) for p in parts)
    if den<=0:
        return None,[]
    rows=[]; total=0.0
    for p in parts:
        sid=source_for_component(dim,p)
        value=source_score(sid,status)
        w=float(p.get('weight',0))
        total+=w*value
        rows.append({'component':p.get('key'),'source_id':sid,'status':((status.get('sources') or {}).get(sid) or {}).get('status','missing'),'score':round(value,1),'weight':w})
    return round(total/den,1),rows


def data_confidence_v2():
    current=current_dimensions()
    status=load_json('status.json', {'sources':{}})
    rev=vintage_evidence_maturity()
    out={}
    for dim in ALL_DIMS:
        cur=current.get(dim) or {}
        completeness=float(cur.get('confidence') or 0)
        fresh=freshness_score(cur)
        src,src_rows=source_reliability(dim,cur,status)
        effective=weighted_geometric([
            (completeness,.30),(fresh,.25),(src,.25),(rev['score'],.20)
        ])
        out[dim]={
            'period':cur.get('period'),
            'score':cur.get('score'),
            'completeness':round(completeness,1),
            'freshness':fresh,
            'source_reliability':src,
            'revision_evidence_maturity':rev['score'],
            'effective_data_confidence':None if effective is None else round(effective,1),
            'source_components':src_rows,
        }
    vals=[x['effective_data_confidence'] for x in out.values() if x.get('effective_data_confidence') is not None]
    return {
        'method':'weighted geometric confidence; completeness 30%, freshness 25%, source reliability 25%, revision-evidence maturity 20%',
        'dimensions':out,
        'overall':None if not vals else round(sum(vals)/len(vals),1),
        'revision_evidence':rev,
        'authority':False,
        'note':'This is evidence confidence, not probability that a Score is correct and not a return forecast.',
    }


def median_mad(values):
    vals=[float(v) for v in values if finite(v)]
    if not vals:
        return None,None
    med=statistics.median(vals)
    mad=statistics.median([abs(x-med) for x in vals])
    return med,mad


def corr_matrix(rows, dims):
    matrix={}
    for i,a in enumerate(dims):
        for b in dims[i+1:]:
            xs=[];ys=[]
            for row in rows:
                if a in row and b in row:
                    xs.append(row[a]);ys.append(row[b])
            r=pearson(xs,ys)
            if r is not None:
                matrix[f'{a}|{b}']=r
    return matrix


def structural_break_monitor():
    hs=histories(); cur=current_dimensions()
    maps={k:de2.as_map(hs.get(k,[])) for k in ALL_DIMS}
    if not all(maps.values()):
        return {'status':'BLOCKED_INSUFFICIENT_HISTORY','authority':False}
    periods=sorted(set.intersection(*(set(m) for m in maps.values())))
    if len(periods)<36:
        return {'status':'BLOCKED_INSUFFICIENT_HISTORY','authority':False,'months':len(periods)}
    states=[{'period':p,**{k:maps[k][p] for k in ALL_DIMS}} for p in periods]
    hist_states=states[:-1] if len(states)>1 else states
    lookback=hist_states[-60:]
    robust={}
    z_abs=[]
    for dim in ALL_DIMS:
        current_score=(cur.get(dim) or {}).get('score')
        vals=[x[dim] for x in lookback]
        med,mad=median_mad(vals)
        if current_score is None or med is None:
            continue
        if mad is None or mad<=1e-9:
            z=0.0 if abs(float(current_score)-med)<=1e-9 else 6.0
        else:
            z=0.6745*(float(current_score)-med)/mad
        robust[dim]={'current':round(float(current_score),2),'median_60m':round(med,2),'mad_60m':round(mad or 0.0,2),'robust_z':round(z,2)}
        z_abs.append(min(6.0,abs(z)))
    mean_abs_z=sum(z_abs)/len(z_abs) if z_abs else 6.0
    distribution_similarity=clamp(math.exp(-mean_abs_z/3.0)*100.0)

    recent=states[-24:]
    prior=states[-84:-24] if len(states)>=84 else states[:-24]
    rc=corr_matrix(recent,ALL_DIMS); pc=corr_matrix(prior,ALL_DIMS)
    common=sorted(set(rc)&set(pc))
    corr_deltas={k:abs(rc[k]-pc[k]) for k in common}
    mean_corr_delta=sum(corr_deltas.values())/len(corr_deltas) if corr_deltas else None
    correlation_drift=None if mean_corr_delta is None else clamp(mean_corr_delta*100.0)

    regime=de2.regime_similarity(hs,cur)
    nearest=float(regime.get('similarity') or 0.0)
    high=nearest<45 or distribution_similarity<40 or (correlation_drift is not None and correlation_drift>55)
    watch=nearest<65 or distribution_similarity<60 or (correlation_drift is not None and correlation_drift>30)
    status='HIGH' if high else 'WATCH' if watch else 'NORMAL'
    reasons=[]
    if nearest<65: reasons.append(f'historical-neighbor similarity {nearest:.1f}')
    if distribution_similarity<60: reasons.append(f'distribution similarity {distribution_similarity:.1f}')
    if correlation_drift is not None and correlation_drift>30: reasons.append(f'correlation drift {correlation_drift:.1f}')
    return {
        'status':status,
        'authority':False,
        'nearest_regime_similarity':round(nearest,1),
        'distribution_similarity':round(distribution_similarity,1),
        'mean_abs_robust_z':round(mean_abs_z,2),
        'correlation_drift_score':None if correlation_drift is None else round(correlation_drift,1),
        'recent_window_months':len(recent),
        'prior_window_months':len(prior),
        'robust_dimension_state':robust,
        'pairwise_correlation_delta':{k:round(v,3) for k,v in sorted(corr_deltas.items())},
        'reasons':reasons or ['No predeclared structural-break threshold breached.'],
        'contract':'Diagnostic novelty/drift monitor only. It may lower reviewed confidence but cannot rewrite Scores or actions.',
    }


def cycle_map():
    return de2.as_map(histories().get('cycle',[]))


def future_cycle_metrics(score_rows,horizon):
    sig=de2.as_map(score_rows); cyc=cycle_map()
    rows=[]
    for p,s in sig.items():
        q=month_shift(p,horizon)
        if q in cyc:
            rows.append((s,cyc[q]))
    r=pearson([x[0] for x in rows],[x[1] for x in rows])
    return {'samples':len(rows),'pearson_to_future_cycle':None if r is None else round(r,3)}


def equal_weight_scores():
    industry=load_json('industry.json', {})
    ndcobj=load_json('ndc.json', {})
    inputs=load_json('decision_inputs.json', {'series':{}})
    ndc=ndcobj.get('series',{})
    prod=industry.get('datasets',{}).get('moea.industry.production',{}).get('series',{}).get('C',{})
    sales=industry.get('datasets',{}).get('moea.manufacturing.sales_index_current',{}).get('series',{}).get('C',{})
    current_period=bds.latest_period(prod) or ndcobj.get('latest_period')
    allseries=[prod,sales,*ndc.values(),*inputs.get('series',{}).values()]
    periods=[p for p in bds.history_periods(allseries,120) if not current_period or p<=current_period]
    original=copy.deepcopy(bds.WEIGHTS)
    try:
        for group in ('growth','domestic','financial'):
            keys=list(bds.WEIGHTS[group])
            bds.WEIGHTS[group]={k:1.0/len(keys) for k in keys}
        fns={
            'growth_persistence':lambda p:bds.growth_score(p,prod,sales,ndc,inputs),
            'domestic_demand':lambda p:bds.domestic_score(p,ndc,inputs),
            'financial_conditions':lambda p:bds.financial_score(p,ndc,inputs),
        }
        out={}
        for dim,fn in fns.items():
            cur=fn(current_period)
            hist=[]
            for p in periods:
                r=fn(p)
                if r: hist.append({k:r[k] for k in ('period','score','label','confidence')})
            out[dim]={'current':cur,'history':hist}
        return out
    finally:
        bds.WEIGHTS.clear(); bds.WEIGHTS.update(original)


def score_challenger_benchmark():
    champion=load_json('decision_scores.json', {'current':{},'history':{}})
    challenger=equal_weight_scores()
    out={}
    for dim in DIRECTIONAL:
        ch_cur=(champion.get('current') or {}).get(dim) or {}
        eq_cur=(challenger.get(dim) or {}).get('current') or {}
        horizons={}
        improvements=[]
        no_bad=True
        for h in (3,6):
            cm=future_cycle_metrics((champion.get('history') or {}).get(dim,[]),h)
            em=future_cycle_metrics((challenger.get(dim) or {}).get('history',[]),h)
            c=cm.get('pearson_to_future_cycle'); e=em.get('pearson_to_future_cycle')
            imp=None if c is None or e is None else e-c
            if imp is not None:
                improvements.append(imp)
                if imp < -0.02: no_bad=False
            horizons[f'{h}m']={'champion':cm,'equal_weight_challenger':em,'correlation_improvement':None if imp is None else round(imp,3)}
        avg=None if not improvements else sum(improvements)/len(improvements)
        worth=avg is not None and avg>=0.05 and no_bad and len(improvements)==2
        out[dim]={
            'champion_current_score':ch_cur.get('score'),
            'equal_weight_current_score':eq_cur.get('score'),
            'current_score_delta':None if ch_cur.get('score') is None or eq_cur.get('score') is None else round(float(eq_cur['score'])-float(ch_cur['score']),2),
            'horizons':horizons,
            'average_correlation_improvement':None if avg is None else round(avg,3),
            'status':'CHALLENGER_WORTH_REVIEW' if worth else 'CHAMPION_RETAINS',
            'automatic_promotion':False,
        }
    return {
        'method':'Production transforms/components held fixed; only compare hand-set production weights with a predeclared equal-weight baseline.',
        'dimensions':out,
        'excluded':{
            'cycle':'Cycle has a different production construction; no like-for-like equal-weight challenger is declared here.',
            'ai_concentration':'Concentration semantics differ from directional health Scores; no automatic equal-weight benchmark.',
        },
        'authority':False,
    }


def market_series():
    ndc=load_json('ndc.json',{}).get('series',{})
    return de2.series_map(ndc.get('stock_index'))


def market_live_state():
    live=load_json('market_live.json',{})
    s=((live.get('series') or {}).get('twse.taiex_month_end') or {})
    data=s.get('data') or []
    return {'period':data[-1][0] if data else live.get('latest_period'),'value':data[-1][1] if data else None}


def v2_current_forecasts():
    obj=load_json('decision_engine_v2.json',{})
    out={}
    for dim in ALL_DIMS:
        hs=((obj.get('walk_forward_oos') or {}).get(dim) or {}).get('horizons') or {}
        out[dim]={h:((hs.get(h) or {}).get('current') or {}).get('probability') for h in ('3m','6m','12m')}
    return out


def validation_snapshot():
    cur=current_dimensions()
    mkt=market_live_state()
    v1=load_json('risk_budget.json',{})
    v2=load_json('risk_budget_v2.json',{})
    investment=load_json('investment.json',{})
    researched=(investment.get('selection') or {}).get('researched') or []
    return {
        'recorded_at':dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'known_latest_score_periods':{k:(cur.get(k) or {}).get('period') for k in ALL_DIMS},
        'scores':{k:{'period':(cur.get(k) or {}).get('period'),'score':(cur.get(k) or {}).get('score')} for k in ALL_DIMS},
        'forecast_probabilities':v2_current_forecasts(),
        'market':mkt,
        'risk':{
            'v1_equity_pct':(v1.get('allocation_guardrails') or {}).get('target_equity_risk_budget_pct'),
            'v2_equity_pct':((v2.get('current') or {}).get('allocation_envelope') or {}).get('equity_risk_budget_review_pct'),
        },
        'alpha':[
            {'ticker':str(x.get('ticker')),'action':x.get('action'),'reference_price':x.get('reference_price'),'reference_price_date':x.get('reference_price_date')}
            for x in researched if x.get('ticker')
        ],
    }


def snapshot_fingerprint(snap):
    stable={
        'scores':snap.get('scores'),'forecast_probabilities':snap.get('forecast_probabilities'),
        'market':snap.get('market'),'risk':snap.get('risk'),'alpha':snap.get('alpha'),
    }
    return hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]


def macro_scorecard(entries,hs):
    maps={k:de2.as_map(hs.get(k,[])) for k in ALL_DIMS}
    rows={k:[] for k in ALL_DIMS}
    for e in entries:
        known=e.get('known_latest_score_periods') or {}
        scores=e.get('scores') or {}; fc=e.get('forecast_probabilities') or {}
        for dim in ALL_DIMS:
            base=(scores.get(dim) or {}).get('period')
            if not base: continue
            for h in HORIZONS:
                q=month_shift(base,h)
                if not q or (known.get(dim) and q<=known[dim]):
                    continue
                actual=maps.get(dim,{}).get(q)
                prob=(fc.get(dim) or {}).get(f'{h}m')
                if actual is None or prob is None:
                    continue
                y=1.0 if de2.target_positive(dim,actual) else 0.0
                rows[dim].append({'horizon_months':h,'probability':float(prob),'actual':y,'brier':(float(prob)-y)**2,'correct':(float(prob)>=.5)==bool(y)})
    dims={}
    for dim,vals in rows.items():
        dims[dim]={
            'resolved':len(vals),
            'direction_hit_rate':None if not vals else round(sum(x['correct'] for x in vals)/len(vals),4),
            'brier_score':None if not vals else round(sum(x['brier'] for x in vals)/len(vals),4),
        }
    return {'dimensions':dims,'resolved_total':sum(x['resolved'] for x in dims.values())}


def risk_portfolio_scorecard(entries):
    stock=market_series()
    rows=[]
    for e in entries:
        p=(e.get('market') or {}).get('period')
        if not p: continue
        risk=e.get('risk') or {}
        for h in HORIZONS:
            q=month_shift(p,h)
            ret=de2.percent_change(stock,p,q)
            dd=de2.forward_drawdown(stock,p,h)
            if ret is None or dd is None: continue
            v1=risk.get('v1_equity_pct'); v2=risk.get('v2_equity_pct')
            if v1 is None or v2 is None: continue
            rows.append({
                'horizon_months':h,'market_return_pct':ret,'market_drawdown_pct':dd,
                'v1_return_pct':ret*float(v1)/100.0,'v2_return_pct':ret*float(v2)/100.0,'static60_return_pct':ret*.60,
                'v1_equity_pct':v1,'v2_equity_pct':v2,
            })
    def aggregate(key):
        vals=[x[key] for x in rows]
        return None if not vals else round(sum(vals)/len(vals),2)
    riskcard={
        'resolved':len(rows),
        'mean_market_drawdown_pct':aggregate('market_drawdown_pct'),
        'mean_v1_equity_pct':aggregate('v1_equity_pct'),
        'mean_v2_equity_pct':aggregate('v2_equity_pct'),
    }
    portfolio={
        'resolved':len(rows),
        'mean_v1_scaled_return_pct':aggregate('v1_return_pct'),
        'mean_v2_scaled_return_pct':aggregate('v2_return_pct'),
        'mean_static60_return_pct':aggregate('static60_return_pct'),
        'scope':'Aggregate equity envelope only; user private holdings are not stored or scored here.',
    }
    return riskcard,portfolio


def alpha_scorecard(entries):
    by_action=defaultdict(list)
    resolved=0
    stock=market_series()
    for i,e in enumerate(entries):
        base_period=(e.get('market') or {}).get('period')
        if not base_period: continue
        for row in e.get('alpha') or []:
            p0=row.get('reference_price'); ticker=row.get('ticker')
            if p0 in (None,0) or not ticker: continue
            for later in entries[i+1:]:
                later_period=(later.get('market') or {}).get('period')
                if not later_period or month_lag(later_period,base_period)<3:
                    continue
                match=next((x for x in later.get('alpha') or [] if str(x.get('ticker'))==str(ticker) and x.get('reference_price') not in (None,0)),None)
                if not match: continue
                ret=(float(match['reference_price'])/float(p0)-1.0)*100.0
                market=de2.percent_change(stock,base_period,later_period)
                rel=None if market is None else ret-market
                by_action[str(row.get('action') or 'UNKNOWN')].append((ret,rel))
                resolved+=1
                break
    out={}
    for action,vals in sorted(by_action.items()):
        rels=[r for _,r in vals if r is not None]
        out[action]={
            'resolved':len(vals),
            'mean_return_pct':round(sum(r for r,_ in vals)/len(vals),2),
            'mean_relative_to_market_pct':None if not rels else round(sum(rels)/len(rels),2),
        }
    return {'resolved_total':resolved,'by_action':out,'minimum_followup_months':3}


def build_validation_journal(append=True):
    obj=load_json('validation_journal.json',{'version':1,'entries':[]})
    entries=obj.get('entries') or []
    if append:
        snap=validation_snapshot(); fp=snapshot_fingerprint(snap); snap['id']=fp; snap['fingerprint']=fp
        if not entries or entries[-1].get('fingerprint')!=fp:
            entries.append(snap)
    entries=entries[-300:]
    hs=histories()
    macro=macro_scorecard(entries,hs)
    risk,portfolio=risk_portfolio_scorecard(entries)
    alpha=alpha_scorecard(entries)
    obj={
        'version':1,
        'updated_at':dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'contract':'prospective-only validation snapshots; no historical backfill before snapshot recording',
        'entries':entries,
        'scorecards':{
            'macro':macro,'risk':risk,'portfolio':portfolio,'alpha':alpha,
            'resolved_total':macro['resolved_total']+risk['resolved']+portfolio['resolved']+alpha['resolved_total'],
        },
    }
    save_json('validation_journal.json',obj)
    return obj


def generate(append_journal=True):
    data_conf=data_confidence_v2()
    structural=structural_break_monitor()
    challengers=score_challenger_benchmark()
    journal=build_validation_journal(append=append_journal)
    out={
        'version':1,
        'generated_at':dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
        'product':'Elephant Validation OS v1',
        'authority':False,
        'contract':{
            'production_scores_unchanged':True,
            'v1_decision_engine_remains_authoritative':True,
            'risk_budget_v2_remains_challenger':True,
            'cannot_change_capital_os':True,
            'cannot_change_alpha_or_constitution':True,
            'no_automatic_promotion':True,
            'no_automatic_trading':True,
        },
        'data_confidence_v2':data_conf,
        'structural_break_monitor':structural,
        'score_challengers':challengers,
        'prospective_scorecards':journal.get('scorecards') or {},
        'evidence_boundary':{
            'reconstructed_history':'Historical score rows before vintage collection remain revised-series reconstructions.',
            'revision_evidence':'Revision stability starts conservative and matures only through prospective vintages.',
            'score_challenger':'Equal-weight baseline changes weights only in-memory and restores production weights before returning.',
            'prospective_journal':'No outcome is counted if it was already known when the validation snapshot was recorded.',
        },
    }
    save_json('validation_os.json',out)
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--no-journal',action='store_true')
    a=ap.parse_args()
    generate(append_journal=not a.no_journal)


if __name__=='__main__':
    main()
