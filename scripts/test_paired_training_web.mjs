// Isolated UI/receipt-contract tests. Fixtures are not game or learning evidence.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';
import { chromium } from 'playwright';
import ts from 'typescript';
const out='runs/paired-training-web';fs.mkdirSync(out,{recursive:true});
const port=3215,origin=`http://127.0.0.1:${port}`;
const m={outcome:0,combat_score:0,curriculum_score:0,p1_hp:400,p2_hp:400,damage_dealt_hp:0,damage_taken_hp:0,minimum_observed_distance_px:480,approach_progress:0,decision_count:60,elapsed_frame:3600,no_damage_draw:true};
const base='https://github.com/Unjuno/connectome-fighter/releases/download/paired-cycle-123-1/';
const report={status:'PASS',experiment:'paired-neural-training-v1',candidate_only:true,auto_promotion:false,strength_claim:false,parent_source_unchanged:true,
 cycle:1,accepted_update:false,update_reason:'zero paired signal',completed_games:8,actual_pipeline_seconds:480,schedule_minutes:10,
 source_commit:'a'.repeat(40),source_run_id:'123',source_run_attempt:'1',source_run_url:'https://github.com/Unjuno/connectome-fighter/actions/runs/123',
 report_url:base+'summary.json',state_url:base+'search-state.npz',release_tag:'paired-cycle-123-1',completed_at:new Date().toISOString(),
 state:{experiment:'paired-neural-training-v1',candidate_only:true,auto_promotion:false,production_compatible:false,cycle:1,accepted_updates:0,total_completed_games:8,weights_sha256:'b'.repeat(64),state_file_sha256:'c'.repeat(64),weights_changed:false},
 baseline_curriculum:m,combat_before:m,combat_after:m,
 videos:Object.fromEntries(['before','after','curriculum'].map(k=>[k,{url:base+k+'.mp4',sha256:'d'.repeat(64),bytes:12000,recording_seconds:60}])),
 history:[{cycle:1,completed_at:new Date().toISOString(),accepted_update:false,update_reason:'zero paired signal',accepted_updates:0,damage_dealt_hp:0,combat_score:0}]};
const compiled=ts.transpileModule(fs.readFileSync('lib/paired-training-contract.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const module={};new Function('exports',compiled)(module);
assert(module.parseTrainingReport(report));
const bad=[r=>r.auto_promotion=true,r=>r.strength_claim=true,r=>r.state.production_compatible=true,r=>r.state.accepted_updates=2,r=>r.state.cycle=0,r=>r.source_commit='bad',r=>r.source_run_url='https://example.com/',r=>r.videos.after.url='https://example.com/fake.mp4',r=>r.videos.after.sha256='bad',r=>r.combat_after.damage_dealt_hp=NaN,r=>r.history=[],r=>r.history[0].cycle=2,r=>r.completed_at='bad',r=>r.accepted_update=true,r=>r.schedule_minutes=5];
for(const change of bad){const x=structuredClone(report);change(x);assert.equal(module.parseTrainingReport(x),null);}
execFileSync('ffmpeg',['-y','-f','lavfi','-i','color=c=0x283039:s=960x640:r=10','-vf',"drawtext=text='UI TEST FIXTURE - NOT A GAME':fontcolor=white:fontsize=28:x=(w-text_w)/2:y=(h-text_h)/2",'-t','1','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',out+'/fixture.mp4'],{stdio:'ignore'});
const video=fs.readFileSync(out+'/fixture.mp4');
const log=fs.openSync(out+'/server.log','w');
const server=spawn('npm',['run','start','--','-p',String(port)],{stdio:['ignore',log,log],detached:true});
let browser;const results=[];const errors=[];
try{
 for(let i=0;i<120;i++){try{if((await fetch(origin+'/training')).ok)break;}catch{}if(i===119)throw new Error('server startup timeout');await new Promise(r=>setTimeout(r,500));}
 browser=await chromium.launch({headless:true});
 async function scenario(name,body,fn,width=1440){
  const context=await browser.newContext({viewport:{width,height:1000},reducedMotion:'reduce'});
  await context.route('**/*',async route=>{const u=new URL(route.request().url());if(u.origin===origin)return route.continue();if(u.pathname.endsWith('.mp4'))return route.fulfill({status:200,contentType:'video/mp4',body:video});return route.abort();});
  await context.route('**/api/paired-training',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(typeof body==='function'?body():body)}));
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+'/training');await fn(page,context);results.push({name,status:'PASS',fixture:true});await context.close();
 }
 const envelope={ready:true,status:'completed-cycle',latest:report};
 await scenario('recorded result and no-update counter',envelope,async page=>{
  await page.getByTestId('training-status').filter({hasText:'Completed cycle 1'}).waitFor();
  assert.equal(await page.getByTestId('accepted-count').textContent(),'0');
  assert.equal(await page.locator('html').getAttribute('lang'),'en');
  assert.equal(await page.getByTestId('training-video').getAttribute('src'),base+'after.mp4');
  await page.getByRole('button',{name:'Parent combat',exact:true}).click();
  assert.equal(await page.getByTestId('training-video').getAttribute('src'),base+'before.mp4');
  await page.getByRole('button',{name:'Parent practice',exact:true}).click();
  assert.equal(await page.getByTestId('training-video').getAttribute('src'),base+'curriculum.mp4');
  await page.getByRole('button',{name:'Selected combat',exact:true}).click();
  await page.screenshot({path:out+'/training-fixture-desktop.png',fullPage:true});
 });
 await scenario('mobile layout has no horizontal overflow',envelope,async page=>{
  await page.getByTestId('cycle-count').filter({hasText:'1'}).waitFor();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:out+'/training-fixture-mobile.png',fullPage:true});
 },375);
 await scenario('missing receipt never becomes zero-valued progress',{ready:false,status:'awaiting-first-cycle',latest:null},async page=>{
  await page.getByTestId('training-status').filter({hasText:'Awaiting the first'}).waitFor();
  assert.equal(await page.getByTestId('cycle-count').textContent(),'—');
  assert.equal(await page.getByTestId('training-video').count(),0);
 });
 const invalid=structuredClone(report);invalid.state.accepted_updates=99;
 await scenario('invalid receipt rejected', {ready:true,latest:invalid},async page=>{
  await page.getByTestId('training-status').filter({hasText:'unavailable'}).waitFor();assert.equal(await page.getByTestId('cycle-count').textContent(),'—');
 });
 const old=structuredClone(report);old.completed_at='2020-01-01T00:00:00Z';
 await scenario('stale receipt not presented as active training',{ready:true,latest:old},async page=>{
  await page.getByText('The last completed cycle is over one hour old.',{exact:false}).waitFor();
 });
 let current=envelope;
 await scenario('pause resume and progression without invented updates',()=>current,async page=>{
  await page.getByTestId('cycle-count').filter({hasText:'1'}).waitFor();
  await page.getByRole('button',{name:'Pause viewer',exact:true}).click();
  assert.equal(await page.getByTestId('training-status').textContent(),'Viewer updates paused');
  const next=structuredClone(report);next.cycle=2;next.state.cycle=2;next.state.total_completed_games=16;next.history.push({...next.history[0],cycle:2});current={ready:true,status:'completed-cycle',latest:next};
  await page.getByRole('button',{name:'Resume viewer',exact:true}).click();
  await page.getByTestId('cycle-count').filter({hasText:'2'}).waitFor();assert.equal(await page.getByTestId('accepted-count').textContent(),'0');
 });
 await scenario('keyboard evidence disclosure',envelope,async page=>{
  const summary=page.getByText('Inspect evidence and scientific boundaries',{exact:true});await summary.focus();await page.keyboard.press('Enter');
  assert.equal(await page.locator('details.training-provenance').getAttribute('open'),'');
 });
 assert.deepEqual(errors,[]);
 fs.writeFileSync(out+'/results.json',JSON.stringify({status:'PASS',fixture_only:true,receipt_cases:16,browser_scenarios:results,page_errors:errors},null,2));
 console.log(JSON.stringify({status:'PASS',receipt_cases:16,browser_scenarios:results.length}));
}finally{if(browser)await browser.close();try{process.kill(-server.pid,'SIGTERM');}catch{}fs.closeSync(log);}
