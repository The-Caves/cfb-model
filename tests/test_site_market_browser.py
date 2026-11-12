"""Browser quote capture: source-only, pre-kickoff and unchanged model scores."""
import subprocess
import unittest
from pathlib import Path

class BrowserMarketTests(unittest.TestCase):
    def test_source_matched_prices_without_fabricated_probabilities(self):
        js = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('site/index.html','utf8');
const start=html.indexOf('function americanMarketNumber(value){');
const end=html.indexOf('function render(){',start);
assert.ok(start>0 && end>start,'Market parser absent');
const startTime='2026-11-12T16:00:00Z',kick='2026-11-13T01:00:00Z';
const g={game_id:'401862824',home_team:'South Florida Bulls',away_team:'Memphis Tigers',
         kickoff_utc:kick,model_home_margin:9.5,model_total:54.5};
const data={games:[g]},dateOf=x=>new Date(x);
const dateKey=d=>String(d.getUTCMonth()+1).padStart(2,'0')+'/'+
  String(d.getUTCDate()).padStart(2,'0')+'/'+d.getUTCFullYear();
const ctx={data,dateKey,dateOf,selectedDay:'11/13/2026',
           identityKey:s=>String(s||'').toLowerCase().replace(/[^a-z0-9]/g,'')};
vm.createContext(ctx);
vm.runInContext(html.slice(start,end),ctx);
const offer={provider:{name:'DraftKings'},spread:3.5,overUnder:52.5,
             homeTeamOdds:{favorite:false,moneyLine:'+140'},
             awayTeamOdds:{favorite:true,moneyLine:-165}};
const comp={date:kick,competitors:[
 {homeAway:'home',team:{displayName:'South Florida Bulls'}},
 {homeAway:'away',team:{displayName:'Memphis Tigers'}}],odds:[offer]};
const event={id:'401862824',date:kick,competitions:[comp]};
const market=ctx.parseEspnMarket({events:[event]},startTime);
assert.equal(market.length,1);
assert.equal(market[0].market_home_spread,3.5);
assert.equal(market[0].market_total,52.5);
assert.equal(market[0].market_home_moneyline,140);
assert.equal(market[0].market_away_moneyline,-165);
assert.equal(market[0].market_provider,'DraftKings');
assert.equal(g.model_home_margin,9.5);
assert.equal(g.model_total,54.5);
assert.equal(ctx.marketDays(new Date(startTime))[0],'20261113');
assert.equal(ctx.americanMarketNumber('0'),null);
assert.equal(ctx.americanMarketNumber('200.5'),null);
assert.equal(ctx.americanMarketNumber('not a price'),null);
assert.equal(ctx.americanMarketNumber('-110'),-110);
const noFlag=JSON.parse(JSON.stringify(event));
delete noFlag.competitions[0].odds[0].homeTeamOdds.favorite;
assert.equal(ctx.parseEspnMarket({events:[noFlag]},startTime)[0].market_home_spread,null);
const wrong=JSON.parse(JSON.stringify(event));
wrong.competitions[0].competitors[0].team.displayName='Wrong Team';
assert.equal(ctx.parseEspnMarket({events:[wrong]},startTime).length,0);
assert.equal(ctx.parseEspnMarket({events:[event]},'2026-11-13T02:00:00Z').length,0);
const wrongKick=JSON.parse(JSON.stringify(event));
wrongKick.competitions[0].date='2026-11-14T01:00:00Z';
assert.equal(ctx.parseEspnMarket({events:[wrongKick]},startTime).length,0);
console.log('OK: observed sportsbook quotes, signed spreads and immutable model data');
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True,
                                timeout=20, cwd=Path(__file__).resolve().parent.parent)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("OK: observed sportsbook quotes", result.stdout)

    def test_dashboard_market_and_model_remain_independent(self):
        src = Path("site/index.html").read_text(encoding="utf-8")
        self.assertIn('const marketClientRows=new Map()', src)
        self.assertIn('const display=marketClientRows.get(String(g.game_id))||g;', src)
        self.assertIn('Number.isFinite(modelMargin)&&handicap!==null?modelMargin+handicap:null', src)
        self.assertIn('Number.isFinite(modelTotal)&&total!==null?modelTotal-total:null', src)
        self.assertIn('300000);', src)
        self.assertNotIn('g.model_home_margin=', src)
        self.assertNotIn('data.prospective_records=', src)

if __name__ == "__main__":
    unittest.main()
