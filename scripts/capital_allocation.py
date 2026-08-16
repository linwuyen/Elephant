#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, hashlib, json, math
from common import DATA, TZ, save_json
import valuation_router

def load(name, default=None):
    p=DATA/name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else ({} if default is None else default)
def finite(v): return isinstance(v,(int,float)) and math.isfinite(float(v))
def annualize_return(total_return_pct,horizon_months):
    if not finite(total_return_pct) or not finite(horizon_months) or float(horizon_months)<=0:return None
    terminal=1.0+float(total_return_pct)/100.0
    if terminal<=0:return None
    return (terminal**(12.0/float(horizon_months))-1.0)*100.0
def net_terminal_return(total_return_pct,friction_pct):
    if not finite(total_return_pct):return None
    friction=max(0.0,float(friction_pct or 0))/100.0
    terminal=(1.0+float(total_return_pct)/100.0)*(1.0-friction)
    return (terminal-1.0)*100.0 if terminal>0 else None
def standardized_return(total_return_pct,horizon_months,friction_pct=0):
    net=net_terminal_return(total_return_pct,friction_pct)
    return annualize_return(net,horizon_months)
def ret(fv,price): return None if not finite(fv) or not finite(price) or float(price)<=0 else (float(fv)/float(price)-1)*100
def archetype(row): return valuation_router.classify(row)

def return_contract(registry):
    c=registry.get('return_comparison') or {}
    return {'basis':c.get('comparison_basis','ANNUALIZED_NOMINAL_PRE_TAX_AFTER_PUBLIC_FRICTION'),
            'security_horizon_months':float(c.get('upstream_security_native_horizon_months',15)),
            'friction_treatment':c.get('friction_treatment')}

def security_return(stock,registry,friction):
    c=return_contract(registry);native=(stock.get('valuation_model') or {}).get('expected_return_pct');h=c['security_horizon_months']
    annual=standardized_return(native,h,friction)
    return {'native_expected_return_pct':native,'native_horizon_months':h,
            'annualized_expected_return_pct':None if annual is None else round(annual,2),
            'expected_return_pct':None if annual is None else round(annual,2),'return_basis':c['basis']}

def probability_provenance(ticker,cal):
    row=next((x for x in cal.get('securities',[]) if str(x.get('ticker'))==str(ticker)),{})
    return {'source':'UPSTREAM_SCENARIO_MODEL','method':'MODEL_ASSUMPTION_UNTIL_PROSPECTIVE_CALIBRATION',
            'calibration_status':row.get('calibration_status','UNAVAILABLE'),
            'resolved_samples':row.get('resolved_samples',cal.get('resolved_samples',0)),
            'minimum_samples':row.get('minimum_samples',cal.get('minimum_samples',30)),
            'empirical_override':bool(row.get('authoritative',False))}

def distribution(stock,hurdle,registry,friction,scenario_cal):
    vm=stock.get('valuation_model',{}); price=stock.get('reference_price');rows=[];ps=weighted=beat=loss20=0.;neg=[]
    h=return_contract(registry)['security_horizon_months'];prov=probability_provenance(stock.get('ticker'),scenario_cal)
    for key in ('bear','base','bull'):
        sc=(vm.get('scenarios') or {}).get(key,{})
        p=sc.get('probability'); native=ret(sc.get('fair_value'),price); ar=standardized_return(native,h,friction) if native is not None else None
        if not finite(p) or ar is None: continue
        p=float(p);ps+=p;weighted+=p*ar
        if hurdle is not None and ar>hurdle:beat+=p
        if ar<=-20:loss20+=p
        if ar<0:neg.append((p,ar))
        rows.append({'scenario':key,'probability':p,'probability_source':prov['method'],
                     'native_return_pct':round(native,2),'annualized_return_pct':round(ar,2),'fair_value':sc.get('fair_value')})
    if ps<=0:return {'status':'INCOMPLETE','scenarios':rows,'expected_return_pct':None,'probability_beating_hurdle_pct':None,'probability_loss_gt_20_pct':None,'expected_shortfall_pct':None,'probability_provenance':prov}
    negp=sum(p for p,_ in neg)
    return {'status':'COMPLETE' if len(rows)==3 and abs(ps-1)<=.02 else 'PARTIAL','scenarios':rows,
            'expected_return_pct':round(weighted/ps,2),'annualized_expected_return_pct':round(weighted/ps,2),
            'probability_beating_hurdle_pct':None if hurdle is None else round(beat/ps*100,1),
            'probability_loss_gt_20_pct':round(loss20/ps*100,1),
            'expected_shortfall_pct':round(sum(p*r for p,r in neg)/negp,2) if negp else 0.0,
            'probability_provenance':prov}

def expectation(stock):
    vm=stock.get('valuation_model') or {};sc=vm.get('scenarios') or {};base=sc.get('base') or {};price=stock.get('reference_price')
    base_mult=base.get('multiple');base_eps=base.get('eps');norm=vm.get('normalized_eps')
    if not all(finite(x) and float(x)>0 for x in (price,base_mult)):
        return {'status':'INCOMPLETE','method':None,'reason':'Requires positive reference price and base-case multiple.'}
    implied=float(price)/float(base_mult)
    gap=(float(base_eps)/implied-1)*100 if finite(base_eps) and implied>0 else None
    norm_gap=(float(norm)/implied-1)*100 if finite(norm) and implied>0 else None
    breakeven=float(price)/float(base_eps) if finite(base_eps) and float(base_eps)>0 else None
    return {'status':'COMPLETE','method':'MARKET_IMPLIED_EPS_AT_BASE_MULTIPLE','ticker':str(stock.get('ticker')),
            'reference_price':price,'base_multiple':base_mult,'market_implied_eps':round(implied,2),
            'base_eps':base_eps,'base_eps_expectation_gap_pct':None if gap is None else round(gap,1),
            'normalized_eps':norm,'normalized_eps_expectation_gap_pct':None if norm_gap is None else round(norm_gap,1),
            'breakeven_multiple_at_base_eps':None if breakeven is None else round(breakeven,2),
            'authority':'ANALYTIC_ONLY','guardrail':'Expectation gap cannot create or upgrade upstream BUY.'}

def opportunity(alpha,inputs,portfolio,registry):
    b=(alpha.get('benchmark_asset',{}).get('valuation_model') or {});out=[];fr=float((inputs.get('frictions') or {}).get('round_trip_friction_pct',0) or 0)
    sec_h=return_contract(registry)['security_horizon_months']
    for src in inputs.get('alternatives',[]):
        x=dict(src);iid=x.get('id');h=x.get('native_horizon_months',12)
        if iid=='2330':
            native=b.get('expected_return_pct');h=sec_h;annual=standardized_return(native,h,fr)
            x.update(native_expected_return_pct=native,native_horizon_months=h,gross_annualized_expected_return_pct=None if native is None else round(annualize_return(native,h),2),
                     expected_return_pct=None if annual is None else round(annual,2),annualized_expected_return_pct=None if annual is None else round(annual,2),
                     status='AVAILABLE' if annual is not None else 'UNAVAILABLE',source='ALPHA_ENGINE')
        elif iid=='DEBT_REPAYMENT':
            native=portfolio.get('debt_effective_rate_pct') if portfolio.get('status')=='COMPLETE' else None;h=12
            x.update(native_expected_return_pct=native,native_horizon_months=h,expected_return_pct=native if finite(native) else None,
                     annualized_expected_return_pct=native if finite(native) else None,status='AVAILABLE' if finite(native) else 'UNAVAILABLE',source='PORTFOLIO_STATE')
        elif finite(x.get('expected_return_pct')):
            gross=float(x['expected_return_pct']);annual=gross if iid=='CASH' else standardized_return(gross,12,fr)
            x.update(gross_annualized_expected_return_pct=round(gross,2),expected_return_pct=round(annual,2),
                     annualized_expected_return_pct=round(annual,2),status='AVAILABLE')
        else:x.update(status='UNAVAILABLE',expected_return_pct=None,annualized_expected_return_pct=None)
        x['comparison_basis']=return_contract(registry)['basis'];out.append(x)
    av=[x for x in out if x.get('status')=='AVAILABLE' and finite(x.get('annualized_expected_return_pct'))]
    hurdle=max((float(x['annualized_expected_return_pct']) for x in av),default=None)
    leader=next((x for x in av if hurdle is not None and float(x['annualized_expected_return_pct'])==hurdle),None)
    return {'status':'COMPLETE' if len(av)>=3 else 'PARTIAL','comparison_basis':return_contract(registry)['basis'],
            'alternatives':out,'available_count':len(av),'hurdle_expected_return_pct':hurdle,
            'hurdle_annualized_expected_return_pct':hurdle,'hurdle_asset':leader.get('id') if leader else None,
            'note':'Hurdle uses annualized after-public-friction returns only; native mixed-horizon returns are retained for audit but never compared directly.'}

UNKNOWN_MAP={
 'SECULAR_GROWTH':[
  ('earnings_conversion','Can revenue/product ramp convert into EPS/FCF?','EPS/margin/OCF keep pace with revenue','revenue grows while margin/FCF deteriorates'),
  ('demand_visibility','How durable is AI/server demand?','first-party backlog/shipment/KPI persists','shipment or customer demand materially misses'),
  ('expectation_gap','How much growth is already priced in?','base EPS materially exceeds market-implied EPS','price requires EPS above supported base case')],
 'CYCLICAL_MEMORY':[
  ('midcycle_earnings','What is normalized mid-cycle EPS?','normalized EPS survives price normalization','profit depends on peak spot pricing/inventory gains'),
  ('cycle_position','Where are pricing/inventory in the cycle?','pricing and inventory support 24-36m path','pricing reverses before earnings path is realized'),
  ('balance_sheet','Can the company survive a cycle reversal?','liquidity and leverage remain robust','downcycle requires rescue financing')],
 'PROPERTY':[
  ('backlog_nav','What backlog/NAV is actually monetizable?','first-party backlog and completion schedule support NAV','recognition timing or sell-through breaks'),
  ('cash_conversion','Will project profits become cash?','OCF/debt trajectory confirms conversion','profits rise while leverage/cash conversion worsens'),
  ('rate_risk','How sensitive is value to funding conditions?','stress case remains survivable','rate/funding stress breaches survival limits')],
 'UTILITY':[
  ('normalized_cashflow','What is sustainable normalized cash flow?','contracted/regulated cash generation persists','one-off accounting gains dominate'),
  ('rate_spread','Can returns exceed funding cost?','spread remains positive through stress','rate reset compresses economics'),
  ('capex_return','Does capex earn above cost of capital?','first-party project economics support returns','capex grows without cash return')],
 'GENERAL_INDUSTRIAL':[
  ('earnings_quality','Is reported growth recurring?','margin/FCF confirm recurring earnings','one-off/base effects dominate'),
  ('customer_product_mix','What mix/customer mechanism drives growth?','first-party mix KPI confirms thesis','mix/customer concentration reverses'),
  ('expectation_gap','Is valuation still below supported fundamentals?','base fundamentals exceed implied expectations','price already discounts bull assumptions')]
}
def research_queue(screen,alpha):
    done={str(x.get('ticker')) for x in alpha.get('stocks',[])};rows=[]
    for r in screen.get('deep_research_queue',[]) or []:
        t=str(r.get('ticker'));a=archetype(r);unknowns=[{'id':u[0],'question':u[1],'pass_signal':u[2],'fail_signal':u[3],
          'source_priority':['company IR/MOPS','TWSE/TPEx official']} for u in UNKNOWN_MAP.get(a,UNKNOWN_MAP['GENERAL_INDUSTRIAL'])]
        flags=r.get('flags') or [];high=bool(set(flags)&{'GROWTH_BASE_EFFECT_OUTLIER','CYCLE_EXTREME_GROWTH_LOW_PE','EARNINGS_VERIFY','PROFITABILITY_PROXY_TTM_PE'})
        rows.append({'ticker':t,'name':r.get('name'),'market':r.get('market'),'rank':r.get('rank'),'screen_priority':r.get('screen_priority'),
          'reference_price':r.get('reference_price'),'archetype':a,'already_researched':t in done,'status':'REFRESH' if t in done else 'NEW_RESEARCH',
          'voi_priority':'HIGH' if high or (r.get('rank') or 999)<=5 else 'MEDIUM',
          'decision_question':'What is the smallest first-party fact that can most change capital eligibility?',
          'unknowns':unknowns,'required_evidence':['reference_price','earnings_basis','revenue_trend','balance_sheet_cash_flow','material_events','valuation_basis','24_36m_eps_or_fcf_path','structured_catalyst','survival_basis','quarterly_falsification_metrics'],
          'promotion_authority':'NONE','next_action':'resolve highest-VoI unknown → valuation route → Investment Constitution → upstream Alpha Buy Gate'})
    return {'status':'COMPLETE' if screen.get('meta',{}).get('status')=='COMPLETE' else 'DEGRADED','as_of':screen.get('meta',{}).get('as_of'),'items':rows,
            'new_research_count':sum(x['status']=='NEW_RESEARCH' for x in rows),
            'guardrail':'Research queue is an uncertainty-reduction queue. It cannot create BUY CANDIDATE or pass the Constitution.'}

def weights(portfolio):
    if portfolio.get('status')!='COMPLETE' or not finite(portfolio.get('investable_assets_twd')) or portfolio['investable_assets_twd']<=0:return {}
    total=float(portfolio['investable_assets_twd']);w={}
    for p in portfolio.get('positions',[]):
        if p.get('ticker') and finite(p.get('market_value_twd')):w[str(p['ticker'])]=float(p['market_value_twd'])/total*100
    if finite(portfolio.get('cash_twd')):w['CASH']=float(portfolio['cash_twd'])/total*100
    return w

def lifecycle(alpha,opp,policy,portfolio,registry,friction,constitution):
    h=opp.get('hurdle_annualized_expected_return_pct');w=weights(portfolio);lc=policy.get('lifecycle',{});out=[]
    for s in alpha.get('stocks',[]):
        t=str(s.get('ticker'));c=constitution.get(t,{});cs=c.get('constitution_status','BLOCKED');sr=security_return(s,registry,friction);er=sr.get('annualized_expected_return_pct')
        na=float(er)-float(h) if all(finite(x) for x in (er,h)) else None;up=s.get('action');cw=w.get(t);act='RESEARCH';reason='Upstream action is not BUY; portfolio layer cannot upgrade it.'
        if s.get('thesis_status')=='INVALIDATED':act,reason='EXIT_REVIEW','Thesis invalidated.'
        elif up=='BUY CANDIDATE':
            if cs!='PASS':act,reason='CONSTITUTION_BLOCK',f'Upstream BUY is blocked because Investment Constitution is {cs}.'
            elif na is None:act,reason='HOLD_REVIEW','Comparable annualized opportunity hurdle incomplete.'
            elif na<=float(lc.get('exit_when_net_alpha_spread_below_pct',-5)):act,reason='EXIT_REVIEW','Annualized net alpha is materially below opportunity hurdle.'
            elif na<=float(lc.get('trim_when_net_alpha_spread_below_pct',2)):act,reason='TRIM_REVIEW','Annualized net alpha edge compressed.'
            elif cw is None:act,reason='BUY_REVIEW','Upstream BUY and Investment Constitution both pass; sizing requires current portfolio state.'
            else:act,reason='ADD_REVIEW','Upstream BUY and Investment Constitution both pass and position exists.'
        elif cw is not None:act,reason='HOLD_REVIEW','Held position is not an upstream BUY; review thesis and opportunity cost.'
        out.append({'ticker':s.get('ticker'),'name':s.get('name'),'upstream_action':up,'constitution_status':cs,'constitution_capital_eligible':bool(c.get('capital_eligible')),
          'portfolio_action':act,'native_expected_return_pct':sr.get('native_expected_return_pct'),'native_horizon_months':sr.get('native_horizon_months'),
          'expected_return_pct':er,'annualized_expected_return_pct':er,'hurdle_expected_return_pct':h,'hurdle_annualized_expected_return_pct':h,
          'net_alpha_spread_pct':None if na is None else round(na,2),'current_weight_pct':None if cw is None else round(cw,2),'return_basis':sr.get('return_basis'),'reason':reason})
    return out

def risk(alpha,portfolio,policy,portfolio_model):
    w=weights(portfolio)
    if portfolio.get('status')!='COMPLETE':
        return {'status':'UNCONFIGURED','personalized':False,'violations':[],'stress_tests':[],'survival_gate':{'status':'UNCONFIGURED'},
                'note':'No personalized server-side risk output until browser-local portfolio state is supplied to the local planner.'}
    c=policy.get('constraints',{});violations=[];facts={str(x.get('ticker')):x for x in portfolio_model.get('security_loadings',[])}
    factors={};assets=float(portfolio.get('investable_assets_twd') or 0);debt=float(portfolio.get('debt_twd') or 0)
    for t,x in w.items():
        if t=='CASH':continue
        if x>c.get('max_single_stock_pct',25):violations.append({'type':'SINGLE_STOCK','ticker':t,'weight_pct':round(x,2),'limit_pct':c.get('max_single_stock_pct',25)})
        arch=(facts.get(t) or {}).get('archetype') or archetype(next((s for s in alpha.get('stocks',[]) if str(s.get('ticker'))==t),{}));factors[arch]=factors.get(arch,0)+x
    for f,x in factors.items():
        if x>c.get('max_common_factor_pct',60):violations.append({'type':'COMMON_FACTOR','factor':f,'weight_pct':round(x,2),'limit_pct':c.get('max_common_factor_pct',60)})
    dr=debt/assets*100 if assets else None
    if dr is not None and dr>c.get('max_net_debt_to_investable_assets_pct',25):violations.append({'type':'LEVERAGE','value_pct':round(dr,2),'limit_pct':c.get('max_net_debt_to_investable_assets_pct',25)})
    stress=[];alt=portfolio_model.get('alternative_loadings',{});scenario_map=portfolio_model.get('stress_scenarios',{})
    for name,shock in scenario_map.items():
        pr=0.0;coverage=0.0
        for t,wpct in w.items():
            if t=='CASH':continue
            L=(facts.get(t) or {}).get('factor_loadings') or alt.get(t)
            if not L:continue
            coverage+=wpct;sr=sum(float(L.get(f,0) or 0)*float(shock.get(f,0) or 0) for f in portfolio_model.get('factors',[]));sr=max(-90.0,min(60.0,sr));pr+=(wpct/100.0)*sr
        post=assets*(1+pr/100.0);postdr=debt/post*100 if post>0 else None;breach=postdr is not None and postdr>float(c.get('max_net_debt_to_investable_assets_pct',25))
        stress.append({'scenario':name,'portfolio_return_pct':round(pr,2),'modeled_weight_coverage_pct':round(coverage,2),
                       'post_shock_assets_twd':round(post,0),'post_shock_debt_ratio_pct':None if postdr is None else round(postdr,2),'leverage_limit_breached':breach})
    reverse=[];eq=sum(x for t,x in w.items() if t!='CASH')
    for shock in (-20,-35,-50):
        impact=eq/100*shock;post=assets*(1+impact/100);reverse.append({'market_shock_pct':shock,'portfolio_impact_pct':round(impact,2),'post_shock_debt_ratio_pct':round(debt/post*100,2) if post>0 else None})
    stress_breach=any(x.get('leverage_limit_breached') for x in stress)
    forced='PASS' if debt<=0 else ('UNKNOWN' if not finite(portfolio.get('broker_maintenance_threshold_pct')) else ('REVIEW' if stress_breach else 'PASS'))
    survival='FAIL' if stress_breach else ('BLOCKED' if forced=='UNKNOWN' else 'PASS')
    return {'status':'REVIEW' if violations or survival!='PASS' else 'PASS','personalized':True,'weights_pct':{k:round(v,2) for k,v in w.items()},
            'common_factor_exposure_pct':{k:round(v,2) for k,v in factors.items()},'debt_to_investable_assets_pct':None if dr is None else round(dr,2),
            'violations':violations,'stress_tests':stress,'reverse_stress_tests':reverse,
            'survival_gate':{'status':survival,'forced_sale_state':forced,'stress_leverage_breach':stress_breach,
              'broker_maintenance_threshold_pct':portfolio.get('broker_maintenance_threshold_pct'),
              'guardrail':'Unknown brokerage maintenance rules fail closed for leveraged portfolios; browser-local planner owns private margin inputs.'}}

def sizing(alpha,opp,policy,portfolio,registry,friction,constitution,scenario_cal,risk_result):
    if portfolio.get('status')!='COMPLETE':return {'status':'UNCONFIGURED','targets':[],'note':'Configure browser-local portfolio state before personalized sizing.'}
    if (risk_result.get('survival_gate') or {}).get('status')!='PASS':return {'status':'SURVIVAL_BLOCKED','targets':[],'note':'Portfolio survival gate must PASS before new-capital sizing.'}
    h=opp.get('hurdle_annualized_expected_return_pct')
    if h is None:return {'status':'BLOCKED','targets':[],'note':'Comparable annualized opportunity hurdle unavailable.'}
    rows=[]
    for s in alpha.get('stocks',[]):
        t=str(s.get('ticker'));c=constitution.get(t,{})
        if s.get('action')!='BUY CANDIDATE' or c.get('constitution_status')!='PASS':continue
        er=security_return(s,registry,friction).get('annualized_expected_return_pct');conf=s.get('confidence_score');down=s.get('risk_model',{}).get('downside_pct');d=distribution(s,h,registry,friction,scenario_cal);beat=d.get('probability_beating_hurdle_pct')
        if all(finite(x) for x in (er,conf,down,beat)):
            raw=max(0,float(er)-float(h))*(float(conf)/100)*(float(beat)/100)/max(10,float(down))
            if raw>0:rows.append((s,raw,d))
    if not rows:return {'status':'NO_BUY','targets':[],'note':'No upstream BUY candidate also passes Constitution, comparable-return and survival gates.'}
    total=sum(x[1] for x in rows);w=weights(portfolio);cap=policy.get('constraints',{});invest=policy.get('sizing',{}).get('normalize_to_investable_pct',85);targets=[]
    for s,raw,d in rows:
        cur=w.get(str(s.get('ticker')),0);maxw=cap.get('max_single_stock_pct',25) if cur>0 else min(cap.get('max_single_stock_pct',25),cap.get('max_new_position_pct',12));target=min(maxw,raw/total*invest)
        targets.append({'ticker':s.get('ticker'),'name':s.get('name'),'target_weight_pct':round(target,2),'current_weight_pct':round(cur,2),'raw_score':round(raw,4),'probability_beating_hurdle_pct':d.get('probability_beating_hurdle_pct'),'constitution_status':'PASS'})
    return {'status':'COMPLETE','targets':targets,'cash_floor_pct':cap.get('cash_floor_pct')}

def fp(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def generate():
    now=dt.datetime.now(TZ).replace(microsecond=0);bundle=load('alpha_engine.json');alpha=bundle.get('alpha',{});screen=bundle.get('screen',{})
    policy=load('portfolio_policy.json');portfolio=load('portfolio_state.json');inputs=load('opportunity_inputs.json');registry=load('model_registry.json')
    pm=load('portfolio_model.json');scenario_cal=load('scenario_probability_calibration.json',{});friction=float((inputs.get('frictions') or {}).get('round_trip_friction_pct',0) or 0)
    cres=load('investment_constitution_results.json',{});cmap={str(x.get('ticker')):x for x in cres.get('securities',[])}
    opp=opportunity(alpha,inputs,portfolio,registry);rq=research_queue(screen,alpha);lc=lifecycle(alpha,opp,policy,portfolio,registry,friction,cmap);rk=risk(alpha,portfolio,policy,pm);sz=sizing(alpha,opp,policy,portfolio,registry,friction,cmap,scenario_cal,rk)
    probs=[{'ticker':s.get('ticker'),'name':s.get('name'),'archetype':archetype(s),'valuation_model':s.get('valuation_model',{}).get('model_type'),'distribution':distribution(s,opp.get('hurdle_annualized_expected_return_pct'),registry,friction,scenario_cal)} for s in alpha.get('stocks',[])]
    expectations=[expectation(alpha.get('benchmark_asset',{}))]+[expectation(s) for s in alpha.get('stocks',[])]
    out={'version':3,'generated_at':now.isoformat(),'model_version':registry.get('model_version'),'status':'COMPLETE' if alpha and screen and cres.get('status')=='COMPLETE' else 'DEGRADED','objective':policy.get('objective'),
         'return_comparison_contract':return_contract(registry),'investment_constitution':{'status':cres.get('status'),'pass_count':cres.get('pass_count'),'capital_eligible_count':cres.get('capital_eligible_count'),'authority':cres.get('authority')},
         'research_queue':rq,'opportunity_set':opp,'expectation_analysis':expectations,'probabilistic_returns':probs,'lifecycle':lc,'portfolio_risk':rk,'target_sizing':sz,'portfolio_state_status':portfolio.get('status'),
         'guardrails':{'portfolio_cannot_upgrade_upstream_action':True,'constitution_required_for_new_capital':True,'constitution_cannot_create_upstream_buy':True,'mixed_horizon_returns_never_compared':True,'expectation_engine_has_no_buy_authority':True,'unavailable_benchmarks_not_fabricated':True,'personalized_sizing_requires_complete_portfolio_state':True,'survival_gate_required_before_sizing':True,'no_automatic_trading':True}}
    out['fingerprint']=fp({k:out[k] for k in ('model_version','return_comparison_contract','investment_constitution','research_queue','opportunity_set','expectation_analysis','lifecycle','portfolio_risk','target_sizing')});save_json('capital_allocation.json',out);save_json('deep_research_queue.json',rq);save_json('opportunity_set.json',opp);return out
if __name__=='__main__':print(json.dumps(generate(),ensure_ascii=False,indent=2))
