import { NextResponse } from 'next/server';
import { parseTrainingReport } from '../../../lib/paired-training-contract';

export const dynamic = 'force-dynamic';
const POINTER = 'https://github.com/Unjuno/connectome-fighter/releases/download/paired-training-latest/latest.json';
export async function GET() {
  try {
    const response = await fetch(`${POINTER}?t=${Date.now()}`, {
      cache: 'no-store', signal: AbortSignal.timeout(10000),
      headers: { 'User-Agent': 'connectome-paired-training-view/1' },
    });
    if (response.status === 404) return NextResponse.json({ ready: false, status: 'awaiting-first-cycle', latest: null }, { headers: { 'Cache-Control': 'no-store' } });
    if (!response.ok) throw new Error(`Receipt HTTP ${response.status}`);
    const text = await response.text();
    if (text.length > 1024*1024) throw new Error('Receipt exceeds size limit');
    const latest = parseTrainingReport(JSON.parse(text));
    if (!latest) throw new Error('Receipt failed the paired-training contract');
    return NextResponse.json({ ready: true, status: 'completed-cycle', latest }, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return NextResponse.json({ ready: false, status: 'receipt-unavailable', latest: null }, { status: 503, headers: { 'Cache-Control': 'no-store' } });
  }
}
