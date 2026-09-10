import React, {createContext, useContext, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams} from 'react-router-dom';
import {ReactFlow, Background, Controls, MiniMap, Handle, Position, addEdge, useEdgesState, useNodesState, type Connection, type NodeProps} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {Activity, Bell, BookOpen, Bot, Check, ChevronRight, ClipboardCheck, FileText, LayoutDashboard, LogOut, Network, Play, Radar, Radio, Save, Shield, SlidersHorizontal, Trash2, Users, X} from 'lucide-react';
import './styles.css';
import './light.css';
import './sensor.css';

const API='/api';
type Role='ANALYST'|'STAFF'|'COMMANDER';
type Session={user_id:string;role:Role;area:string;permissions:string[]};
type Agent={id:string;name:string;role:Role;area:string;owner:string;lifecycle:string;version:number;definition:any;deletable?:boolean};
type Execution={id:string;agent_id:string;agent_name:string;role:Role;area:string;version:number;status:string;created_at:string;trigger_type?:string;source_report_id?:string;child_execution_id?:string;trace?:any[];approval?:any;reports?:any[];snapshot?:any};

async function api(path:string, options:RequestInit={}){const r=await fetch(API+path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});if(!r.ok){const d=await r.json().catch(()=>({detail:r.statusText}));throw new Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));}return r.json()}
async function markNotificationRead(notification:any,role:Role){if(notification.read_at)return notification.read_at;const result=await api('/notifications/'+notification.id+'/read',{method:'POST',headers:{'X-Demo-Role':role}});return result.read_at as string}
const SessionContext=createContext<{session:Session|null;login:(r:Role)=>Promise<void>;logout:()=>void}>({session:null,login:async()=>{},logout:()=>{}});
const roleName={ANALYST:'파주지역 분석관',STAFF:'정보·작전 참모',COMMANDER:'지휘관'};
const userName:Record<string,string>={'analyst.a12':'김분석 분석관','staff.ops':'이작전 참모','commander.demo':'박지휘 지휘관'};
const statusName:Record<string,string>={PUBLISHED:'게시됨',DRAFT:'초안',COMPLETED:'완료',REJECTED:'반려',RUNNING:'실행 중',WAITING_FOR_ANALYST_APPROVAL:'분석관 승인 대기',WAITING_FOR_STAFF_APPROVAL:'참모 승인 대기',SUCCEEDED:'완료',WAITING:'승인 대기',FAILED:'실패'};

function App(){const [session,setSession]=useState<Session|null>(()=>{try{const saved=JSON.parse(localStorage.getItem('session')||'null');if(saved?.area==='A-12')saved.area='경기도 파주시';if(saved?.area==='ALL')saved.area='접경지역 전체';return saved}catch{return null}});async function login(role:Role){const s=await api('/session',{method:'POST',body:JSON.stringify({role})});setSession(s);localStorage.setItem('session',JSON.stringify(s))}return <SessionContext.Provider value={{session,login,logout:()=>{setSession(null);localStorage.removeItem('session')}}}><BrowserRouter><Routes><Route path="/login" element={<Login/>}/><Route path="/*" element={session?<Shell/>:<Navigate to="/login"/>}/></Routes></BrowserRouter></SessionContext.Provider>}

function Login(){const {login}=useContext(SessionContext);const nav=useNavigate();const [role,setRole]=useState<Role>('ANALYST');return <main className="login"><div className="loginBrand"><div className="emblem"><Shield size={44}/></div><div><span>DEFENSE AI PLATFORM</span><h1>Workflow Builder</h1><p>지능형 국방 의사결정 워크플로</p></div></div><section className="loginCard"><div className="mock">DEMO · MOCK LOGIN</div><h2>임무 역할을 선택하세요</h2><p>선택한 역할에 맞춰 워크플로우와 데이터 접근 범위가 설정됩니다.</p><div className="roleCards">{(['ANALYST','STAFF','COMMANDER'] as Role[]).map((r,i)=><button key={r} className={role===r?'role active':'role'} onClick={()=>setRole(r)}><span className="roleIcon">{i===0?<Radar/>:i===1?<Network/>:<Users/>}</span><span><b>{roleName[r]}</b><small>{r==='ANALYST'?'파주시 감시 이벤트 분석 및 지역 보고':r==='STAFF'?'다지역 정보 종합 및 지휘관 보고':'승인된 최종 상황 보고 열람'}</small></span><span className="radio">{role===r&&<Check size={14}/>}</span></button>)}</div><button className="primary loginBtn" onClick={async()=>{await login(role);nav('/dashboard')}}>Workflow Builder 시작 <ChevronRight size={18}/></button><small className="security">훈련용 가상 데이터 · 모든 활동은 감사 기록에 저장됩니다</small></section></main>}

function BuilderEntry(){const {session}=useContext(SessionContext);if(session?.role==='COMMANDER')return <Navigate to="/dashboard" replace/>;return <Navigate to={session?.role==='STAFF'?'/agents/staff-synthesis/builder':'/agents/analyst-a12/builder'} replace/>}

function Shell(){
  const {session,login,logout}=useContext(SessionContext);
  const nav=useNavigate();
  const location=useLocation();
  if(!session)return null;
  const links=[['/dashboard',session.role==='COMMANDER'?'상황판':'대시보드',session.role==='COMMANDER'?Radar:LayoutDashboard],...(session.role!=='COMMANDER'?[['/builder','워크플로우 빌더',Network],['/agents','워크플로우 레지스트리',Bot],['/executions','실행 모니터링',Activity],['/situation','상황판',Radar]] as any:[]),['/manual','사용 매뉴얼',BookOpen],...(session.role==='ANALYST'?[['/sensor','센서 입력',Radio]] as any:[])];
  const isBuilderPath=location.pathname==='/builder'||/^\/agents\/[^/]+\/builder$/.test(location.pathname);
  return <div className="app"><header><div className="brand"><Shield/> <b>Agent&Workflow Builder</b><span>DEMO</span></div><div className="headRight"><NotificationBell session={session}/><select value={session.role} onChange={async e=>{await login(e.target.value as Role);nav('/dashboard')}}>{(['ANALYST','STAFF','COMMANDER'] as Role[]).map(r=><option key={r} value={r}>{roleName[r]}</option>)}</select><div className="avatar">{session.role[0]}</div><div><b>{roleName[session.role]}</b><small>{session.area==='접경지역 전체'?'접경지역 전체':session.area}</small></div><button className="iconBtn" onClick={()=>{logout();nav('/login')}}><LogOut size={17}/></button></div></header><aside><div className="scope"><small>현재 작전 구역</small><b><span className="online"/>{session.area==='접경지역 전체'?'전 지역 통합':session.area}</b></div><nav>{links.map(([to,label,Icon]:any)=><NavLink to={to} key={to} end={to==='/agents'||to==='/dashboard'||to==='/situation'} className={({isActive})=>((to==='/builder'&&isBuilderPath)||(to!=='/builder'&&isActive))?'active':undefined}><Icon size={18}/>{label}</NavLink>)}</nav><SystemStatus/></aside><div className="content"><Routes><Route path="/dashboard" element={<Dashboard/>}/><Route path="/builder" element={<BuilderEntry/>}/><Route path="/agents" element={<AgentRegistry/>}/><Route path="/agents/:id/builder" element={<Builder/>}/><Route path="/executions" element={<Executions/>}/><Route path="/executions/:id" element={<ExecutionDetail/>}/><Route path="/situation" element={session.role==='COMMANDER'?<Navigate to="/dashboard" replace/>:<SituationMap/>}/><Route path="/sensor" element={<SensorInput/>}/><Route path="/manual" element={<Manual/>}/><Route path="*" element={<Navigate to="/dashboard"/>}/></Routes></div></div>
}

function PageHead({eyebrow,title,children}:{eyebrow:string,title:string,children?:React.ReactNode}){return <div className="pageHead"><div><span>{eyebrow}</span><h1>{title}</h1></div><div>{children}</div></div>}
function Badge({value}:{value:string}){return <span className={'badge '+value.toLowerCase().replaceAll('_','-')}>{statusName[value]||value}</span>}

function Dashboard(){const {session}=useContext(SessionContext);const nav=useNavigate();const [data,setData]=useState<any>();const [agents,setAgents]=useState<Agent[]>([]);const [execs,setExecs]=useState<Execution[]>([]);useEffect(()=>{if(!session)return;Promise.all([api('/dashboard?role='+session.role),api('/agents?role='+session.role,{headers:{'X-Demo-Role':session.role}}),api('/executions?role='+session.role)]).then(([d,a,e])=>{setData(d);setAgents(a);setExecs(e)})},[session]);if(!session)return null;if(session.role==='COMMANDER')return <SituationMap commanderHome/>;return <><PageHead eyebrow={`${roleName[session.role]} · ${session.area}`} title={false?'지휘 상황 개요':'워크플로우 운영 대시보드'}>{true&&agents[0]&&<button className="primary" onClick={()=>nav('/agents/'+agents[0].id+'/builder')}><Bot size={17}/> 워크플로우 열기</button>}</PageHead>{data?.pending_count>0&&<ApprovalAlert count={data.pending_count}/>}<div className="metrics"><Metric label="운영 워크플로우" value={data?.agent_count||0} icon={<Bot/>}/><Metric label="활성 실행" value={data?.active_count||0} icon={<Activity/>}/><Metric label="승인 대기" value={data?.pending_count||0} icon={<ClipboardCheck/>}/><Metric label="시스템 상태" value="정상" icon={<Shield/>}/></div><div className="dashboardGrid"><section className="panel"><div className="panelTitle"><h2>{false?'최근 완료 실행':'내 워크플로우'}</h2><button className="textBtn" onClick={()=>nav(false?'/situation':'/agents')}>전체 보기 <ChevronRight size={15}/></button></div>{true?agents.map(a=><article className="agentCard" key={a.id}><div className="agentMark"><Network/></div><div className="grow"><div><Badge value={a.lifecycle}/><span className="muted">v{a.version} · {a.area}</span></div><h3>{a.name}</h3><p>{a.role==='ANALYST'?'센서 이벤트를 분석하고 지역 위협 보고서를 생성합니다.':'승인된 지역 보고를 종합하여 지휘관 상황 보고를 생성합니다.'}</p><div className="chips"><span>Trigger</span><b>{a.role==='ANALYST'?'Sensor Event':'Approved Report'}</b></div></div><button className="secondary" onClick={()=>nav('/agents/'+a.id+'/builder')}>빌더 열기</button></article>):execs.slice(0,4).map(e=><RunRow key={e.id} e={e}/>)}</section><section className="panel"><div className="panelTitle"><h2>승인 및 알림</h2><Bell size={18}/></div>{data?.notifications?.length?data.notifications.map((n:any)=><button className={'notification '+(n.read_at?'read':'unread')} key={n.id} onClick={async()=>{const wasUnread=!n.read_at;const readAt=await markNotificationRead(n,session.role);if(wasUnread)setData((current:any)=>({...current,unread_count:Math.max(0,(current.unread_count||0)-1),notifications:current.notifications.map((item:any)=>item.id===n.id?{...item,read_at:readAt}:item)}));nav('/executions/'+n.execution_id)}}><span className="pulse"/><div><b>{n.title}</b><p>{n.body}</p><small>{n.execution_id} · {n.read_at?'확인함':'새 알림'}</small></div><ChevronRight/></button>):<Empty text="새로운 알림이 없습니다."/>}</section></div></>}
function Metric({label,value,icon}:{label:string;value:any;icon:React.ReactNode}){return <div className="metric"><span>{icon}</span><div><small>{label}</small><b>{value}</b></div></div>}
function RunRow({e}:{e:Execution}){const nav=useNavigate();return <button className="runRow" onClick={()=>nav('/executions/'+e.id)}><span className="runIcon"><Activity/></span><div><b>{e.agent_name}</b><small>{e.id} · {new Date(e.created_at).toLocaleString('ko')}</small></div><Badge value={e.status}/><ChevronRight/></button>}

function NotificationBell({session}:{session:Session}){
  const nav=useNavigate();const [count,setCount]=useState(0);
  useEffect(()=>{const load=()=>api('/dashboard?role='+session.role).then(x=>setCount(x.unread_count||0)).catch(()=>{});load();const timer=setInterval(load,5000);return()=>clearInterval(timer)},[session.role]);
  return <button className={'iconBtn notificationBell '+(count?'hasAlert':'')} title={count?'읽지 않은 알림 '+count+'건':'새 알림 없음'} onClick={()=>nav('/dashboard')}><Bell size={18}/>{count>0&&<b>{count}</b>}</button>
}

function ApprovalAlert({count}:{count:number}){
  const nav=useNavigate();
  return <button className="approvalAlert" onClick={()=>nav('/executions')}><span><Bell/><i/></span><div><small>즉시 확인 필요</small><b>승인을 기다리는 보고서가 {count}건 있습니다.</b><p>검토 후 승인해야 다음 보고 단계가 진행됩니다.</p></div><strong>승인 요청 열기 <ChevronRight/></strong></button>
}
function Empty({text}:{text:string}){return <div className="empty"><Radar/><p>{text}</p></div>}

function Registry(){const {session}=useContext(SessionContext);const [agents,setAgents]=useState<Agent[]>([]);const nav=useNavigate();useEffect(()=>{session&&api('/agents?role='+session.role,{headers:{'X-Demo-Role':session.role}}).then(setAgents)},[session]);return <><PageHead eyebrow="WORKFLOW MANAGEMENT" title="워크플로우 목록"><button className="primary"><Bot size={17}/> 새 워크플로우</button></PageHead><section className="panel tablePanel"><div className="filters"><div className="search">⌕ <input placeholder="워크플로우 이름 검색"/></div><button className="secondary"><SlidersHorizontal/> 필터</button></div><table><thead><tr><th>워크플로우</th><th>Owner / 역할</th><th>Trigger</th><th>버전</th><th>상태</th><th></th></tr></thead><tbody>{agents.map(a=><tr key={a.id}><td><b>{a.name}</b><small>{a.area} · 기본 제공 템플릿</small></td><td>{userName[a.owner]||a.owner}<small>{roleName[a.role]}</small></td><td>{a.role==='ANALYST'?'Sensor Event':'Approved Report'}</td><td>v{a.version}</td><td><Badge value={a.lifecycle}/></td><td><button className="secondary" onClick={()=>nav('/agents/'+a.id+'/builder')}>Builder <ChevronRight/></button></td></tr>)}</tbody></table></section></>}

const NODE_IO:Record<string,{input:string[];output:string[]}>={
  sensor:{input:['센서 신호'],output:['event']},filter:{input:['event'],output:['filtered','event']},
  context:{input:['area','event'],output:['evidence_ids']},threat:{input:['event','evidence_ids'],output:['threat_level','summary','draft']},
  generator:{input:['threat_level','summary'],output:['draft']},approval:{input:['draft'],output:['approval_decision','edited_content']},
  send:{input:['draft','approval_decision'],output:['report_id']},report_trigger:{input:['승인 보고 이벤트'],output:['event']},
  reports:{input:['event'],output:['source_report_ids']},synthesis:{input:['source_report_ids'],output:['threat_level','summary','priority_areas','draft']},
};
const GROUP_META:Record<string,{name:string;description:string}>={trigger:{name:'시작',description:'워크플로를 시작하는 입력'},data:{name:'정보 조회',description:'분석에 필요한 근거 수집'},ai:{name:'AI 판단·초안',description:'LLM 분석과 보고서 초안 생성'},control:{name:'검토·제어',description:'조건 검사와 사람 승인'},action:{name:'결과 발행',description:'승인 결과를 시스템에 반영'}};
function FlowNode({data,selected}:NodeProps){const d=data as any;const st=d.status;return <div className={'flowNode '+(selected?'selected ':'')+(st?st.toLowerCase():'')}><Handle type="target" position={Position.Left}/><span className="nodeIcon"><Network size={16}/></span><div><small>{GROUP_META[d.group]?.name||d.group}</small><b>{d.label}</b></div>{st&&<i>{st==='SUCCEEDED'?<Check/>:st==='WAITING'?<ClipboardCheck/>:<Activity/>}</i>}<Handle type="source" position={Position.Right}/></div>}
const nodeTypes={default:FlowNode};
function Builder(){const {id}=useParams();const {session}=useContext(SessionContext);const nav=useNavigate();const [agent,setAgent]=useState<Agent>();const [catalog,setCatalog]=useState<any[]>([]);const [models,setModels]=useState<any[]>([]);const [nodes,setNodes,onNodesChange]=useNodesState<any>([]);const [edges,setEdges,onEdgesChange]=useEdgesState<any>([]);const [selected,setSelected]=useState<any>();const [dirty,setDirty]=useState(false);const [message,setMessage]=useState('');const [run,setRun]=useState<Execution>();useEffect(()=>{if(!id||!session)return;Promise.all([api('/agents/'+id,{headers:{'X-Demo-Role':session!.role}}),api('/nodes?role='+session!.role,{headers:{'X-Demo-Role':session!.role}}),api('/models',{headers:{'X-Demo-Role':session!.role}})]).then(([a,c,m])=>{setAgent(a);setCatalog(c);setModels(m);setNodes(a.definition.nodes.map((n:any)=>({...n,type:'default',data:{label:n.label,group:n.group,config:n.config,capabilityType:n.type}})));setEdges(a.definition.edges);})},[id,session]);useEffect(()=>{if(!run||!id)return;const t=setInterval(()=>api('/executions/'+run.id).then(setRun),1500);return()=>clearInterval(t)},[run?.id]);if(!agent||!session)return <div className="loading">Builder 불러오는 중…</div>;const definition=()=>({...agent.definition,nodes:nodes.map(n=>({id:n.id,type:n.data.capabilityType||n.id,label:n.data.label,group:n.data.group,position:n.position,config:n.data.config||{}})),edges});async function save(){await api('/agents/'+id,{method:'PUT',headers:{'X-Demo-Role':session!.role},body:JSON.stringify({definition:definition()})});setDirty(false);setMessage('초안이 저장되었습니다.')}async function validate(){const r=await api('/agents/'+id+'/validate',{method:'POST',headers:{'X-Demo-Role':session!.role},body:JSON.stringify({definition:definition()})});setMessage(r.valid?'검증 통과 · 실행 가능한 워크플로입니다.':r.errors.join(' · '))}async function publish(){if(dirty)await save();const r=await api('/agents/'+id+'/publish',{method:'POST',headers:{'X-Demo-Role':session!.role}});setAgent({...agent!,lifecycle:'PUBLISHED',version:r.version});setMessage(`v${r.version} 게시 완료`)}async function test(){if(dirty)await save();const r=await api('/agents/'+id+'/test',{method:'POST',headers:{'X-Demo-Role':session!.role}});setRun(await api('/executions/'+r.execution_id))}const traceMap=Object.fromEntries((run?.trace||[]).map(t=>[t.node_id,t.status]));const displayNodes=nodes.map(n=>({...n,data:{...n.data,status:traceMap[n.id]}}));return <div className="builderPage"><div className="builderHead"><div><span>워크플로우 빌더 / {roleName[agent.role]}</span><h1>{agent.name}</h1><div><Badge value={agent.lifecycle}/><small>v{agent.version} · {dirty?'저장되지 않은 변경':'저장됨'}</small></div></div><div className="builderActions"><button className="secondary" onClick={save}><Save/> 저장</button><button className="secondary" onClick={validate}><Check/> 검증</button><button className="primary" onClick={publish}>게시</button></div></div>{message&&<div className="toast"><Check/> {message}<button onClick={()=>setMessage('')}><X/></button></div>}<div className="builder"><aside className="palette"><h3>노드 팔레트</h3>{['trigger','data','ai','control','action'].map(group=><div key={group}><small>{GROUP_META[group]?.name||group}</small><em>{GROUP_META[group]?.description}</em>{catalog.filter(n=>n.group===group).map(n=><button key={n.type} onClick={()=>{const newN={id:n.type+'-'+Date.now(),type:'default',position:{x:200,y:160},data:{label:n.label,group:n.group,config:{...(n.config||{})},capabilityType:n.type}};setNodes(ns=>[...ns,newN]);setDirty(true)}}><span className={'dot '+group}/>{n.label}<b>+</b></button>)}</div>)}</aside><main className="canvas"><ReactFlow nodes={displayNodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={(c)=>{onNodesChange(c);if(c.some(x=>x.type!=='select'))setDirty(true)}} onEdgesChange={(c)=>{onEdgesChange(c);setDirty(true)}} onConnect={(c:Connection)=>{setEdges(es=>addEdge(c,es));setDirty(true)}} onNodeClick={(_,n)=>setSelected(n)} connectionRadius={30} deleteKeyCode={["Backspace","Delete"]} fitView><Background color="#cbd5e1" gap={24}/><Controls/><MiniMap pannable zoomable/></ReactFlow><div className="canvasLabel"><span className="online"/> 워크플로 편집 캔버스 · 연결점을 드래그해 직접 연결하세요</div></main><aside className="config"><h3>노드 설정</h3>{selected?<NodeSettings node={selected} models={models} onChange={(next:any)=>{setSelected(next);setNodes(ns=>ns.map(n=>n.id===next.id?next:n));setDirty(true)}} onDelete={()=>{setNodes(ns=>ns.filter(n=>n.id!==selected.id));setEdges(es=>es.filter(e=>e.source!==selected.id&&e.target!==selected.id));setSelected(undefined);setDirty(true)}}/>:<><div className="configType">워크플로우 설정</div><label>감시 지역<input value={agent.area} readOnly/></label><label>Provider<input value={agent.definition.model.provider} readOnly/></label><label>모델 ID<input value={agent.definition.model.model_id} readOnly/></label><div className="info">API credential는 backend 환경에만 저장됩니다.</div></>}</aside></div><div className="testBar"><button className="run" onClick={test} disabled={!!run&&run.status.includes('RUNNING')}><Play/> 시험 실행</button><div><small>예시 입력</small><b>파주-감시센서-03 · 경기도 파주시 / 이동체 감지 / 0.94</b></div>{run?<><div className="runStatus"><small>실행</small><b>{run.id}</b></div><Badge value={run.status}/><button className="secondary" onClick={()=>nav('/executions/'+run.id)}>실행 열기 <ChevronRight/></button></>:<span className="muted">저장된 스냅샷으로 실제 런타임을 시작합니다.</span>}</div>{run&&<div className="traceStrip">{run.trace?.map((t,i)=><div key={t.id} className={'traceStep '+t.status.toLowerCase()}><span>{i+1}</span><div><small>{t.status}</small><b>{t.label}</b><em>{t.output_summary}</em></div></div>)}</div>}</div>}

function Executions(){const {session}=useContext(SessionContext);const [items,setItems]=useState<Execution[]>([]);useEffect(()=>{if(!session)return;const load=()=>api('/executions?role='+session.role).then(setItems);load();const t=setInterval(load,2000);return()=>clearInterval(t)},[session]);return <><PageHead eyebrow="RUNTIME OBSERVABILITY" title="실행 모니터링"/><section className="panel tablePanel"><div className="filters"><div className="search">⌕ <input placeholder="Execution ID 검색"/></div><button className="secondary"><SlidersHorizontal/> 상태 필터</button></div><table><thead><tr><th>Execution</th><th>워크플로우 / 버전</th><th>시작 시각</th><th>상태</th><th></th></tr></thead><tbody>{items.map(e=><tr key={e.id}><td><b className="mono">{e.id}</b><small>{e.trigger_type}</small></td><td>{e.agent_name}<small>v{e.version} · {e.role}</small></td><td>{new Date(e.created_at).toLocaleString('ko')}</td><td><Badge value={e.status}/></td><td><NavLink className="secondary buttonLink" to={'/executions/'+e.id}>상세 <ChevronRight/></NavLink></td></tr>)}</tbody></table></section></>}

function ExecutionDetail(){const {id}=useParams();const {session}=useContext(SessionContext);const [e,setE]=useState<Execution>();const [edit,setEdit]=useState(false);const [draft,setDraft]=useState('');const [error,setError]=useState('');const nav=useNavigate();const load=()=>id&&api('/executions/'+id).then((x)=>{setE(x);setDraft(x.approval?.draft||'')});useEffect(()=>{load();const t=setInterval(load,1800);return()=>clearInterval(t)},[id]);if(!e||!session)return <div className="loading">실행 상태 복구 중…</div>;const nodeStatus=Object.fromEntries((e.trace||[]).map(t=>[t.node_id,t.status]));const def=e.snapshot;const nodes=(def?.nodes||[]).map((n:any)=>({...n,type:'default',data:{label:n.label,group:n.group,status:nodeStatus[n.id],capabilityType:n.type}}));async function decide(decision:string){try{await api('/approvals/'+e!.approval.id+'/decision',{method:'POST',headers:{'X-Demo-Role':session!.role},body:JSON.stringify({decision,content:decision==='EDIT_APPROVE'?draft:undefined})});setEdit(false);load()}catch(x:any){setError(x.message)}}const canReview=e.approval?.status==='PENDING'&&e.approval.reviewer_role===session!.role;const evidence=e.role==='ANALYST'?['OBS-A12-017 · 24시간 이동 패턴','OBS-A12-021 · 열원 관측','CTX-WX-003 · 기상 가시성']:['신규 파주시 승인 보고','연천군 보고 · 데모 기본자료','철원군 보고 · 데모 기본자료'];const aiTrace=e.trace?.find(t=>t.node_id==='threat'||t.node_id==='synthesis');const threatLevel=aiTrace?.output_summary?.split(' · ')[0]||'분석 완료';const threatSummary=aiTrace?.output_summary?.split(' · ').slice(1).join(' · ')||'LLM 분석 결과를 확인하세요.';return <><PageHead eyebrow="EXECUTION DETAIL" title={e.id}><div className="headButtons"><Badge value={e.status}/>{e.child_execution_id&&<button className="secondary" onClick={()=>nav('/executions/'+e.child_execution_id)}>연결된 Staff 실행 <ChevronRight/></button>}</div></PageHead><div className="executionGrid"><section className="panel execGraph"><div className="panelTitle"><div><h2>{e.agent_name}</h2><small>PINNED SNAPSHOT · v{e.version} · {e.role} / {e.area}</small></div></div><div className="readFlow"><ReactFlow nodes={nodes} edges={def?.edges||[]} nodeTypes={nodeTypes} fitView nodesDraggable={false} nodesConnectable={false}><Background color="#cbd5e1" gap={24}/><Controls/></ReactFlow></div></section><section className="panel tracePanel"><div className="panelTitle"><h2>실행 추적</h2><span className="live"><span className="online"/> LIVE</span></div><div className="timeline">{e.trace?.map((t,i)=><div className={'timelineItem '+t.status.toLowerCase()} key={t.id}><span>{t.status==='SUCCEEDED'?<Check/>:t.status==='WAITING'?<ClipboardCheck/>:<Activity/>}</span><div><small>STEP {String(i+1).padStart(2,'0')} · {t.status}</small><b>{t.label}</b>{t.input_summary&&<p className="traceIo"><b>입력</b> {t.input_summary}</p>}{t.output_summary&&<p className="traceIo"><b>출력</b> {t.output_summary}</p>}<em>{new Date(t.started_at).toLocaleTimeString('ko')}</em></div></div>)}</div></section></div>{e.approval?.status==='PENDING'&&<div className="drawerBackdrop"><aside className="approvalDrawer"><div className="drawerHead"><div><span>HUMAN IN THE LOOP</span><h2>{e.approval.reviewer_role==='ANALYST'?'분석관':'참모'} 승인 필요</h2><small>{e.id} · 체크포인트에서 일시 정지됨</small></div><button onClick={()=>nav('/executions')}><X/></button></div><div className="drawerBody"><div className="threat"><span>종합 위협 수준</span><b>{threatLevel}</b><small>{e.area} · 승인 전 초안</small></div><h3>AI 분석 요약</h3><p>{threatSummary}</p><h3>근거 및 출처</h3><div className="evidence">{evidence.map((x,i)=><span key={i}><FileText/>{x}</span>)}</div><h3>보고서 초안</h3>{edit?<textarea className="draftEditor" value={draft} onChange={x=>setDraft(x.target.value)}/>:<div className="draft">{draft}</div>}{error&&<p className="error">{error}</p>}</div><div className="drawerFoot">{canReview?<><button className="danger" onClick={()=>decide('REJECT')}>반려</button><button className="secondary" onClick={()=>setEdit(!edit)}>{edit?'편집 취소':'수정'}</button><button className="primary" onClick={()=>decide(edit?'EDIT_APPROVE':'APPROVE')}><Check/> {edit?'수정 내용 승인':'승인 및 실행 재개'}</button></>:<div className="info">현재 역할에는 이 승인 요청을 처리할 권한이 없습니다.</div>}</div></aside></div>}</>}

function Situation(){const {session}=useContext(SessionContext);const [reports,setReports]=useState<any[]>([]);const [selected,setSelected]=useState<any>();useEffect(()=>{session&&api('/reports?role='+session.role).then(setReports)},[session]);const areas=session?.role==='ANALYST'?['경기도 파주시']:['경기도 파주시','경기도 연천군','강원특별자치도 철원군'];return <><PageHead eyebrow="COMMON OPERATING PICTURE" title="상황판"><span className="live"><span className="online"/> 승인 데이터 기준</span></PageHead><div className="sectorGrid">{areas.map(area=>{const r=reports.find(x=>x.area===area);return <article className="sector" key={area}><div><small>지역</small><h2>{area}</h2></div><Badge value={r?.threat||'LOW'}/><div className="radarViz"><span/><i/><b/></div><p>최근 승인 보고</p><strong>{r?.title||'보고 없음'}</strong><small>{r?new Date(r.approved_at).toLocaleString('ko'):'-'}</small></article>})}</div><section className="panel"><div className="panelTitle"><h2>승인된 보고서</h2><span>{reports.length} reports</span></div><div className="reportGrid">{reports.map(r=><button className="reportCard" key={r.id} onClick={()=>setSelected(r)}><div><FileText/><Badge value={r.threat}/></div><h3>{r.title}</h3><p>{r.content}</p><small>{r.id} · {r.approved_by}{r.fixture&&<b> 데모 기본자료</b>}</small></button>)}</div></section>{selected&&<div className="modalBackdrop" onClick={()=>setSelected(null)}><article className="reportModal" onClick={x=>x.stopPropagation()}><button className="close" onClick={()=>setSelected(null)}><X/></button><span>APPROVED {selected.kind} REPORT</span><h1>{selected.title}</h1><div className="reportMeta"><Badge value={selected.threat}/><b>{selected.area}</b><small>{new Date(selected.approved_at).toLocaleString('ko')}</small></div><h3>승인 내용</h3><p className="reportContent">{selected.content}</p><h3>보고 계보</h3><div className="lineage"><span>실행</span><b>{selected.source_execution_id||'External demo fixture'}</b><span>Approver</span><b>{selected.approved_by}</b>{selected.source_report_ids?.map((x:string)=><React.Fragment key={x}><span>Source</span><b>{x}</b></React.Fragment>)}</div></article></div>}</>}

const MAP_AREAS={
  '경기도 파주시':{lat:37.8897,lon:126.7660,bbox:'126.64,37.73,127.02,38.08'},
  '경기도 연천군':{lat:38.0964,lon:127.0748,bbox:'126.83,37.91,127.30,38.25'},
  '강원특별자치도 철원군':{lat:38.1467,lon:127.3134,bbox:'127.04,37.98,127.61,38.34'},
} as const;

function AgentRegistry(){
  const {session}=useContext(SessionContext);
  const nav=useNavigate();
  const [agents,setAgents]=useState<Agent[]>([]);
  const [creating,setCreating]=useState(false);
  const [form,setForm]=useState({name:'',description:'',template:'BLANK'});
  const [error,setError]=useState('');
  const load=()=>session&&api('/agents?role='+session.role,{headers:{'X-Demo-Role':session.role}}).then(setAgents);
  useEffect(()=>{load()},[session]);
  if(session?.role==='COMMANDER')return <Navigate to="/dashboard"/>;
  async function create(){
    if(!session||!form.name.trim())return setError('워크플로우 이름을 입력하세요.');
    try{
      const result=await api('/agents',{method:'POST',headers:{'X-Demo-Role':session.role},body:JSON.stringify({
        ...form,role:session.role,area:session.role==='ANALYST'?'경기도 파주시':'접경지역 전체'
      })});
      nav('/agents/'+result.id+'/builder');
    }catch(e:any){setError(e.message)}
  }
  async function remove(agent:Agent){
    if(!session||!agent.deletable||!window.confirm(`'${agent.name}' 워크플로우를 삭제하시겠습니까?\n기존 실행 기록은 유지됩니다.`))return;
    try{await api('/agents/'+agent.id,{method:'DELETE',headers:{'X-Demo-Role':session.role}});await load()}
    catch(e:any){setError(e.message)}
  }
  return <>
    <PageHead eyebrow="내 워크플로우 관리" title="워크플로우 레지스트리"><button className="primary" onClick={()=>setCreating(true)}><Bot size={17}/> 새 워크플로우</button></PageHead>
    <section className="panel tablePanel"><div className="filters"><div className="search">⌕ <input placeholder="워크플로우 이름 검색"/></div><button className="secondary"><SlidersHorizontal/> 필터</button></div><table><thead><tr><th>워크플로우</th><th>소유자 / 역할</th><th>버전</th><th>상태</th><th/></tr></thead><tbody>{agents.map(a=><tr key={a.id}><td><b>{a.name}</b><small>{a.area}</small></td><td>{userName[a.owner]||a.owner}<small>{roleName[a.role]}</small></td><td>{a.version?`v${a.version}`:'미게시'}</td><td><Badge value={a.lifecycle}/></td><td><div className="registryActions"><button className="secondary" onClick={()=>nav('/agents/'+a.id+'/builder')}>빌더 열기 <ChevronRight/></button>{a.deletable&&<button className="danger iconDelete" title="워크플로우 삭제" onClick={()=>remove(a)}><Trash2 size={15}/></button>}</div></td></tr>)}</tbody></table></section>
    {creating&&<div className="modalBackdrop" onClick={()=>setCreating(false)}><article className="createModal" onClick={e=>e.stopPropagation()}><button className="close" onClick={()=>setCreating(false)}><X/></button><span>NEW WORKFLOW</span><h2>새 워크플로우 만들기</h2><p>빈 캔버스에서 직접 구성하거나 역할별 기본 템플릿으로 시작합니다.</p><label>워크플로우 이름<input autoFocus value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="예: 파주 북부 감시 워크플로우"/></label><label>설명<textarea value={form.description} onChange={e=>setForm({...form,description:e.target.value})} placeholder="수행할 임무를 입력하세요."/></label><label>시작 방식<select value={form.template} onChange={e=>setForm({...form,template:e.target.value})}><option value="BLANK">빈 캔버스</option><option value={session?.role}>{session?.role==='ANALYST'?'분석관':'참모'} 기본 템플릿</option></select></label><div className="createScope"><span>역할</span><b>{session&&roleName[session.role]}</b><span>지역</span><b>{session?.role==='ANALYST'?'경기도 파주시':'접경지역 전체'}</b></div>{error&&<p className="error">{error}</p>}<div className="createActions"><button className="secondary" onClick={()=>setCreating(false)}>취소</button><button className="primary" onClick={create}>초안 만들기 <ChevronRight/></button></div></article></div>}
  </>
}

function SituationMap({commanderHome=false}:{commanderHome?:boolean}){
  const {session}=useContext(SessionContext);
  const [reports,setReports]=useState<any[]>([]);
  const [activity,setActivity]=useState<any>({events:[],notifications:[]});
  const [selectedReport,setSelectedReport]=useState<any>();
  const areas=session?.role==='ANALYST'?['경기도 파주시']:Object.keys(MAP_AREAS);
  const [selectedArea,setSelectedArea]=useState('경기도 파주시');
  useEffect(()=>{if(session)Promise.all([api('/reports?role='+session.role),api('/situation-board?role='+session.role)]).then(([r,a])=>{setReports(r);setActivity(a)})},[session]);
  const point=MAP_AREAS[selectedArea as keyof typeof MAP_AREAS];
  const mapUrl=`https://www.openstreetmap.org/export/embed.html?bbox=${point.bbox}&layer=mapnik&marker=${point.lat},${point.lon}`;
  const reportNotifications=(activity.notifications||[]).map((note:any)=>({note,report:reports.find(report=>report.kind==='COMMANDER'&&report.source_execution_id===note.execution_id)})).filter((item:any)=>item.report);
  return <>
    <PageHead eyebrow={commanderHome?"지휘관 공통 상황도":"실제 지도 기반 상황 인식"} title="접경지역 상황판"><span className="live"><span className="online"/> 실시간 이벤트·승인 보고</span></PageHead>
    <div className="mapLayout">
      <section className="mapPanel">
        <iframe title={`${selectedArea} 지도`} src={mapUrl} loading="lazy"/>
        <div className="mapCaption"><Radar size={16}/><b>{selectedArea}</b><span>OpenStreetMap 실제 지도를 사용합니다.</span></div>
      </section>
      <aside className="areaList">
        <h2>감시 지역</h2>
        {areas.map(area=>{const report=reports.find(x=>x.area===area);return <button key={area} className={selectedArea===area?'areaItem selected':'areaItem'} onClick={()=>setSelectedArea(area)}><div><b>{area}</b><small>{report?.title||'승인 보고 없음'}</small></div><Badge value={report?.threat||'LOW'}/></button>})}
      </aside>
    </div>
    {session?.role==='COMMANDER'&&<div className="commanderFeed"><section className="panel"><div className="panelTitle"><h2>최근 센서 이벤트</h2><span>{activity.events.length}건</span></div>{activity.events.length?activity.events.map((event:any)=><article className="feedItem" key={event.id}><Radio/><div><b>{event.type}</b><p>{event.area} · 탐지 {event.object_count}개 · 신뢰도 {Math.round(event.confidence*100)}%</p><small>{new Date(event.created_at).toLocaleString('ko')}</small></div><Badge value={event.confidence>=.85?'HIGH':'MEDIUM'}/></article>):<Empty text="최근 센서 이벤트가 없습니다."/>}</section>
    <section className="panel"><div className="panelTitle"><h2>보고서 도착 알림</h2><span>{reportNotifications.length}건</span></div>{reportNotifications.length?reportNotifications.map(({note,report}:any)=><button className={'feedItem reportArrival '+(note.read_at?'read':'unread')} key={note.id} onClick={async()=>{const readAt=await markNotificationRead(note,session.role);setActivity((current:any)=>({...current,notifications:current.notifications.map((item:any)=>item.id===note.id?{...item,read_at:readAt}:item)}));setSelectedReport(report)}}><Bell/><div><b>{note.title}</b><p>{note.body}</p><small>{new Date(note.created_at).toLocaleString('ko')} · {note.read_at?'확인함':'새 알림'}</small></div><span>보고서 열기 <ChevronRight/></span></button>):<Empty text="새로 전달된 지휘관 보고서가 없습니다."/>}</section></div>}
    {!commanderHome&&<section className="panel"><div className="panelTitle"><h2>승인된 보고서</h2><span>{reports.length}건</span></div><div className="reportGrid">{reports.map(r=><button className="reportCard" key={r.id} onClick={()=>setSelectedReport(r)}><div><FileText/><Badge value={r.threat}/></div><h3>{r.title}</h3><p>{r.content}</p><small>{r.id} · {r.approved_by}{r.fixture&&<b> 데모 기본자료</b>}</small></button>)}</div></section>}
    {selectedReport&&<div className="modalBackdrop" onClick={()=>setSelectedReport(null)}><article className="reportModal" onClick={x=>x.stopPropagation()}><button className="close" onClick={()=>setSelectedReport(null)}><X/></button><span>승인된 {selectedReport.kind==='COMMANDER'?'지휘관':'지역'} 보고서</span><h1>{selectedReport.title}</h1><div className="reportMeta"><Badge value={selectedReport.threat}/><b>{selectedReport.area}</b><small>{new Date(selectedReport.approved_at).toLocaleString('ko')}</small></div><h3>승인 내용</h3><p className="reportContent">{selectedReport.content}</p><h3>보고 계보</h3><div className="lineage"><span>실행</span><b>{selectedReport.source_execution_id||'외부 데모 기본자료'}</b><span>승인자</span><b>{selectedReport.approved_by}</b></div></article></div>}
  </>
}

function NodeSettings({node,models,onChange,onDelete}:{node:any;models:any[];onChange:(node:any)=>void;onDelete:()=>void}){
  const capability=node.data.capabilityType||node.id;
  const config=node.data.config||{};
  const io=NODE_IO[capability]||{input:['state'],output:['state']};
  const setLabel=(label:string)=>onChange({...node,data:{...node.data,label}});
  const setConfig=(key:string,value:any)=>onChange({...node,data:{...node.data,config:{...config,[key]:value}}});
  return <><div className="configType"><b>{GROUP_META[node.data.group]?.name||node.data.group}</b><span>{GROUP_META[node.data.group]?.description}</span></div>
    <div className="ioContract"><div><b>INPUT</b>{io.input.map(x=><span key={x}>{x}</span>)}</div><ChevronRight/><div><b>OUTPUT</b>{io.output.map(x=><span key={x}>{x}</span>)}</div></div>
    <label>노드 이름<input value={node.data.label} onChange={e=>setLabel(e.target.value)}/></label>
    {capability==='filter'&&<><label>최소 센서 신뢰도<input type="number" min=".5" max=".99" step=".01" value={config.min_confidence??.8} onChange={e=>setConfig('min_confidence',+e.target.value)}/><small>이 값 이상인 이벤트만 다음 노드로 전달합니다.</small></label><label>최소 탐지 개체 수<input type="number" min="1" max="12" value={config.min_object_count??2} onChange={e=>setConfig('min_object_count',+e.target.value)}/></label></>}
    {(capability==='threat'||capability==='synthesis')&&<><label>호출 모델<select value={config.model_id||models.find(x=>x.default)?.id||''} onChange={e=>setConfig('model_id',e.target.value)}>{models.map(model=><option key={model.id} value={model.id}>{model.label}{model.default?' · 기본':''}</option>)}</select><small>게시 후 실제 Responses API 호출에 사용됩니다.</small></label><label>시스템 프롬프트<textarea value={config.system_prompt||''} onChange={e=>setConfig('system_prompt',e.target.value)} placeholder="모델의 역할과 출력 기준을 입력하세요."/></label></>}
    {capability==='context'&&<label>조회 조건<textarea value={config.query||''} onChange={e=>setConfig('query',e.target.value)} placeholder="조회할 작전 정보 범위를 입력하세요."/></label>}
    {capability==='generator'&&<label>보고서 권고 문구<textarea value={config.recommendation||''} onChange={e=>setConfig('recommendation',e.target.value)}/></label>}
    {capability==='sensor'&&<div className="info">센서 ID, 이벤트 종류, 규모와 신뢰도는 센서 입력 화면에서 전달됩니다.</div>}
    {(capability==='approval'||capability==='send'||capability==='report_trigger'||capability==='reports')&&<div className="info">이 노드는 워크플로우 역할과 보고서 유형에 맞춰 자동 설정됩니다.</div>}
    <div className="nodeConfigActions"><button className="danger" onClick={onDelete}><X size={15}/> 노드 삭제</button></div>
  </>
}

function SensorInput(){
  const {session}=useContext(SessionContext);
  const nav=useNavigate();
  const [count,setCount]=useState(4);
  const [confidence,setConfidence]=useState(.94);
  const [kind,setKind]=useState('이동체 감지');
  const [result,setResult]=useState<any>();
  const [sending,setSending]=useState(false);
  const [error,setError]=useState('');
  if(session?.role!=='ANALYST') return <Navigate to="/dashboard"/>;
  async function send(){
    setSending(true);setError('');
    try{setResult(await api('/sensor-events',{method:'POST',headers:{'X-Demo-Role':'ANALYST'},body:JSON.stringify({sensor_id:'파주-감시센서-03',type:kind,area:'경기도 파주시',object_count:count,confidence})}))}
    catch(e:any){setError(e.message)}finally{setSending(false)}
  }
  return <><PageHead eyebrow="DEMO SENSOR INPUT" title="센서 입력"><span className="muted">실제 센서를 대신하는 데모 입력기</span></PageHead>
    <div className="sensorLayout"><section className="panel sensorForm"><div className="sensorIdentity"><Radio/><div><small>활성 감시 센서</small><h2>파주-감시센서-03</h2><span><i className="online"/> 경기도 파주시 · 정상</span></div></div>
      <label>이벤트 종류<select value={kind} onChange={e=>setKind(e.target.value)}><option>이동체 감지</option><option>열원 감지</option><option>경계선 접근</option></select></label>
      <label><span>탐지 개체 수 <b>{count}개</b></span><input type="range" min="1" max="12" value={count} onChange={e=>setCount(+e.target.value)}/><small>1</small><small>12</small></label>
      <label><span>센서 신뢰도 <b>{Math.round(confidence*100)}%</b></span><input type="range" min="50" max="99" value={Math.round(confidence*100)} onChange={e=>setConfidence(+e.target.value/100)}/><small>50%</small><small>99%</small></label>
      <button className="primary sensorSend" onClick={send} disabled={sending}><Play/>{sending?' 이벤트 처리 중…':'센서 이벤트 전송'}</button>{error&&<p className="error">{error}</p>}
    </section><aside className="panel sensorPreview"><h2>전송 데이터</h2><pre>{JSON.stringify({sensor_id:'파주-감시센서-03',type:kind,area:'경기도 파주시',object_count:count,confidence},null,2)}</pre>
      <div className="scaleHint"><b>분석 기준 안내</b><p>탐지 규모와 신뢰도를 함께 높이면 LLM이 더 높은 위협 수준으로 판단할 가능성이 커집니다.</p></div>
      {result&&<div className="sensorResult"><Check/><div><small>이벤트가 접수되었습니다.</small><b>{result.execution_id}</b><Badge value={result.status}/></div><button className="secondary" onClick={()=>nav('/executions/'+result.execution_id)}>실행 열기 <ChevronRight/></button></div>}
    </aside></div></>
}

function SystemStatus(){
  const [health,setHealth]=useState<any>();
  useEffect(()=>{api('/health').then(setHealth).catch(()=>setHealth({status:'error'}))},[]);
  const ready=health?.status==='ok'&&health?.configured!==false;
  return <div className="system"><span className={ready?'online':'pulse'}/> {ready?'시스템 정상':'LLM 설정 필요'}<small>{health?.mode==='deterministic'?'Deterministic 리허설':health?.model||'상태 확인 중'}</small></div>
}

const ROLE_GUIDE={
  ANALYST:{title:'파주지역 분석관',summary:'파주시 센서 이벤트를 분석하고 지역 보고서를 검토·승인합니다.',permissions:['본인 소유 분석 워크플로우 생성·편집·게시·삭제','파주시 센서 이벤트 실행','분석관 승인 요청 처리'],nodes:['감시 센서 이벤트','이벤트 조건 확인','작전 정보 조회','위협 분석·초안 생성','분석관 검토·승인','지역 보고서 발행']},
  STAFF:{title:'정보·작전 참모',summary:'승인된 지역 보고서를 종합하고 지휘관 상황보고를 검토·승인합니다.',permissions:['본인 소유 종합 워크플로우 생성·편집·게시·삭제','승인 지역보고 기반 자동 실행','참모 승인 요청 처리'],nodes:['승인 지역보고 접수','승인 지역보고 수집','접경지역 작전상황 조회','위협 종합·초안 생성','참모 검토·승인','지휘관 보고서 발행']},
  COMMANDER:{title:'지휘관',summary:'승인이 끝난 최종 상황보고와 접경지역 상황판을 열람합니다.',permissions:['완료된 지휘관 보고서 열람','접경지역 통합 상황판 열람','워크플로우 편집 및 승인 권한 없음'],nodes:[]},
} as const;

function Manual(){
  const {session}=useContext(SessionContext);
  if(!session)return null;
  const guide=ROLE_GUIDE[session.role];
  const steps=session.role==='ANALYST'
    ?['워크플로우 레지스트리에서 새 워크플로우를 만들거나 기본 워크플로우를 엽니다.','노드를 배치·연결하고 조건과 AI 프롬프트를 설정한 뒤 저장, 검증, 게시합니다.','센서 입력에서 탐지 규모와 신뢰도를 정해 이벤트를 전송합니다.','실행 모니터링에서 LLM 분석을 확인하고 지역 보고서를 승인합니다.']
    :session.role==='STAFF'
    ?['워크플로우 레지스트리에서 종합 워크플로우의 노드와 프롬프트를 설정하고 게시합니다.','분석관이 지역 보고서를 승인하면 종합 워크플로우가 자동 실행됩니다.','실행 모니터링에서 지역별 근거와 LLM 종합 결과를 확인합니다.','지휘관 보고서 초안을 검토하고 승인합니다.']
    :['대시보드에서 완료된 주요 실행과 보고 현황을 확인합니다.','상황판에서 파주·연천·철원 지역의 승인 보고를 지도와 함께 확인합니다.','최종 지휘관 보고서의 승인자와 원본 보고 계보를 확인합니다.'];
  return <><PageHead eyebrow="USER GUIDE" title="사용 매뉴얼"><Badge value={guide.title}/></PageHead>
    <section className="manualHero"><BookOpen/><div><h2>{guide.title}</h2><p>{guide.summary}</p></div></section>
    <div className="manualGrid"><section className="panel manualCard"><h2>권한과 접근 범위</h2>{guide.permissions.map((x,i)=><div className="manualItem" key={x}><Check/><span><b>{i+1}</b>{x}</span></div>)}</section>
    <section className="panel manualCard"><h2>사용 순서</h2>{steps.map((x,i)=><div className="manualStep" key={x}><b>{i+1}</b><p>{x}</p></div>)}</section></div>
    <section className="panel manualNodes"><div className="panelTitle"><h2>사용 가능한 노드</h2><span>{guide.nodes.length?guide.nodes.length+'개':'읽기 전용'}</span></div>{guide.nodes.length?<div>{guide.nodes.map((x,i)=><React.Fragment key={x}><span>{x}</span>{i<guide.nodes.length-1&&<ChevronRight/>}</React.Fragment>)}</div>:<p>지휘관은 워크플로를 편집하지 않으며 승인된 결과만 열람합니다.</p>}</section>
  </>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
