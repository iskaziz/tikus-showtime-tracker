const $ = s => document.querySelector(s);
const fmt = n => n == null ? '—' : new Intl.NumberFormat().format(n);
let DATA, HISTORY=[], DAYS=[];
let MAP_SELECTED_ID=null;

const MAP_POSITIONS={
  "gsc-paradigm-jb":[36.2,78.5],
  "tgv-tebrau":[37.6,80.4],
  "paragon-batu-pahat":[32.9,72.8],
  "gsc-aman-central":[25.1,24.5],
  "mega-riverfront":[24.3,27.1],
  "gsc-midvalley":[29.3,62.8],
  "tgv-wangsa-walk":[31.2,59.8],
  "gsc-dataran-pahlawan":[31.4,70.2],
  "gsc-kuantan-city-mall":[40.2,53.0],
  "gsc-ioi-city-mall":[30.3,65.0],
  "gsc-imago":[88.6,47.0],
  "gsc-the-spring":[66.1,65.0],
  "tgv-gurney":[23.2,35.0],
  "tgv-bukit-tinggi":[27.8,61.8],
  "tgv-1utama":[28.4,60.1],
  "paragon-ktcc":[40.7,37.7]
};

function mapCinemaStats(c){
  const ss=c.sessions||[],known=ss.filter(isKnown);
  return {
    shows:ss.length,
    used:known.length?known.reduce((a,s)=>a+s.booked,0):null,
    capacity:known.length?known.reduce((a,s)=>a+s.capacity,0):null
  };
}
function nextShowLabel(c){
  const now=new Date(),currentMinutes=now.getHours()*60+now.getMinutes();
  const future=(c.sessions||[]).map(s=>({s,mins:Number(s.time.slice(0,2))*60+Number(s.time.slice(3,5))}))
    .filter(x=>Number.isFinite(x.mins)&&x.mins>=currentMinutes).sort((a,b)=>a.mins-b.mins);
  if(future.length){
    const s=future[0].s;
    return `Next listed show: <b>${s.time}</b>${s.hall&&s.hall!=='—'?` · ${s.hall}`:''}`;
  }
  if((c.sessions||[]).length)return 'No later listed showtimes today.';
  return 'No verified showtimes currently listed for this date.';
}
function renderMap(){
  const host=$('#map-markers');if(!host||!DATA)return;
  const s=stats(DATA.cinemas);
  $('#map-location-count').textContent=DATA.cinemas.length;
  $('#map-show-count').textContent=s.ss.length;
  $('#map-seat-count').textContent=s.known.length?fmt(s.used):'—';
  host.innerHTML='';
  DATA.cinemas.forEach(c=>{
    const pos=MAP_POSITIONS[c.id];if(!pos)return;
    const st=mapCinemaStats(c),btn=document.createElement('button');
    btn.type='button';btn.className='map-marker';btn.dataset.chain=c.chain;btn.dataset.cinemaId=c.id;
    btn.style.left=`${pos[0]}%`;btn.style.top=`${pos[1]}%`;
    btn.setAttribute('aria-label',`${c.name}, ${c.state}. ${st.shows} listed shows.`);
    btn.title=c.name;
    btn.addEventListener('click',()=>openMapTooltip(c.id));
    host.append(btn);
  });
}
function openMapTooltip(id){
  const c=DATA.cinemas.find(x=>x.id===id);if(!c)return;
  MAP_SELECTED_ID=id;
  document.querySelectorAll('.map-marker').forEach(b=>b.classList.toggle('is-selected',b.dataset.cinemaId===id));
  const st=mapCinemaStats(c);
  $('#map-tooltip-chain').textContent=c.chain;$('#map-tooltip-title').textContent=c.name;$('#map-tooltip-state').textContent=c.state;
  $('#map-tooltip-shows').textContent=st.shows;$('#map-tooltip-used').textContent=st.used==null?'—':fmt(st.used);
  $('#map-tooltip-capacity').textContent=st.capacity==null?'—':fmt(st.capacity);
  $('#map-tooltip-next').innerHTML=nextShowLabel(c);$('#map-tooltip-jump').dataset.cinemaId=id;$('#map-tooltip').hidden=false;
}
function closeMapTooltip(){
  MAP_SELECTED_ID=null;document.querySelectorAll('.map-marker').forEach(b=>b.classList.remove('is-selected'));
  if($('#map-tooltip'))$('#map-tooltip').hidden=true;
}
function jumpToCinema(id){
  const cinema=DATA.cinemas.find(c=>c.id===id);if(!cinema)return;
  $('#search').value=cinema.name;render();
  requestAnimationFrame(()=>{
    const card=document.querySelector('.cinema');
    if(!card)return;
    card.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
    const head=card.querySelector('.cinema-head');if(head&&!card.classList.contains('open'))head.click();head?.focus();
  });
}


async function fetchJson(path){
  const bust=`${path.includes('?')?'&':'?'}v=${Date.now()}`;
  const r=await fetch(`${path}${bust}`,{cache:'no-store'});
  if(!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

async function loadDays(){
  try{
    const idx=await fetchJson('data/days/index.json');
    DAYS=idx.days||[];
  }catch{DAYS=[]}
}

async function load(date=null){
  await loadDays();
  const selected=date || new URL(location.href).searchParams.get('date');
  const day=DAYS.find(d=>d.date===selected);
  const path=day ? `data/${day.file}` : 'data/current.json';
  DATA=await fetchJson(path);

  try{
    const idx=await fetchJson('data/history-index.json');
    HISTORY=(idx.snapshots||[]).filter(x=>!x.datasetDate || x.datasetDate===DATA.date);
  }catch{HISTORY=[]}

  initDateFilter();
  initFilters();
  render();
}

function initDateFilter(){
  const el=$('#date-filter');
  const rows=DAYS.length?DAYS:[{date:DATA.date,label:DATA.date,status:'current'}];
  el.innerHTML=rows.slice().sort((a,b)=>b.date.localeCompare(a.date))
    .map(d=>`<option value="${d.date}" ${d.date===DATA.date?'selected':''}>${d.label||d.date}${d.status==='current'?' · Live':''}</option>`)
    .join('');
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
function sessions(cinemas){return cinemas.flatMap(c=>(c.sessions||[]).map(s=>({...s,cinema:c})));}
function isKnown(s){return Number.isFinite(s.capacity)&&Number.isFinite(s.booked);}
function semanticLabel(s){
  if(s.cinema?.chain==='TGV' || s.countSemantics==='tgv-seatsused') return 'used';
  if(s.cinema?.chain==='GSC') return 'booked';
  return 'observed';
}
function stats(cin){
  const ss=sessions(cin),known=ss.filter(isKnown);
  const capacity=known.reduce((a,s)=>a+s.capacity,0),used=known.reduce((a,s)=>a+s.booked,0);
  const available=known.reduce((a,s)=>a+(Number.isFinite(s.available)?s.available:s.capacity-s.booked),0);
  const occ=capacity?used/capacity*100:null;
  const hour=s=>Number(s.time.slice(0,2));
  return {ss,known,capacity,used,available,occ,
    matinee:ss.filter(s=>hour(s)<17).length,
    prime:ss.filter(s=>hour(s)>=17&&hour(s)<21).length,
    late:ss.filter(s=>hour(s)>=21).length,
    reporting:cin.filter(c=>(c.sessions||[]).length).length
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
  renderMap();
  const dateLabel=new Date(`${DATA.date}T12:00:00+08:00`).toLocaleDateString('en-MY',{dateStyle:'medium'});
  $('#updated').textContent=`${dateLabel} · Updated ${new Date(DATA.updatedAt).toLocaleString('en-MY',{timeStyle:'short'})}`;
  $('#stat-shows').textContent=fmt(s.ss.length); $('#stat-cinemas').textContent=`${s.reporting} cinemas reporting`;
  $('#stat-booked').textContent=s.known.length?fmt(s.used):'—'; $('#stat-available').textContent=s.known.length?fmt(s.available):'—';
  $('#stat-occupancy').textContent=s.occ==null?'—':`${s.occ.toFixed(1)}%`;
  $('#stat-capacity').textContent=s.known.length?`${fmt(s.capacity)} observed seats`:'Capacity pending';
  $('#stat-velocity').textContent=v==null?'—':`${v.toFixed(1)}/hr`;
  $('#stat-velocity-sub').textContent=v==null?'Needs 2+ same-day snapshots':'Observed inventory change';
  $('#s-locations').textContent=DATA.cinemas.length;
  $('#s-reporting').textContent=s.reporting; $('#s-shows').textContent=s.ss.length; $('#s-matinee').textContent=s.matinee; $('#s-prime').textContent=s.prime; $('#s-late').textContent=s.late;
  $('#s-capacity').textContent=s.known.length?fmt(s.capacity):'—'; $('#s-booked').textContent=s.known.length?fmt(s.used):'—'; $('#s-remaining').textContent=s.known.length?fmt(s.available):'—';
  $('#s-velocity').textContent=v==null?'—':`${v.toFixed(1)}/hr`;
  $('#reporting-note').textContent=s.known.length?`${s.known.length} sessions with observed seat data`:'Showtime feed active · seat feed pending';
  renderBars(cin); renderRanking(cin); renderCinemaList(cin);
}
function renderBars(cin){
  $('#bars').innerHTML=cin.map(c=>{
    const known=(c.sessions||[]).filter(isKnown);
    const cap=known.reduce((a,s)=>a+s.capacity,0),used=known.reduce((a,s)=>a+s.booked,0),pct=cap?used/cap*100:null;
    return `<div class="bar-row"><div class="bar-label"><b>${c.name}</b><small>${c.state} · ${(c.sessions||[]).length} show${(c.sessions||[]).length===1?'':'s'}</small></div><div class="track"><div class="fill" style="width:${pct??0}%"></div></div><div class="bar-value">${pct==null?'—':pct.toFixed(1)+'%'}</div></div>`;
  }).join('');
}
function renderRanking(cin){
  const ranked=cin.map(c=>{
    const k=(c.sessions||[]).filter(isKnown);
    const cap=k.reduce((a,s)=>a+s.capacity,0),used=k.reduce((a,s)=>a+s.booked,0);
    return {...c,pct:cap?used/cap*100:null};
  }).filter(x=>x.pct!=null).sort((a,b)=>b.pct-a.pct);
  $('#ranking').innerHTML=ranked.length?ranked.map((c,i)=>`<div class="rank-row"><div class="rank-num">${i+1}</div><div class="rank-name"><b>${c.name}</b><small>${c.state}</small></div><div class="rank-pct">${c.pct.toFixed(1)}%</div></div>`).join(''):'<div class="empty">Ranking appears when seat data is available.</div>';
}
function renderCinemaList(cin){
  const host=$('#cinema-list');host.innerHTML='';const tpl=$('#cinema-template');
  cin.forEach(c=>{
    const node=tpl.content.cloneNode(true),article=node.querySelector('.cinema'),btn=node.querySelector('.cinema-head');
    node.querySelector('.cinema-name').textContent=c.name;node.querySelector('.cinema-meta').textContent=`${c.chain} · ${c.state}`;
    node.querySelector('.cinema-summary').textContent=(c.sessions||[]).length?`${c.sessions.length} shows`:'No shows found';
    const holder=node.querySelector('.sessions');
    holder.innerHTML=(c.sessions||[]).length?c.sessions.map(s=>{
      const known=isKnown(s),pct=known?s.booked/s.capacity*100:null,label=c.chain==='TGV'?'used':'booked';
      const extra=c.chain==='GSC'&&Number.isFinite(s.otherUnavailable)&&s.otherUnavailable>0?` · ${s.otherUnavailable} other unavailable`:'';
      const state=s.isExpired?' · last observed':'';
      const fallbackOnly=s.sourceStatus==='fallback-showtime-only' || s.seatStatus==='official-gsc-showtime-not-listed';
      const seatMessage=known
        ? `${s.booked} ${label} · ${s.available ?? s.capacity-s.booked} available${extra}${state}`
        : fallbackOnly
          ? 'Fallback showtime · not listed in GSC official feed'
          : 'Seat data not observed';
      const countMessage=known
        ? `${s.booked} / ${s.capacity} ${label}`
        : fallbackOnly
          ? 'Official seat count unavailable'
          : 'Observed count unavailable';
      return `<div class="session"><div class="time">${s.time}</div><div><b>${s.hall==='—'||!s.hall?'Hall unverified':s.hall}</b><div class="hall">${seatMessage}</div></div><div><div class="seat-note">${countMessage}</div><div class="seatbar"><i style="width:${pct??0}%"></i></div></div><div class="occ">${pct==null?'—':pct.toFixed(1)+'%'}</div></div>`;
    }).join(''):'<div class="empty">Awaiting showtime data for this date.</div>';
    btn.addEventListener('click',()=>{article.classList.toggle('open');btn.setAttribute('aria-expanded',article.classList.contains('open'))});
    host.append(node);
  })
}
document.addEventListener('input',e=>{if(['state-filter','chain-filter','search'].includes(e.target.id))render()});
$('#date-filter').addEventListener('change',e=>{
  const u=new URL(location.href);u.searchParams.set('date',e.target.value);history.replaceState({},'',u);load(e.target.value);
});
$('#refresh').addEventListener('click',()=>load(DATA.date));
$('#map-tooltip-close')?.addEventListener('click',closeMapTooltip);
$('#map-tooltip-jump')?.addEventListener('click',e=>jumpToCinema(e.currentTarget.dataset.cinemaId));
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('#map-tooltip')?.hidden)closeMapTooltip()});
load().catch(err=>{console.error(err);$('#updated').textContent='Data load failed';});
