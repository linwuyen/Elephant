#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, hashlib, json, math
from common import DATA, TZ, save_json
import valuation_router


def load(name, default=None):
    p=DATA/name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else ({} if default is None else default)
def finite(v): return isinstance(v,(int,float)) and math.isfinite(float(v))
def ret(fv,price): return None if not finite(fv) or not finite(price) or float(price)<=0 else (float(fv)/float(price)-1)*100
def archetype(row): return valuation_router.classify(row)

def distribution(stock,hurdle):
    vm=stock.get('valuation_model',{}); price=stock.get('reference_price'); rows=[]; ps=weighted=beat=loss20=0.; neg=[]
    for key in ('bear','base','bull'):
        sc=(vm.get('scenarios') or {}).get(key,{})
        p=sc.get('probability'); r=ret(sc.get('fair_value'),price)
        if not finite(p) or r is None: continue
        p=float(p); ps+=p; weighted+=p*r
        if hurdle is not None and r>hurdle: beat+=p
        if r<=-20: loss20+=p
        if r<0: neg.append((p,r))
        rows.append({'scenario':key,'probability':p,'return_pct':round(r,2),'fair_value':sc.get('fair_value')})
    if ps<=0: return {'status':'INCOMPLETE','scenarios':rows,'expected_return_pct':vm.get('expected_return_pct'),'probability_beating_hurdle_pct':None,'probability_loss_gt_20_pct':None,'expected_shortfall_pct':None}
    negp=sum(p for p,_ in neg)
    return {'status':'COMPLETE' if len(rows)==3 and abs(ps-1)<=.02 else 'PARTIAL','scenarios':rows,'expected_return_pct':round(weighted/ps,2),'probability_beating_hurdle_pct':None if hurdle is None else round(beat/ps*100,1),'probability_loss_gt_20_pct':round(loss20/ps*100,1),'expected_shortfall_pct':round(sum(p*r for p,r in neg)/negp,2) if negp else 0.0}

def opportunity(alpha,inputs,portfolio):
    b=alpha.get('benchmark_asset',{}).get('valuation_model',{}); out=[]
    for src in inputs.get('alternatives',[]):
        x=dict(src); iid=x.get('id')
        if iid=='2330': x.update(expected_return_pct=b.get('expected_return_pct'),status='AVAILABLE' if finite(b.get('expected_return_pct')) else 'UNAVAILABLE',source='ALPHA_ENGINE')
        elif iid=='DEBT_REPAYMENT':
            r=portfolio.get('debt_effective_rate_pct') if portfolio.get('status')=='COMPLETE' else None
            x.update(expected_return_pct=r if finite(r) else None,status='AVAILABLE' if finite(r) else 'UNAVAILABLE',source='PORTFOLIO_STATE')
        elif finite(x.get('expected_return_pct')): x['status']='AVAILABLE'
        else: x['status']='UNAVAILABLE'; x['expected_return_pct']=None
        out.append(x)
    av=[x for x in out if x.get('status')=='AVAILABLE' and finite(x.get('expected_return_pct'))]
    h=max((float(x['expected_return_pct']) for x in av),default=None); leader=next((x for x in av if h is not None and float(x['expected_return_pct'])==h),None)
    return {'status':'COMPLETE' if len(av)>=3 else 'PARTIAL','alternatives':out,'available_count':len(av),'hurdle_expected_return_pct':h,'hurdle_asset':leader.get('id') if leader else None,'note':'Only AVAILABLE alternatives form the hurdle; unavailable alternatives remain null.'}

def research_queue(screen,alpha):
    done={str(x.get('ticker')) for x in alpha.get('stocks',[])}; rows=[]
    for r in screen.get('deep_research_queue',[]) or []:
        t=str(r.get('ticker')); rows.append({'ticker':t,'name':r.get('name'),'market':r.get('market'),'rank':r.get('rank'),'screen_priority':r.get('screen_priority'),'reference_price':r.get('reference_price'),'archetype':archetype(r),'already_researched':t in done,'status':'REFRESH' if t in done else 'NEW_RESEARCH','required_evidence':['reference_price','earnings_basis','revenue_trend','balance_sheet_cash_flow','material_events','valuation_basis','24_36m_eps_or_fcf_path','structured_catalyst','survival_basis','quarterly_falsification_metrics'],'promotion_authority':'NONE','next_action':'collect first-party evidence → valuation route → Investment Constitution → upstream Alpha Buy Gate'})
    return {'status':'COMPLETE' if screen.get('meta',{}).get('status')=='COMPLETE' else 'DEGRADED','as_of':screen.get('meta',{}).get('as_of'),'items':rows,'new_research_count':sum(x['status']=='NEW_RESEARCH' for x in rows),'guardrail':'Research queue cannot create BUY CANDIDATE or pass the Constitution without structured evidence.'}

def weights(portfolio):
    if portfolio.get('status')!='COMPLETE' or not finite(portfolio.get('investable_assets_twd')) or portfolio['investable_assets_twd']<=0:return {}
    total=float(portfolio['investable_assets_twd']); w={}
    for p in portfolio.get('positions',[]):
        if p.get('ticker') and finite(p.get('market_value_twd')): w[str(p['ticker'])]=float(p['market_value_twd'])/total*100
    if finite(portfolio.get('cash_twd')): w['CASH']=float(portfolio['cash_twd'])/total*100
    return w

def lifecycle(alpha,opp,policy,portfolio,friction,constitution):
    h=opp.get('hurdle_expected_return_pct'); w=weights(portfolio); lc=policy.get('lifecycle',{}); out=[]
    for s in alpha.get('stocks',[]):
        t=str(s.get('ticker')); c=constitution.get(t,{}); cs=c.get('constitution_status','BLOCKED')
        er=s.get('valuation_model',{}).get('expected_return_pct'); na=float(er)-float(h)-float(friction) if all(finite(x) for x in (er,h,friction)) else None
        up=s.get('action'); cw=w.get(t); act='RESEARCH'; reason='Upstream action is not BUY; portfolio layer cannot upgrade it.'
        if s.get('thesis_status')=='INVALIDATED': act,reason='EXIT_REVIEW','Thesis invalidated.'
        elif up=='BUY CANDIDATE':
            if cs!='PASS': act,reason='CONSTITUTION_BLOCK',f'Upstream BUY is blocked because Investment Constitution is {cs}.'
            elif na is None: act,reason='HOLD_REVIEW','Opportunity hurdle incomplete.'
            elif na<=float(lc.get('exit_when_net_alpha_spread_below_pct',-5)): act,reason='EXIT_REVIEW','Net alpha is materially below opportunity hurdle.'
            elif na<=float(lc.get('trim_when_net_alpha_spread_below_pct',2)): act,reason='TRIM_REVIEW','Net alpha edge compressed.'
            elif cw is None: act,reason='BUY_REVIEW','Upstream BUY and Investment Constitution both pass; sizing requires current portfolio state.'
            else: act,reason='ADD_REVIEW','Upstream BUY and Investment Constitution both pass and position exists.'
        elif cw is not None: act,reason='HOLD_REVIEW','Held position is not an upstream BUY; review thesis and opportunity cost.'
        out.append({'ticker':s.get('ticker'),'name':s.get('name'),'upstream_action':up,'constitution_status':cs,'constitution_capital_eligible':bool(c.get('capital_eligible')),'portfolio_action':act,'expected_return_pct':er,'hurdle_expected_return_pct':h,'net_alpha_spread_pct':None if na is None else round(na,2),'current_weight_pct':None if cw is None else round(cw,2),'reason':reason})
    return out

def risk(alpha,portfolio,policy):
    w=weights(portfolio)
    if portfolio.get('status')!='COMPLETE': return {'status':'UNCONFIGURED','personalized':False,'violations':[],'stress_tests':[],'note':'No personalized risk output until portfolio_state is COMPLETE.'}
    stocks={str(x.get('ticker')):x for x in alpha.get('stocks',[])}; c=policy.get('constraints',{}); violations=[]; factors={}
    for t,x in w.items():
        if t=='CASH':continue
        if x>c.get('max_single_stock_pct',25): violations.append({'type':'SINGLE_STOCK','ticker':t,'weight_pct':round(x,2),'limit_pct':c.get('max_single_stock_pct',25)})
        f=archetype(stocks.get(t,{})); factors[f]=factors.get(f,0)+x
    for f,x in factors.items():
        if x>c.get('max_common_factor_pct',60): violations.append({'type':'COMMON_FACTOR','factor':f,'weight_pct':round(x,2),'limit_pct':c.get('max_common_factor_pct',60)})
    assets=float(portfolio.get('investable_assets_twd') or 0); debt=float(portfolio.get('debt_twd') or 0); dr=debt/assets*100 if assets else None
    if dr is not None and dr>c.get('max_net_debt_to_investable_assets_pct',25): violations.append({'type':'LEVERAGE','value_pct':round(dr,2),'limit_pct':c.get('max_net_debt_to_investable_assets_pct',25)})
    eq=sum(x for t,x in w.items() if t!='CASH'); stress=[]
    for shock in (-20,-35,-50):
        impact=eq/100*shock; post=assets*(1+impact/100); stress.append({'market_shock_pct':shock,'portfolio_impact_pct':round(impact,2),'post_shock_debt_ratio_pct':round(debt/post*100,2) if post>0 else None})
    return {'status':'REVIEW' if violations else 'PASS','personalized':True,'weights_pct':{k:round(v,2) for k,v in w.items()},'common_factor_exposure_pct':{k:round(v,2) for k,v in factors.items()},'debt_to_investable_assets_pct':None if dr is None else round(dr,2),'violations':violations,'stress_tests':stress}

def sizing(alpha,opp,policy,portfolio,constitution):
    if portfolio.get('status')!='COMPLETE': return {'status':'UNCONFIGURED','targets':[],'note':'Configure portfolio_state before personalized sizing.'}
    h=opp.get('hurdle_expected_return_pct')
    if h is None:return {'status':'BLOCKED','targets':[],'note':'Opportunity hurdle unavailable.'}
    rows=[]
    for s in alpha.get('stocks',[]):
        t=str(s.get('ticker')); c=constitution.get(t,{})
        if s.get('action')!='BUY CANDIDATE' or c.get('constitution_status')!='PASS':continue
        er=s.get('valuation_model',{}).get('expected_return_pct'); conf=s.get('confidence_score'); down=s.get('risk_model',{}).get('downside_pct'); d=distribution(s,h); beat=d.get('probability_beating_hurdle_pct')
        if all(finite(x) for x in (er,conf,down,beat)):
            raw=max(0,float(er)-float(h))*(float(conf)/100)*(float(beat)/100)/max(10,float(down))
            if raw>0:rows.append((s,raw,d))
    if not rows:return {'status':'NO_BUY','targets':[],'note':'No upstream BUY candidate also passes the six-rule Investment Constitution with complete sizing inputs.'}
    total=sum(x[1] for x in rows); w=weights(portfolio); cap=policy.get('constraints',{}); invest=policy.get('sizing',{}).get('normalize_to_investable_pct',85); targets=[]
    for s,raw,d in rows:
        cur=w.get(str(s.get('ticker')),0); maxw=cap.get('max_single_stock_pct',25) if cur>0 else min(cap.get('max_single_stock_pct',25),cap.get('max_new_position_pct',12)); target=min(maxw,raw/total*invest)
        targets.append({'ticker':s.get('ticker'),'name':s.get('name'),'target_weight_pct':round(target,2),'current_weight_pct':round(cur,2),'raw_score':round(raw,4),'probability_beating_hurdle_pct':d.get('probability_beating_hurdle_pct'),'constitution_status':'PASS'})
    return {'status':'COMPLETE','targets':targets,'cash_floor_pct':cap.get('cash_floor_pct')}
def fp(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def generate():
    now=dt.datetime.now(TZ).replace(microsecond=0); bundle=load('alpha_engine.json'); alpha=bundle.get('alpha',{}); screen=bundle.get('screen',{}); policy=load('portfolio_policy.json'); portfolio=load('portfolio_state.json'); inputs=load('opportunity_inputs.json'); friction=inputs.get('frictions',{}).get('round_trip_friction_pct',0)
    cres=load('investment_constitution_results.json',{}); cmap={str(x.get('ticker')):x for x in cres.get('securities',[])}
    opp=opportunity(alpha,inputs,portfolio); rq=research_queue(screen,alpha); lc=lifecycle(alpha,opp,policy,portfolio,friction,cmap); rk=risk(alpha,portfolio,policy); sz=sizing(alpha,opp,policy,portfolio,cmap); probs=[{'ticker':s.get('ticker'),'name':s.get('name'),'archetype':archetype(s),'valuation_model':s.get('valuation_model',{}).get('model_type'),'distribution':distribution(s,opp.get('hurdle_expected_return_pct'))} for s in alpha.get('stocks',[])]
    out={'version':2,'generated_at':now.isoformat(),'status':'COMPLETE' if alpha and screen and cres.get('status')=='COMPLETE' else 'DEGRADED','objective':policy.get('objective'),'investment_constitution':{'status':cres.get('status'),'pass_count':cres.get('pass_count'),'capital_eligible_count':cres.get('capital_eligible_count'),'authority':cres.get('authority')},'research_queue':rq,'opportunity_set':opp,'probabilistic_returns':probs,'lifecycle':lc,'portfolio_risk':rk,'target_sizing':sz,'portfolio_state_status':portfolio.get('status'),'guardrails':{'portfolio_cannot_upgrade_upstream_action':True,'constitution_required_for_new_capital':True,'constitution_cannot_create_upstream_buy':True,'unavailable_benchmarks_not_fabricated':True,'personalized_sizing_requires_complete_portfolio_state':True,'no_automatic_trading':True}}
    out['fingerprint']=fp({k:out[k] for k in ('investment_constitution','research_queue','opportunity_set','lifecycle','portfolio_risk','target_sizing')}); save_json('capital_allocation.json',out); save_json('deep_research_queue.json',rq); save_json('opportunity_set.json',opp); return out
if __name__=='__main__': print(json.dumps(generate(),ensure_ascii=False,indent=2))
