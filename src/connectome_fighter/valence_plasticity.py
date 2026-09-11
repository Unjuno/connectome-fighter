"""Valence-channel reward plasticity over real MaleCNS KC->MBON edges.

This is a project model extension layered on top of MaleCNS anatomy and the
pinned Shiu LIF dynamics. It never creates/removes edges, never changes
transmitter sign, and only depresses existing KC->MBON magnitudes.

Positive modulatory signal targets avoidance-associated MBON channels;
negative modulatory signal targets approach-associated MBON channels. The
channel partition is derived from post-MBON transmitter identity and the
population-level valence relationship reported in Aso et al. 2014 eLife.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

STATE_SCHEMA = 1


def sha256_file(path: str | Path) -> str:
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class ValencePlasticityConfig:
    learning_rate: float = 0.01
    eligibility_decay: float = 0.9
    pair_count_cap: float = 25.0
    normalization_percentile: float = 95.0
    multiplier_min: float = 0.8
    multiplier_max: float = 1.0
    positive_target: str = 'avoidance_associated'
    negative_target: str = 'approach_associated'
    reward_id: str = 'R2d-v0'

    def validate(self) -> None:
        if not (0 < self.learning_rate <= 0.1): raise ValueError('learning_rate must be in (0,0.1]')
        if not (0 < self.eligibility_decay <= 1): raise ValueError('eligibility_decay must be in (0,1]')
        if self.pair_count_cap <= 0: raise ValueError('pair_count_cap must be positive')
        if not (0 < self.normalization_percentile <= 100): raise ValueError('normalization_percentile invalid')
        if not (0 < self.multiplier_min <= self.multiplier_max <= 1.0): raise ValueError('depression-only multiplier bounds invalid')
        if self.positive_target != 'avoidance_associated': raise ValueError('positive target contract changed')
        if self.negative_target != 'approach_associated': raise ValueError('negative target contract changed')
        if not self.reward_id: raise ValueError('reward_id missing')

    def fingerprint(self) -> str:
        self.validate()
        payload={
            'learning_rate':self.learning_rate,
            'eligibility_decay':self.eligibility_decay,
            'pair_count_cap':self.pair_count_cap,
            'normalization_percentile':self.normalization_percentile,
            'multiplier_min':self.multiplier_min,
            'multiplier_max':self.multiplier_max,
            'positive_target':self.positive_target,
            'negative_target':self.negative_target,
            'reward_id':self.reward_id,
        }
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


@dataclass
class ValencePlasticityState:
    character: str
    multipliers: np.ndarray
    generation: int
    matches: int
    update_events: int
    candidate_sha256: str
    config_sha256: str

    def validate(self, n: int, config: ValencePlasticityConfig) -> None:
        config.validate()
        if self.multipliers.shape != (n,): raise ValueError('multiplier shape mismatch')
        if not np.isfinite(self.multipliers).all(): raise ValueError('non-finite multipliers')
        if np.any(self.multipliers < config.multiplier_min-1e-7) or np.any(self.multipliers > config.multiplier_max+1e-7):
            raise ValueError('multipliers outside depression-only bounds')
        if min(self.generation,self.matches,self.update_events) < 0: raise ValueError('negative counters')
        if not self.character or not self.candidate_sha256 or not self.config_sha256: raise ValueError('state identity missing')


def initialize_state(*,character:str,n_candidates:int,candidate_sha256:str,config:ValencePlasticityConfig)->ValencePlasticityState:
    config.validate()
    state=ValencePlasticityState(str(character),np.ones(n_candidates,dtype=np.float32),0,0,0,str(candidate_sha256),config.fingerprint())
    state.validate(n_candidates,config)
    return state


def save_state(path:str|Path,state:ValencePlasticityState,config:ValencePlasticityConfig)->dict[str,Any]:
    path=Path(path); state.validate(len(state.multipliers),config); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('wb') as f: np.savez_compressed(f,multipliers=state.multipliers.astype(np.float32))
    tmp.replace(path)
    meta={
        'schema_version':STATE_SCHEMA,'model':'KC-MBON-valence-depression-v0','character':state.character,
        'generation':int(state.generation),'matches':int(state.matches),'update_events':int(state.update_events),
        'candidate_sha256':state.candidate_sha256,'config_sha256':state.config_sha256,
        'n_candidates':int(len(state.multipliers)),'multiplier_min':float(state.multipliers.min()),
        'multiplier_max':float(state.multipliers.max()),'multiplier_mean':float(state.multipliers.mean()),
        'depression_only':True,'reward_id':config.reward_id,
    }
    meta['state_sha256']=sha256_file(path)
    path.with_suffix(path.suffix+'.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return meta


def load_state(path:str|Path,*,expected_character:str,n_candidates:int,expected_candidate_sha256:str,config:ValencePlasticityConfig)->ValencePlasticityState:
    path=Path(path); meta_path=path.with_suffix(path.suffix+'.json')
    if not path.is_file() or not meta_path.is_file(): raise FileNotFoundError(path)
    meta=json.loads(meta_path.read_text(encoding='utf-8'))
    checks={
        'schema_version':STATE_SCHEMA,'model':'KC-MBON-valence-depression-v0','character':expected_character,
        'candidate_sha256':expected_candidate_sha256,'config_sha256':config.fingerprint(),'reward_id':config.reward_id,
    }
    for key,value in checks.items():
        if meta.get(key)!=value: raise ValueError(f'valence plasticity state {key} mismatch')
    if meta.get('state_sha256')!=sha256_file(path): raise ValueError('state checksum mismatch')
    with np.load(path,allow_pickle=False) as z: multipliers=z['multipliers'].astype(np.float32,copy=True)
    state=ValencePlasticityState(expected_character,multipliers,int(meta['generation']),int(meta['matches']),int(meta['update_events']),expected_candidate_sha256,config.fingerprint())
    state.validate(n_candidates,config); return state


def update_eligibility(previous:np.ndarray,pre_counts:np.ndarray,post_counts:np.ndarray,config:ValencePlasticityConfig)->np.ndarray:
    config.validate()
    previous=np.asarray(previous,dtype=np.float64); pre_counts=np.asarray(pre_counts,dtype=np.float64); post_counts=np.asarray(post_counts,dtype=np.float64)
    if previous.shape!=pre_counts.shape or previous.shape!=post_counts.shape: raise ValueError('eligibility input shape mismatch')
    if np.any(previous<0) or np.any(pre_counts<0) or np.any(post_counts<0): raise ValueError('eligibility inputs must be non-negative')
    coactivity=np.minimum(pre_counts*post_counts,config.pair_count_cap)
    out=previous*config.eligibility_decay+coactivity
    if not np.isfinite(out).all(): raise ValueError('non-finite eligibility')
    return out


def apply_modulatory_signal(state:ValencePlasticityState,eligibility:np.ndarray,signal:float,channels:np.ndarray,config:ValencePlasticityConfig)->dict[str,Any]:
    config.validate(); signal=float(signal)
    if not np.isfinite(signal): raise ValueError('non-finite modulatory signal')
    eligibility=np.asarray(eligibility,dtype=np.float64); channels=np.asarray(channels)
    if eligibility.shape!=state.multipliers.shape or channels.shape!=state.multipliers.shape: raise ValueError('candidate vector shape mismatch')
    if np.any(eligibility<0) or not np.isfinite(eligibility).all(): raise ValueError('invalid eligibility')
    before=state.multipliers.astype(np.float64,copy=True)
    if signal>0: target=config.positive_target
    elif signal<0: target=config.negative_target
    else: target=None
    target_mask=(channels==target) if target else np.zeros(len(channels),dtype=bool)
    eligible=eligibility[target_mask & (eligibility>0)]
    scale=float(np.percentile(eligible,config.normalization_percentile)) if len(eligible) else 0.0
    changed=0
    if target is not None and scale>0:
        normalized=np.zeros_like(eligibility)
        normalized[target_mask]=np.clip(eligibility[target_mask]/scale,0.0,1.0)
        factor=np.exp(-config.learning_rate*abs(signal)*normalized)
        after=before*factor
        after=np.clip(after,config.multiplier_min,config.multiplier_max)
        state.multipliers=after.astype(np.float32)
        changed=int(np.count_nonzero(np.abs(after-before)>1e-12))
        state.update_events += 1
    return {
        'signal':signal,'target_channel':target,'eligibility_scale':scale,
        'target_edges':int(target_mask.sum()),'eligible_target_edges':int(np.count_nonzero(target_mask & (eligibility>0))),
        'changed_edges':changed,'multiplier_min_before':float(before.min()),'multiplier_min_after':float(state.multipliers.min()),
        'multiplier_mean_after':float(state.multipliers.mean()),'potentiated_edges':int(np.count_nonzero(state.multipliers.astype(np.float64)>before+1e-12)),
    }


def finish_match(state:ValencePlasticityState)->None:
    state.matches += 1; state.generation += 1
