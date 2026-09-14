import { ArenaClient } from './arena-client';

export const dynamic = 'force-dynamic';

export default function LiveArenaPage() {
  // CI replaces only cloud allocation/address discovery, not game, neural,
  // physics or media data. Never accept a browser query parameter as a target.
  const origin = process.env.CONNECTOME_CI_RUNTIME_ORIGIN?.trim() || '';
  if (origin) {
    if (process.env.CI !== 'true' || process.env.VERCEL) {
      throw new Error('CI runtime origin is forbidden outside standalone CI');
    }
    if (origin !== 'http://127.0.0.1:18000') {
      throw new Error('CI runtime must use the fixed loopback origin');
    }
  }
  return <ArenaClient runtimeOrigin={origin} />;
}
