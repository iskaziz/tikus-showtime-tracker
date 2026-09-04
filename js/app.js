const $ = s => document.querySelector(s);
const fmt = n => n == null ? '—' : new Intl.NumberFormat().format(n);
const setText = (selector,value) => { const el=$(selector); if(el) el.textContent=value; };
const setHtml = (selector,value) => { const el=$(selector); if(el) el.innerHTML=value; };
let DATA, HISTORY=[], HISTORY_DETAIL=[], DAYS=[];
let MAP_SELECTED_ID=null;
let MAP_CYCLE_INDEX=0;
let MAP_CYCLE_TIMER=null;
let MAP_CYCLE_PAUSED=false;

const MAP_POSITIONS={
  "gsc-aman-central":[10.83,21.98],
  "mega-riverfront":[14.47,16.21],
  "tgv-gurney":[8.79,34.05],
  "gsc-midvalley":[6.04,69.19],
  "tgv-wangsa-walk":[8.19,68.29],
  "gsc-ioi-city-mall":[7.00,75.86],
  "tgv-1utama":[8.91,73.51],
  "tgv-bukit-tinggi":[18.54,68.10],
  "paragon-ktcc":[31.52,41.09],
  "gsc-kuantan-city-mall":[31.76,59.82],
  "gsc-dataran-pahlawan":[23.98,83.97],
  "paragon-batu-pahat":[34.57,90.99],
  "gsc-paradigm-jb":[33.13,85.58],
  "tgv-tebrau":[35.47,85.95],
  "gsc-imago":[64.53,42.16],
  "gsc-the-spring":[73.39,84.69]
};



function cinemaSummary(c){
  const known=(c.sessions||[]).filter(isKnown);
  const capacity=known.reduce((a,s)=>a+s.capacity,0);
  const used=known.reduce((a,s)=>a+s.booked,0);
  const occ=capacity?used/capacity*100:null;
  return {
    shows:(c.sessions||[]).length,
    known:known.length,
    capacity,
    used,
    available:capacity-used,
    occ
  };
}
function chainClass(chain){
  return String(chain||'').toLowerCase();
}
function sourceText(c){
  return c.sourceStatus==='gsc-official-api'
    ? 'Source: GSC official showtime / seat-status feed'
    : c.sourceStatus==='tgv-official-api'
      ? 'Source: TGV official public API'
      : c.sourceStatus==='fallback-showtimes-official-gsc-not-listed'
        ? 'Source: fallback showtime listing; not present in GSC official feed'
        : c.sourceStatus==='awaiting-refresh'
          ? 'Source: awaiting verified current-date refresh'
          : `Source: ${c.sourceStatus||'tracker feed'}`;
}
function mapDisplaySet(){
  const visibleIds=new Set(filtered().map(c=>c.id));
  return DATA.cinemas.map(c=>({...c, __visible:visibleIds.has(c.id)}));
}
function highlightCinemaCard(id){
  document.querySelectorAll('.cinema-card').forEach(card=>{
    card.classList.toggle('is-highlighted',card.dataset.cinemaId===id);
  });
}
function startMapCycle(){
  stopMapCycle();
  if(matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if(!DATA||!DATA.cinemas?.length)return;
  const liveFirst=[...DATA.cinemas].sort((a,b)=>{
    const aa=cinemaSummary(a), bb=cinemaSummary(b);
    return (bb.known-bb.shows/100)-(aa.known-aa.shows/100);
  });
  MAP_CYCLE_TIMER=setInterval(()=>{
    if(MAP_CYCLE_PAUSED||!liveFirst.length) return;
    MAP_CYCLE_INDEX=(MAP_CYCLE_INDEX+1)%liveFirst.length;
    openMapTooltip(liveFirst[MAP_CYCLE_INDEX].id,{auto:true,scroll:false});
  },4200);
}
function stopMapCycle(){
  if(MAP_CYCLE_TIMER){ clearInterval(MAP_CYCLE_TIMER); MAP_CYCLE_TIMER=null; }
}
function pauseMapCycle(value=true){
  MAP_CYCLE_PAUSED=value;
}

function mapCinemaStats(c){
  const ss=c.sessions||[],known=ss.filter(isKnown);
  return {
    shows:ss.length,
    used:known.length?known.reduce((a,s)=>a+s.booked,0):null,
    capacity:known.length?known.reduce((a,s)=>a+s.capacity,0):null
  };
}
function nextShowLabel(c){
  const listed=(c.sessions||[]).map(s=>({
    s,
    mins:Number(s.time?.slice(0,2))*60+Number(s.time?.slice(3,5))
  })).filter(x=>Number.isFinite(x.mins)).sort((a,b)=>a.mins-b.mins);

  if(!listed.length) return 'No verified showtimes currently listed for this date.';

  const now=new Date();
  const myDate=new Intl.DateTimeFormat('en-CA',{
    timeZone:'Asia/Kuala_Lumpur',year:'numeric',month:'2-digit',day:'2-digit'
  }).format(now);
  if(DATA?.date!==myDate){
    const s=listed[0].s;
    return `First listed show: <b>${s.time}</b>${s.hall&&s.hall!=='—'?` · ${s.hall}`:''}`;
  }

  const parts=new Intl.DateTimeFormat('en-GB',{
    timeZone:'Asia/Kuala_Lumpur',hour:'2-digit',minute:'2-digit',hour12:false
  }).formatToParts(now);
  const hh=Number(parts.find(x=>x.type==='hour')?.value);
  const mm=Number(parts.find(x=>x.type==='minute')?.value);
  const currentMinutes=hh*60+mm;
  const future=listed.filter(x=>x.mins>=currentMinutes);

  if(future.length){
    const s=future[0].s;
    return `Next listed show: <b>${s.time}</b>${s.hall&&s.hall!=='—'?` · ${s.hall}`:''}`;
  }
  return 'No later listed showtimes today.';
}
function renderMap(){
  const host=$('#map-markers'); if(!host||!DATA) return;
  const globalStats=stats(DATA.cinemas);
  setText('#map-show-count',globalStats.ss.length);
  setText('#map-seat-count',globalStats.known.length?fmt(globalStats.used):'—');
  setText('#map-live-count',globalStats.known.length?fmt(globalStats.known.length):'—');
  setText('#map-update-short',new Date(DATA.updatedAt).toLocaleTimeString('en-MY',{hour:'2-digit',minute:'2-digit'}));

  const chainShows=chain=>DATA.cinemas.filter(c=>c.chain===chain).reduce((n,c)=>n+(c.sessions||[]).length,0);
  setText('#map-gsc-shows',chainShows('GSC'));
  setText('#map-tgv-shows',chainShows('TGV'));
  setText('#map-paragon-shows',chainShows('Paragon'));
  setText('#map-mega-shows',chainShows('Mega'));

  const ranked=DATA.cinemas
    .map(c=>({c,s:cinemaSummary(c)}))
    .filter(x=>x.s.occ!=null)
    .sort((a,b)=>b.s.occ-a.s.occ || b.s.used-a.s.used);
  if(ranked.length){
    setText('#map-best-cinema',ranked[0].c.name);
    setText('#map-best-meta',`${ranked[0].s.occ.toFixed(1)}% · ${fmt(ranked[0].s.used)} used / booked`);
  }else{
    setText('#map-best-cinema','Awaiting seat data');
    setText('#map-best-meta','—');
  }

  host.innerHTML='';

  mapDisplaySet().forEach(c=>{
    const pos=MAP_POSITIONS[c.id]; if(!pos) return;
    const sum=cinemaSummary(c);
    const btn=document.createElement('button');
    btn.type='button';
    btn.className='map-marker';
    btn.dataset.chain=c.chain;
    btn.dataset.cinemaId=c.id;
    btn.dataset.muted=String(!c.__visible);
    btn.dataset.coverage=sum.known ? (sum.known===sum.shows ? 'full' : 'partial') : 'none';
    btn.style.left=`${pos[0]}%`;
    btn.style.top=`${pos[1]}%`;
    btn.setAttribute('aria-label',`${c.name}, ${c.state}. ${sum.shows} listed shows.`);
    btn.title=c.name;

    const badge=document.createElement('span');
    badge.className='marker-badge';
    badge.textContent=sum.shows;
    btn.append(badge);

    btn.addEventListener('mouseenter',()=>{ pauseMapCycle(true); openMapTooltip(c.id,{auto:true,scroll:false}); });
    btn.addEventListener('focus',()=>{ pauseMapCycle(true); openMapTooltip(c.id,{auto:true,scroll:false}); });
    btn.addEventListener('mouseleave',()=>pauseMapCycle(false));
    btn.addEventListener('click',()=>{ pauseMapCycle(true); openMapTooltip(c.id,{auto:false,scroll:false}); });

    host.append(btn);
  });

  const activeId=(MAP_SELECTED_ID && DATA.cinemas.some(c=>c.id===MAP_SELECTED_ID)) ? MAP_SELECTED_ID : DATA.cinemas[0]?.id;
  if(activeId) openMapTooltip(activeId,{auto:true,scroll:false});
  startMapCycle();
}
function openMapTooltip(id,{auto=false,scroll=false}={}){
  const c=DATA.cinemas.find(x=>x.id===id); if(!c) return;
  MAP_SELECTED_ID=id;
  document.querySelectorAll('.map-marker').forEach(b=>b.classList.toggle('is-active',b.dataset.cinemaId===id));
  highlightCinemaCard(id);

  const st=cinemaSummary(c);
  $('#map-tooltip-chain').textContent=c.chain;
  $('#map-tooltip-title').textContent=c.name;
  $('#map-tooltip-state').textContent=c.state;
  $('#map-tooltip-shows').textContent=st.shows;
  $('#map-tooltip-used').textContent=st.used || st.used===0 ? fmt(st.used) : '—';
  $('#map-tooltip-capacity').textContent=st.capacity ? fmt(st.capacity) : '—';
  $('#map-tooltip-next').innerHTML=nextShowLabel(c);
  $('#map-tooltip-source').textContent=sourceText(c);
  $('#map-tooltip-jump').dataset.cinemaId=id;
  $('#map-tooltip').hidden=false;

  const liveMeta = st.occ==null
    ? `${st.shows} shows · seat feed pending`
    : `${st.shows} shows · ${fmt(st.used)} used / booked · ${st.occ.toFixed(1)}% occupancy`;
  $('#map-live-title').textContent=c.name;
  $('#map-live-meta').textContent=liveMeta;

  if(scroll) jumpToCinema(id);
}
function closeMapTooltip(){
  document.querySelectorAll('.map-marker').forEach(b=>b.classList.remove('is-active'));
  const tip=$('#map-tooltip'); if(tip) tip.hidden=true;
}
function jumpToCinema(id){
  highlightCinemaCard(id);
  const card=document.querySelector(`.cinema-card[data-cinema-id="${id}"]`);
  if(card){
    card.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'nearest'});
    card.focus?.();
  }
}



function showRuntimeError(error){
  const message=error?.message || String(error || 'Unknown dashboard error');
  setText('#updated','Data load failed');
  const panel=$('#runtime-status');
  if(panel){
    panel.hidden=false;
    panel.textContent=`Dashboard error: ${message}`;
  }
}
function clearRuntimeError(){
  const panel=$('#runtime-status');
  if(panel){
    panel.hidden=true;
    panel.textContent='';
  }
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
    const latest=[...HISTORY].filter(x=>x.file).sort((a,b)=>new Date(a.observedAt)-new Date(b.observedAt)).slice(-2);
    HISTORY_DETAIL=(await Promise.all(latest.map(x=>fetchJson(`data/${x.file}`).catch(()=>null)))).filter(Boolean);
  }catch{
    HISTORY=[];
    HISTORY_DETAIL=[];
  }


  initDateFilter();
  initFilters();
  clearRuntimeError();
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
  const sort=$('#sort-filter')?.value || 'occupancy';
  const rows=DATA.cinemas.filter(c=>(!st||c.state===st)&&(!ch||c.chain===ch)&&(!q||c.name.toLowerCase().includes(q)));
  rows.sort((a,b)=>{
    const sa=cinemaSummary(a), sb=cinemaSummary(b);
    if(sort==='used') return sb.used-sa.used || sb.shows-sa.shows || a.name.localeCompare(b.name);
    if(sort==='velocity') return (cinemaVelocity(b.id)??-Infinity)-(cinemaVelocity(a.id)??-Infinity) || (sb.occ??-1)-(sa.occ??-1);
    if(sort==='shows') return sb.shows-sa.shows || (sb.occ??-1)-(sa.occ??-1);
    if(sort==='name') return a.name.localeCompare(b.name);
    return (sb.occ??-1)-(sa.occ??-1) || sb.used-sa.used || a.name.localeCompare(b.name);
  });
  return rows;
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
function cinemaVelocity(cinemaId){
  if(HISTORY_DETAIL.length<2) return null;
  const a=HISTORY_DETAIL[HISTORY_DETAIL.length-2], b=HISTORY_DETAIL[HISTORY_DETAIL.length-1];
  const ta=new Date(a.observedAt), tb=new Date(b.observedAt);
  const hours=(tb-ta)/36e5;
  if(!(hours>0)) return null;
  const total=snap=>(snap.sessions||[])
    .filter(s=>s.cinemaId===cinemaId && Number.isFinite(s.booked))
    .reduce((sum,s)=>sum+s.booked,0);
  return (total(b)-total(a))/hours;
}

function render(){
  const cin=filtered(),s=stats(cin),v=velocity();
  renderMap();
  const dateLabel=new Date(`${DATA.date}T12:00:00+08:00`).toLocaleDateString('en-MY',{dateStyle:'medium'});
  $('#updated').textContent=`${dateLabel} · Updated ${new Date(DATA.updatedAt).toLocaleString('en-MY',{timeStyle:'short'})}`;
  $('#stat-shows').textContent=fmt(s.ss.length); $('#stat-cinemas').textContent=`${s.reporting} cinemas reporting`;
  $('#stat-booked').textContent=s.known.length?fmt(s.used):'—'; $('#stat-booked-sub').textContent=s.known.length?'Across sessions with seat data':'Awaiting seat-map feed'; $('#stat-available').textContent=s.known.length?fmt(s.available):'—';
  $('#stat-occupancy').textContent=s.occ==null?'—':`${s.occ.toFixed(1)}%`;
  $('#stat-capacity').textContent=s.known.length?`${fmt(s.capacity)} observed seats`:'Capacity pending';
  $('#stat-velocity').textContent=v==null?'—':`${v.toFixed(1)}/hr`;
  $('#stat-velocity-sub').textContent=v==null?'Needs 2+ same-day snapshots':'Observed inventory change';
  $('#stat-live-sessions').textContent=fmt(s.known.length);
  $('#stat-live-sub').textContent=s.known.length?'Sessions with live seat data':'Seat feed pending';
  $('#s-locations').textContent=DATA.cinemas.length;
  $('#s-reporting').textContent=s.reporting; $('#s-shows').textContent=s.ss.length; $('#s-matinee').textContent=s.matinee; $('#s-prime').textContent=s.prime; $('#s-late').textContent=s.late;
  $('#s-capacity').textContent=s.known.length?fmt(s.capacity):'—'; $('#s-booked').textContent=s.known.length?fmt(s.used):'—'; $('#s-remaining').textContent=s.known.length?fmt(s.available):'—';
  $('#s-velocity').textContent=v==null?'—':`${v.toFixed(1)}/hr`;
  $('#reporting-note').textContent=s.known.length?`${s.known.length} sessions with observed seat data`:'Showtime feed active · seat feed pending';
  renderBars(cin); renderRanking(cin); renderCinemaList(cin);
}
function renderBars(cin){
  const ordered=[...cin].sort((a,b)=>{
    const sa=cinemaSummary(a), sb=cinemaSummary(b);
    return (sb.occ ?? -1) - (sa.occ ?? -1) || sb.shows-sa.shows;
  });
  $('#bars').innerHTML=ordered.map(c=>{
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
  const host=$('#cinema-list');
  host.className='cinema-grid';
  host.innerHTML='';
  cin.forEach(c=>{
    const sum=cinemaSummary(c);
    const vel=cinemaVelocity(c.id);
    const next=(c.sessions||[]).length ? ((c.sessions||[]).find(s=>!s.isExpired)?.time || c.sessions[0].time) : '—';
    const coverageClass=sum.known===0 ? '' : (sum.known===sum.shows ? ' live' : ' partial');
    const coverageText=sum.known===0 ? 'Seat feed pending' : (sum.known===sum.shows ? 'Full live seat coverage' : `${sum.known}/${sum.shows} sessions live`);
    const sessions=(c.sessions||[]).length ? (c.sessions||[]).map(s=>{
      const known=isKnown(s);
      const pct=known ? `${(s.booked/s.capacity*100).toFixed(0)}%` : 'Pending';
      const label=known
        ? `${fmt(s.booked)} / ${fmt(s.capacity)} ${c.chain==='TGV'?'used':'booked'}`
        : (s.sourceStatus==='fallback-showtime-only' || s.seatStatus==='official-gsc-showtime-not-listed')
          ? 'Fallback only'
          : 'Seat data not observed';
      return `<div class="session-chip">
        <div class="session-chip-top">
          <span class="session-time">${s.time}</span>
          <span class="session-hall">${s.hall && s.hall!=='—' ? s.hall : 'Hall?'}</span>
        </div>
        <strong>${pct}</strong>
        <div class="session-mini">${label}</div>
      </div>`;
    }).join('') : '<div class="empty">Awaiting showtime data for this date.</div>';

    host.insertAdjacentHTML('beforeend', `
      <article class="cinema-card" data-cinema-id="${c.id}" tabindex="-1">
        <div class="cinema-card-head">
          <div>
            <h3>${c.name}</h3>
            <div class="cinema-card-meta">${c.state} · next ${next}${vel==null?'':` · ${vel>=0?'+':''}${vel.toFixed(1)}/hr`}</div>
          </div>
          <span class="chain-pill ${chainClass(c.chain)}">${c.chain}</span>
        </div>

        <div class="cinema-card-stats">
          <span>Shows<b>${sum.shows}</b></span>
          <span>Used / booked<b>${sum.known ? fmt(sum.used) : '—'}</b></span>
          <span>Occ.<b>${sum.occ==null ? '—' : `${sum.occ.toFixed(1)}%`}</b></span>
          <span>Available<b>${sum.known ? fmt(sum.available) : '—'}</b></span>
          <span>Velocity<b>${vel==null?'—':`${vel>=0?'+':''}${vel.toFixed(1)}/hr`}</b></span>
        </div>

        <div class="session-chip-grid">${sessions}</div>
        <span class="coverage-pill${coverageClass}">${coverageText}</span>
      </article>
    `);
  });
  if(MAP_SELECTED_ID) highlightCinemaCard(MAP_SELECTED_ID);
}
document.addEventListener('input',e=>{if(['state-filter','chain-filter','search','sort-filter'].includes(e.target.id))render()});
$('#date-filter').addEventListener('change',e=>{
  const u=new URL(location.href);u.searchParams.set('date',e.target.value);history.replaceState({},'',u);load(e.target.value);
});
$('#refresh').addEventListener('click',()=>load(DATA.date));
$('#map-tooltip-close')?.addEventListener('click',()=>{closeMapTooltip(); pauseMapCycle(false);});
$('#map-tooltip-jump')?.addEventListener('click',e=>jumpToCinema(e.currentTarget.dataset.cinemaId));
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&!$('#map-tooltip')?.hidden){
    closeMapTooltip();
    pauseMapCycle(false);
  }
});
$('#malaysia-map')?.addEventListener('mouseenter',()=>pauseMapCycle(true));
$('#malaysia-map')?.addEventListener('mouseleave',()=>pauseMapCycle(false));
window.addEventListener('error',event=>{
  console.error(event.error||event.message);
  showRuntimeError(event.error||event.message);
});
window.addEventListener('unhandledrejection',event=>{
  console.error(event.reason);
  showRuntimeError(event.reason);
});
load().catch(err=>{
  console.error(err);
  showRuntimeError(err);
});
