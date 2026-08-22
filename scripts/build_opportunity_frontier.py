#!/usr/bin/env python3
import argparse,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';OUT=DATA/'opportunity_frontier.json'

def load(name,default=None):
 p=DATA/name;return json.loads(p.read_text(encoding='utf-8')) if p.exists() else ({} if default is None else default)

def build():
 cap=load('capital_allocation.json',{})
 alternatives=[x for x in (cap.get('opportunity_set') or {}).get('alternatives') or [] if x.get('status')=='AVAILABLE']
 probs={x.get('ticker'):x.get('distribution') or {} for x in cap.get('probabilistic_returns') or []}
 rows=[]
 for x in alternatives:
  dist=probs.get(str(x.get('id'))) or {}
  rows.append({
   'id':x.get('id'),'name':x.get('name'),'type':x.get('type'),'source':x.get('source'),
   'annualized_expected_return_pct':x.get('annualized_expected_return_pct'),
   'expected_shortfall_pct':dist.get('expected_shortfall_pct') if dist.get('status')=='COMPLETE' else None,
   'probability_loss_gt_20_pct':dist.get('probability_loss_gt_20_pct') if dist.get('status')=='COMPLETE' else None,
   'liquidity_evidence':x.get('liquidity') or None,
   'risk_complete':dist.get('status')=='COMPLETE',
  })
 # Add researched securities as diagnostic frontier candidates, but preserve
 # upstream/capital eligibility so the frontier can never upgrade authority.
 lifecycle={x.get('ticker'):x for x in cap.get('lifecycle') or []}
 for ticker,dist in probs.items():
  life=lifecycle.get(ticker) or {}
  if dist.get('status')!='COMPLETE':continue
  rows.append({
   'id':ticker,'name':next((x.get('name') for x in cap.get('probabilistic_returns') or [] if x.get('ticker')==ticker),ticker),
   'type':'researched_security','source':'ALPHA_ENGINE+CAPITAL_OS',
   'annualized_expected_return_pct':dist.get('annualized_expected_return_pct'),
   'expected_shortfall_pct':dist.get('expected_shortfall_pct'),
   'probability_loss_gt_20_pct':dist.get('probability_loss_gt_20_pct'),
   'liquidity_evidence':None,'risk_complete':True,
   'upstream_action':life.get('upstream_action'),'constitution_status':life.get('constitution_status'),
   'capital_action':life.get('portfolio_action'),'capital_eligible':life.get('constitution_capital_eligible') is True,
  })
 comparable=[x for x in rows if x.get('annualized_expected_return_pct') is not None and x.get('expected_shortfall_pct') is not None]
 frontier=[]
 for a in comparable:
  dominated=False
  for b in comparable:
   if a is b:continue
   # Higher return and less-negative expected shortfall dominate; at least one strict.
   ar=float(a['annualized_expected_return_pct']);br=float(b['annualized_expected_return_pct'])
   ae=float(a['expected_shortfall_pct']);be=float(b['expected_shortfall_pct'])
   if br>=ar and be>=ae and (br>ar or be>ae):
    dominated=True;break
  if not dominated:frontier.append(a['id'])
 missing=[x['id'] for x in rows if not x.get('risk_complete')]
 return {
  'version':1,'contract':'capital-opportunity-frontier-v1','authority':False,
  'status':'COMPLETE' if not missing else 'PARTIAL_RISK_DATA',
  'comparison_basis':(cap.get('opportunity_set') or {}).get('comparison_basis'),
  'dimensions':{'return':'annualized_expected_return_pct','tail_risk':'expected_shortfall_pct','liquidity':'evidence-only-until-standardized'},
  'assets':rows,'comparable_asset_count':len(comparable),'non_dominated_ids':frontier,'missing_standardized_risk_ids':missing,
  'current_hurdle_unchanged':True,
  'guardrail':'Frontier is diagnostic until public risk/liquidity evidence is standardized across alternatives. It cannot override upstream action, Constitution, sizing, or the production hurdle.'
 }

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();obj=build()
 if a.check:
  assert load('opportunity_frontier.json',{})==obj,'opportunity_frontier.json stale';print('OPPORTUNITY FRONTIER PASS')
 else:OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(OUT)
if __name__=='__main__':main()
