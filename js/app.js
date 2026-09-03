
const $ = s => document.querySelector(s);
const fmt = n => n == null ? '—' : new Intl.NumberFormat().format(n);
let DATA, HISTORY=[];

async function load(){
  const bust=`?v=${Date.now()}`;
  DATA=await (await fetch(`data/current.json${bust}`,{cache:'no-store'})).json();
  try{
    const idx=await (await fetch(`data/history-index.json${bust}`,{cache:'no-store'})).json();
    HISTORY=idx.snapshots||[];
  }catch{HISTORY=[]}
  initFilters(); render();
}
function initFilters(){
  const states=[...new Set(DATA.cinemas.map(c=>c.state))].sort();
  const chains=[...new Set(DATA.cinemas.map(c=>c.chain))].sort();
  $('#state-filter').innerHTML='<option value="">All states</option>'+states.map(v=>`<option>${v}</option>`).join('');
  $('#chain-filter').innerHTML='<option value="">All chains</option>'+chains.map(v=>`<option>${v}</option>`).join('');
}
function filtered(){
  const st=$('#state-filter').value,ch=$('#chain-filter').value,q=$('#search').value.trim().toLowerCase();
  return DATA.cinemas.filter(c=>(!st||c.state===st)&&(!ch||c.chain===ch)&&(!q||c.name.toLowerCase().includes(q)));
}
function sessions(cinemas){return cinemas.flatMap(c=>c.sessions.map(s=>({...s,cinema:c})));}
function stats(cin){
  const ss=sessions(cin),known=ss.filter(s=>Number.isFinite(s.capacity)&&Number.isFinite(s.booked));
  const capacity=known.reduce((a,s)=>a+s.capacity,0),booked=known.reduce((a,s)=>a+s.booked,0);
  const available=known.reduce((a,s)=>a+(Number.isFinite(s.available)?s.available:s.capacity-s.booked),0);
  const occ=capacity?booked/capacity*100:null;
  const hour=s=>Number(s.time.slice(0,2));
  return {ss,known,capacity,booked,available,occ,
    matinee:ss.filter(s=>hour(s)<17).length,
    prime:ss.filter(s=>hour(s)>=17&&hour(s)<21).length,
    late:ss.filter(s=>hour(s)>=21).length,
    reporting:cin.filter(c=>c.sessions.length).length
  };
}
function velocity(){
  const points=HISTORY.filter(x=>Number.isFinite(x.booked)&&x.observedAt).sort((a,b)=>new Date(a.observedAt)-new Date(b.observedAt));
  if(points.length<2)return null;
  const a=points[points.length-2],b=points[points.length-1];
  const hours=(new Date(b.observedAt)-new Date(a.observedAt))/36e5;
  if(hours<=0)return null;
  return (b.booked-a.booked)/hours;
}
function render(){
  const cin=filtered(),s=stats(cin),v=velocity();
  $('#updated').textContent=`Updated ${new Date(DATA.updatedAt).toLocaleString('en-MY',{dateStyle:'medium',timeStyle:'short'})}`;
  $('#stat-shows').textContent=fmt(s.ss.length); $('#stat-cinemas').textContent=`${s.reporting} cinemas reporting`;
  $('#stat-booked').textContent=s.known.length?fmt(s.booked):'—'; $('#stat-available').textContent=s.known.length?fmt(s.available):'—';
  $('#stat-occupancy').textContent=s.occ==null?'—':`${s.occ.toFixed(1)}%`;
  $('#stat-capacity').textContent=s.known.length?`${fmt(s.capacity)} tracked seats`:'Capacity pending';
  $('#stat-velocity').textContent=v==null?'—':`${v.toFixed(1)}/hr`;
  $('#stat-velocity-sub').textContent=v==null?'Needs 2+ seat snapshots':'Across tracked sessions';
  $('#s-reporting').textContent=s.reporting; $('#s-shows').textContent=s.ss.length; $('#s-matinee').textContent=s.matinee; $('#s-prime').textContent=s.prime; $('#s-late').textContent=s.late;
  $('#s-capacity').textContent=s.known.length?fmt(s.capacity):'—'; $('#s-booked').textContent=s.known.length?fmt(s.booked):'—'; $('#s-remaining').textContent=s.known.length?fmt(s.available):'—';
  $('#s-velocity').textContent=v==null?'—':`${v.toFixed(1)}/hr`;
  $('#reporting-note').textContent=s.known.length?`${s.known.length} sessions with seat data`:'Showtime feed active · seat feed pending';
  renderBars(cin); renderRanking(cin); renderCinemaList(cin);
}
function renderBars(cin){
  $('#bars').innerHTML=cin.map(c=>{
    const known=c.sessions.filter(s=>Number.isFinite(s.capacity)&&Number.isFinite(s.booked));
    const cap=known.reduce((a,s)=>a+s.capacity,0),book=known.reduce((a,s)=>a+s.booked,0),pct=cap?book/cap*100:null;
    return `<div class="bar-row"><div class="bar-label"><b>${c.name}</b><small>${c.state} · ${c.sessions.length} show${c.sessions.length===1?'':'s'}</small></div><div class="track"><div class="fill" style="width:${pct??0}%"></div></div><div class="bar-value">${pct==null?'—':pct.toFixed(0)+'%'}</div></div>`;
  }).join('');
}
function renderRanking(cin){
  const ranked=cin.map(c=>{
    const k=c.sessions.filter(s=>Number.isFinite(s.capacity)&&Number.isFinite(s.booked));
    const cap=k.reduce((a,s)=>a+s.capacity,0),book=k.reduce((a,s)=>a+s.booked,0);
    return {...c,pct:cap?book/cap*100:null};
  }).filter(x=>x.pct!=null).sort((a,b)=>b.pct-a.pct);
  $('#ranking').innerHTML=ranked.length?ranked.map((c,i)=>`<div class="rank-row"><div class="rank-num">${i+1}</div><div class="rank-name"><b>${c.name}</b><small>${c.state}</small></div><div class="rank-pct">${c.pct.toFixed(1)}%</div></div>`).join(''):'<div class="empty">Ranking appears when seat-map snapshots are available.</div>';
}
function renderCinemaList(cin){
  const host=$('#cinema-list');host.innerHTML='';const tpl=$('#cinema-template');
  cin.forEach(c=>{
    const node=tpl.content.cloneNode(true),article=node.querySelector('.cinema'),btn=node.querySelector('.cinema-head');
    node.querySelector('.cinema-name').textContent=c.name;node.querySelector('.cinema-meta').textContent=`${c.chain} · ${c.state}`;
    node.querySelector('.cinema-summary').textContent=c.sessions.length?`${c.sessions.length} shows`:'No showtime feed yet';
    const holder=node.querySelector('.sessions');
    holder.innerHTML=c.sessions.length?c.sessions.map(s=>{
      const known=Number.isFinite(s.capacity)&&Number.isFinite(s.booked),pct=known?s.booked/s.capacity*100:null;
      return `<div class="session"><div class="time">${s.time}</div><div><b>${s.hall==='—'?'Hall pending':s.hall}</b><div class="hall">${known?`${s.booked} booked · ${s.available ?? s.capacity-s.booked} open`:'Seat map not connected'}</div></div><div><div class="seat-note">${known?`${s.booked} / ${s.capacity} seats booked`:'Booked-seat count unavailable'}</div><div class="seatbar"><i style="width:${pct??0}%"></i></div></div><div class="occ">${pct==null?'—':pct.toFixed(1)+'%'}</div></div>`;
    }).join(''):'<div class="empty">Awaiting the next automated showtime refresh for this location.</div>';
    btn.addEventListener('click',()=>{article.classList.toggle('open');btn.setAttribute('aria-expanded',article.classList.contains('open'))});
    host.append(node);
  })
}
document.addEventListener('input',e=>{if(['state-filter','chain-filter','search'].includes(e.target.id))render()});
$('#refresh').addEventListener('click',load);
load().catch(err=>{console.error(err);$('#updated').textContent='Data load failed';});
