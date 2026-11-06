"""Runtime checks for free ESPN live-score browser parsing.

Executes the shipped dashboard JavaScript in Node with mocked ESPN replies.
No external requests, no betting picks, and no frozen performance mutations.
"""
import subprocess
import unittest
from pathlib import Path


class LiveBrowserTests(unittest.TestCase):
    def test_numeric_scores_two_live_games_and_ungrouped_fallback(self):
        js = r"""
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('site/index.html','utf8');
const start=html.indexOf('function espnScore(value){');
const end=html.indexOf('function render(){',start);
assert.ok(start>0 && end>start,'Live score parser absent');
const now=new Date();
const kickoff=new Date(now.getTime()-12*60*1000).toISOString();
function event(id,home,away,hs,as,status='in'){
 return {id,date:kickoff,status:{
   period:3,displayClock:'08:21',type:{state:status,completed:false,shortDetail:'3rd 08:21'}},
   competitions:[{date:kickoff,competitors:[
     {homeAway:'home',team:{displayName:home},score:String(hs)},
     {homeAway:'away',team:{displayName:away},score:String(as)}]}]};
}
const first=event('401800001','Akron Zips','Ohio Bobcats',7,7);
const updated=event('401800001','Akron Zips','Ohio Bobcats',24,21);
const second=event('401800002','Temple Owls','UTSA Roadrunners',31,17);
let requests=0;
const ctx={
 console,setTimeout,clearTimeout,AbortController,
 ESPN_LIVE_URL:'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard',
 data:{live_games:[{
   game_id:'401800001',home_team:'Akron Zips',away_team:'Ohio Bobcats',
   kickoff_utc:kickoff,pregame:{pre_kickoff_archive_verified:true,archived_home_points:21}
 }]},
 identityKey:x=>String(x||'').toLowerCase().replace(/[^a-z0-9]/g,''),
 fetch:async url=>{
  requests++;
  const events=url.includes('groups=80')?[first]:[updated,second];
  return {ok:true,json:async()=>({events})};
 }
};
vm.createContext(ctx);
vm.runInContext(html.slice(start,end),ctx);
assert.equal(ctx.espnScore('17'),17);
assert.equal(ctx.espnScore('7-7'),null);
assert.equal(ctx.espnScore('X'),null);
assert.equal(ctx.parseEspnLive({events:[first,second]},now.toISOString()).length,2);
assert.equal(ctx.parseEspnLive({events:[event('401800003','A','B',17,9,'post')]},
 now.toISOString()).length,0);
assert.equal(ctx.liveRequestUrls(now).length>=2,true);
(async()=>{
 const fetched=await ctx.liveBrowserFetch();
 assert.equal(fetched.games.length,2,'Must include two active ESPN games');
 const one=fetched.games.find(g=>g.game_id==='401800001');
 const two=fetched.games.find(g=>g.game_id==='401800002');
 assert.equal(one.home_score,24,'Newest scored feed should replace cached 7-7');
 assert.equal(one.away_score,21);
 assert.equal(two.home_score,31);
 assert.equal(two.away_score,17);
 assert.equal(one.pregame.archived_home_points,21,'Never rewrite frozen pregame score');
 assert.equal(two.pregame,null,'Never invent a pregame snapshot for unknown matchup');
 assert.equal(one.in_game_model_update,null,'Live score must not fabricate an in-game model');
 assert.ok(requests>=2);
 console.log('OK: numeric live scoreboard, extra game and unchanged frozen projection');
})().catch(error=>{console.error(error);process.exitCode=1});
"""
        result=subprocess.run(
            ["node","-e",js],capture_output=True,text=True,timeout=25,
            check=False,cwd=Path(__file__).resolve().parent.parent)
        self.assertEqual(result.returncode,0,
                         result.stderr or result.stdout)
        self.assertIn("OK: numeric live scoreboard",result.stdout)

    def test_html_has_no_backend_rebilling_or_forecast_rewrite(self):
        text=Path("site/index.html").read_text(encoding="utf-8")
        self.assertIn('const ESPN_LIVE_URL="https://site.api.espn.com/',text)
        self.assertIn('mode:"cors",cache:"no-store"',text)
        self.assertIn('byId("live-games").replaceChildren(...live.map(liveGameCard))',text)
        self.assertIn('renderPerformance();updateDayNav();render();renderLive();',text)
        self.assertIn('},60000);',text)
        self.assertNotIn("data.prospective_records=",text)
        self.assertNotIn("archived_home_points=",text)


if __name__=="__main__":
    unittest.main()
