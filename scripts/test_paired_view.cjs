// Artificial UI-envelope tests; these are not browser or live-game results.
const assert = require('node:assert/strict');
const { isPairedView } = require('../runs/view-contract/paired-view.js');
const source = 'https://github.com/Unjuno/connectome-fighter/actions/runs/123';
const evaluation = {protocol:'paired-rollout-combat-v1',round_frame_limit:3600,decision_interval_frames:60,seed_p1:800101,seed_p2:20202};
const ev = phase => ({status:'COMPLETED',candidate_only:true,auto_promotion:false,policy_pixel_access:false,served_by_vercel:false,
 comparison_phase:phase,source_training_run_url:source,state_sha256:'a'.repeat(64),generation:11,reward_id:'outcome-hp-epsilon002-v1',
 video:{asset_url:`https://github.com/Unjuno/connectome-fighter/releases/download/paired-cycle-123-1/${phase}.mp4`,sha256:'c'.repeat(64)},
 result:{p1_hp:400,p2_hp:400,combat_score:0},evaluation});
const base={schema_version:1,rollout:'paired-neural-rollout-v1',ready:true,status:'paired-evaluation-ready',protocol_sha256:'b'.repeat(64),
 cycle_index:1,accepted_update_count:0,source_run_url:source,previous:ev('before'),latest:ev('after'),training:{cycle_index:1,
 accepted_update_count:0,source_run_url:source,auto_promotion:false,served_by_vercel:false,state_sha256:'a'.repeat(64),
 accepted_update:false,phase:'curriculum',strength_claim:false}};
let passed=0;
function test(name, fn){fn();passed++;console.log('PASS '+name);}
test('accept coherent no-update recording',()=>assert.equal(isPairedView(base),true));
for(const [name, mutate] of [
 ['no mixed runs', v=>v.latest.source_training_run_url=source+'4'],
 ['no reward substitution', v=>v.latest.reward_id='R2e-combat-v1'],
 ['no phantom updates', v=>v.training.accepted_update=true],
 ['no phantom generation', v=>v.latest.generation=12],
 ['no promotion', v=>v.latest.auto_promotion=true],
 ['no missing checkpoint hash', v=>v.latest.state_sha256='unknown'],
 ['no different media run', v=>v.latest.video.asset_url=v.latest.video.asset_url.replace('cycle-123-', 'cycle-124-')],
 ['no mixed media attempts', v=>v.latest.video.asset_url=v.latest.video.asset_url.replace('123-1/', '123-2/')],
 ['no external video', v=>v.latest.video.asset_url='https://example.invalid/after.mp4'],
 ['no malformed video hash', v=>v.previous.video.sha256=''],
 ['no nonfinite HP', v=>v.latest.result.p1_hp=NaN],
 ['no changed cadence', v=>v.latest.evaluation.decision_interval_frames=15],
 ['no mismatched counters', v=>v.training.cycle_index=2],
 ['no unsupported phase', v=>v.training.phase='strong'],
 ['no strength claim', v=>v.training.strength_claim=true],
]) test(name,()=>{const v=structuredClone(base);mutate(v);assert.equal(isPairedView(v),false);});
test('accept real-count increment with changed weight identity',()=>{const v=structuredClone(base);v.accepted_update_count=1;v.training.accepted_update_count=1;v.training.accepted_update=true;v.latest.generation=12;v.latest.state_sha256='d'.repeat(64);v.training.state_sha256=v.latest.state_sha256;assert.equal(isPairedView(v),true);});
console.log(JSON.stringify({kind:'artificial-envelope-unit-tests',passed}));
