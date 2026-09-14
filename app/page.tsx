import { LiveClient } from "./live-client";
import './training/training.css';
export default function Home() {
  return <><aside className="training-promo" aria-label="Current paired-training experiment"><span>New experiment: paired neural training · verified cycles, not automatic progress</span><a href="/training">Open the Training Colosseum ↗</a></aside><LiveClient /></>;
}
