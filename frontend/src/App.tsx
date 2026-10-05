import { useEffect, useState } from 'react'

type Scenario = { id: string; title: string; description: string; service: string; start_time: string }
type Evidence = { id: string; timestamp: string; source: string; excerpt: string; service: string }
type Finding = { agent: string; summary: string; evidence: Evidence[] }
type Report = { root_cause: string; confidence: number; summary: string; hypotheses: {cause:string;confidence:number;reason:string}[]; timeline:Evidence[]; evidence:Evidence[]; agent_results:Finding[]; recommendations:string[]; mode:string; safety:string; llm_explanation?: {available:boolean; text:string} }

const label = (s: string) => s.replaceAll('_', ' ')

export default function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [selected, setSelected] = useState('')
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(false)
  const [useLlm, setUseLlm] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { fetch('/api/scenarios').then(r => r.json()).then((data: Scenario[]) => { setScenarios(data); setSelected(data[0]?.id ?? '') }).catch(() => setError('API unavailable. Start FastAPI on port 8000.')) }, [])

  async function investigate() {
    if (!selected) return
    setLoading(true); setError(''); setReport(null)
    try {
      const response = await fetch('/api/investigations', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({scenario_id:selected,use_llm:useLlm}) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail ?? 'Investigation failed')
      setReport(data)
    } catch (e) { setError(e instanceof Error ? e.message : 'Investigation failed') } finally { setLoading(false) }
  }

  return <main className="shell">
    <header className="top"><div className="brand"><div className="mark">IC</div><div><span className="eyebrow">SRE TOOLKIT / DEMO ENVIRONMENT</span><h1>Incident Response Copilot</h1></div></div><div className="live"><i/> Synthetic data · read only</div></header>
    <section className="intro"><div><div className="pill">MULTI-AGENT INVESTIGATION</div><h2>Evidence first.<br/><em>Root cause, clearly.</em></h2><p>Coordinate specialist agents to correlate logs, metrics, and releases into a traceable incident report.</p></div><div className="flow"><div className="flow-node"><b>◉</b> Coordinator</div><div className="branches"><span>↙</span><span>↓</span><span>↘</span></div><div className="agents"><div>▤<small>Logs</small></div><div>⌁<small>Metrics</small></div><div>↥<small>Deployments</small></div></div><div className="protocols"><span>A2A DELEGATION</span><span>MCP TOOLS</span></div></div></section>
    <section className="workspace"><div className="section-title"><div><span className="eyebrow">01 / SELECT SCENARIO</span><h3>Choose an incident to investigate</h3></div><span className="tag">3 REPRODUCIBLE CASES</span></div>
      <div className="scenario-grid">{scenarios.map((s,i)=><button className={`scenario ${selected===s.id?'selected':''}`} key={s.id} onClick={()=>{setSelected(s.id);setReport(null)}}><span className="scenario-num">0{i+1}</span><span className="scenario-service">{s.service}</span><strong>{s.title}</strong><small>{s.description}</small><span className="scenario-time">{new Date(s.start_time).toLocaleString()}</span></button>)}</div>
      <div className="action-row"><div><div className="hint"><span className="spark">✳</span> Agents investigate independently, then correlate evidence.</div><label className="llm-toggle"><input type="checkbox" checked={useLlm} onChange={e=>setUseLlm(e.target.checked)}/> Optional LLM explanation (requires API key)</label></div><button className="run" onClick={investigate} disabled={!selected||loading}>{loading?<><span className="spinner"/> Investigating…</>:<>Run investigation <span>→</span></>}</button></div>
    </section>
    {error&&<div className="error">{error}</div>}
    {loading&&<section className="working"><span className="spinner"/> Asking Log Analyst, Metrics Analyst, and Deployment Analyst over A2A…</section>}
    {report&&<section className="results"><div className="section-title"><div><span className="eyebrow">02 / INVESTIGATION REPORT</span><h3>Findings &amp; evidence</h3></div><span className="tag green">{report.mode}</span></div>
      <div className="finding"><div className="finding-icon">⌁</div><div className="finding-main"><span className="eyebrow">LEADING HYPOTHESIS · {Math.round(report.confidence*100)}% CONFIDENCE</span><h3>{label(report.root_cause)}</h3><p>{report.summary}</p></div><span className="confidence">{Math.round(report.confidence*100)}%</span></div>
      <div className="result-grid"><article className="panel"><h4>Agent findings <span>{report.agent_results.length}</span></h4>{report.agent_results.map(a=><div className="agent-row" key={a.agent}><div className="agent-icon">{a.agent==='logs'?'▤':a.agent==='metrics'?'⌁':a.agent==='deployments'?'↥':a.agent==='investigator'?'⌕':'≡'}</div><div><strong>{label(a.agent)} agent</strong><p>{a.summary}</p></div><span className="evidence-count">{a.evidence.length} refs</span></div>)}</article>
      <article className="panel"><h4>Ranked hypotheses</h4>{report.hypotheses.slice(0,3).map((h,i)=><div className="hypothesis" key={h.cause}><div className="hypothesis-head"><strong>{i+1}. {label(h.cause)}</strong><span>{Math.round(h.confidence*100)}%</span></div><div className="bar"><i style={{width:`${h.confidence*100}%`}}/></div><p>{h.reason}</p></div>)}</article></div>
      <article className="panel evidence-panel"><h4>Correlated evidence <span>{report.evidence.length} items</span></h4><div className="timeline">{report.timeline.map(ev=><div className="evidence" key={ev.id}><span className={`source ${ev.source}`}>{ev.source}</span><time>{new Date(ev.timestamp).toLocaleTimeString()}</time><code>{ev.id}</code><p>{ev.excerpt}</p></div>)}</div></article>
      <div className="recommendations"><div><span className="eyebrow">SUGGESTED NEXT CHECKS</span>{report.recommendations.map((r,i)=><p key={r}><b>0{i+1}</b>{r}</p>)}</div></div>
      {report.llm_explanation&&<div className="llm-explanation"><span className="eyebrow">OPTIONAL NATURAL-LANGUAGE EXPLANATION</span><p>{report.llm_explanation.text}</p></div>}
      <p className="safety">ⓘ {report.safety}</p>
    </section>}
    <footer><span>INCIDENT RESPONSE COPILOT <b>·</b> PORTFOLIO DEMO</span><span>MCP tools are read-only <b>·</b> Remediation is never automated</span></footer>
  </main>
}
