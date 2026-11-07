'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const report = window.__PULSEPROOF_REPORT__;
  let state = {runs:[],scenarios:[],job:{}}, selected, token, busy=false,zoom=false;
  const ns = value => value == null ? '—' : value >= 1e6 ? (value/1e6).toFixed(2)+' ms' : (value/1e3).toFixed(1)+' µs';
  const txt = (id, value) => { $(id).textContent = value; };
  function metric(id, value) {
    const node=$(id); node.replaceChildren();
    if(value==null){node.textContent='—';return;}
    const parts=ns(value).split(' '); node.append(document.createTextNode(parts[0]+' '));
    const unit=document.createElement('em');unit.textContent=parts[1];node.append(unit);
  }
  function notice(message) { $('notice').hidden=!message; txt('notice',message||''); }
  async function api(url, options) {
    const response=await fetch(url,options); const body=await response.json();
    if(!response.ok) throw new Error(body.error||'Request failed'); return body;
  }
  function svgNode(name, attributes={}, text) {
    const node=document.createElementNS('http://www.w3.org/2000/svg',name);
    for(const [key,value] of Object.entries(attributes))node.setAttribute(key,String(value));
    if(text!=null)node.textContent=text; return node;
  }
  function grid(svg,width,height,maxX,maxY,xLabel) {
    const left=58,right=20,top=20,bottom=37,w=width-left-right,h=height-top-bottom;
    const x=v=>left+v/Math.max(maxX,1)*w,y=v=>top+h-v/Math.max(maxY,1)*h;
    for(let i=0;i<=4;i++) {
      const yy=top+i*h/4;
      svg.append(svgNode('line',{x1:left,x2:width-right,y1:yy,y2:yy,stroke:'#e9ede4','stroke-dasharray':'3 4'}));
      svg.append(svgNode('text',{x:left-10,y:yy+3,'text-anchor':'end',fill:'#9aa38f','font-size':9,'font-family':'Consolas,monospace'},xLabel ? (100-i*25)+'%' : ns(maxY*(1-i/4))));
    }
    for(let i=0;i<=4;i++) {
      const v=maxX*i/4;
      svg.append(svgNode('text',{x:x(v),y:height-13,'text-anchor':'middle',fill:'#9aa38f','font-size':9,'font-family':'Consolas,monospace'},xLabel?ns(v):Math.round(v)));
    }
    return {x,y,left,top,w,h};
  }
  function charts(run) {
    const samples=run.samples,timeline=$('timeline');timeline.replaceChildren();
    const deadline=run.scenario.parameters.deadline_us*1000;
    const maxY=Math.max(zoom?0:deadline,...samples.map(s=>s.latency_ns))*1.12;
    const {x,y}=grid(timeline,900,260,samples.length-1,maxY,false);
    if(deadline<=maxY){
      timeline.append(svgNode('line',{x1:58,x2:880,y1:y(deadline),y2:y(deadline),stroke:'#c69165','stroke-dasharray':'5 4','stroke-width':1}));
      timeline.append(svgNode('text',{x:875,y:y(deadline)-7,'text-anchor':'end',fill:'#ad845d','font-size':9,'font-family':'Consolas,monospace'},'DEADLINE '+ns(deadline)));
    }else timeline.append(svgNode('text',{x:875,y:17,'text-anchor':'end',fill:'#ad845d','font-size':9},'Budget '+ns(deadline)+' above displayed range'));
    const points=samples.map((s,i)=>x(i)+','+y(s.latency_ns)).join(' ');
    timeline.append(svgNode('polygon',{points:'58,223 '+points+' '+x(samples.length-1)+',223',fill:'#eaf2e5',opacity:.75}));
    timeline.append(svgNode('polyline',{points,fill:'none',stroke:'#579474','stroke-width':1.7,'stroke-linejoin':'round'}));
    samples.forEach((s,i)=> {if(s.deadline_miss||s.timeout)timeline.append(svgNode('circle',{cx:x(i),cy:y(s.latency_ns),r:3,fill:'#be6b50'}));});
    const cursor=svgNode('line',{x1:0,x2:0,y1:20,y2:223,stroke:'#7b9272','stroke-dasharray':'2 3',visibility:'hidden'});timeline.append(cursor);
    timeline.onpointermove=event=>{
      const rect=timeline.getBoundingClientRect(),px=(event.clientX-rect.left)*900/rect.width;
      const index=Math.max(0,Math.min(samples.length-1,Math.round((px-58)/822*(samples.length-1))));
      const s=samples[index];cursor.setAttribute('x1',x(index));cursor.setAttribute('x2',x(index));cursor.setAttribute('visibility','visible');
      txt('tooltip',`Sample ${index} · ${ns(s.latency_ns)}\nWake lateness ${ns(s.wake_lateness_ns)}\n${s.timeout?'KERNEL TIMEOUT':s.deadline_miss?'DEADLINE MISS':'OK'}${s.recovery?' · RECOVERY':''}${s.injected?' · INJECTED STALL':''}`);
      $('tooltip').hidden=false;$('tooltip').style.left=Math.min(rect.width-245,Math.max(5,event.clientX-rect.left+10))+'px';
    };
    timeline.onpointerleave=()=>{$('tooltip').hidden=true;cursor.setAttribute('visibility','hidden');};
    const values=samples.filter(s=>!s.error).map(s=>s.latency_ns).sort((a,b)=>a-b),cdf=$('distribution');cdf.replaceChildren();
    if(values.length){
      const coords=grid(cdf,430,260,values[values.length-1]*1.08,100,true);
      let path='M '+coords.x(values[0])+' '+coords.y(0);
      values.forEach((v,i)=>{path+=' H '+coords.x(v)+' V '+coords.y((i+1)*100/values.length);});
      cdf.append(svgNode('path',{d:path,fill:'none',stroke:'#579474','stroke-width':2}));
    }
    txt('distribution-count',values.length+' SUCCESSFUL / '+samples.length+' TOTAL');
  }
  function exports(run) {
    if(!report){
      for(const [id,file] of [['json-download','summary.json'],['csv-download','samples.csv'],['raw-download','raw.ndjson'],['report-download','report.html']]){$(id).href='/api/runs/'+run.run_id+'/'+file;$(id).download=run.scenario.id+'-'+file;}
      $('report-download').hidden=false;
    } else {
      $('report-download').hidden=true;$('raw-download').hidden=true;
      const blob=(id,body,type,name)=>{$(id).href=URL.createObjectURL(new Blob([body],{type}));$(id).download=name;};
      blob('json-download',JSON.stringify(run,null,2),'application/json','summary.json');
      const fields=Object.keys(run.samples[0]);const rows=[fields.join(','),...run.samples.map(s=>fields.map(f=>String(s[f])).join(','))];
      blob('csv-download',rows.join('\n'),'text/csv','samples.csv');
    }
  }
  function render(run) {
    selected=run;$('results').hidden=false;$('empty').hidden=true;
    txt('experiment-name',run.scenario.id);txt('experiment-description',run.scenario.description);
    txt('source-badge',run.source==='qnx-native'?'● REAL QNX MEASUREMENT':'SYNTHETIC FIXTURE');$('source-badge').classList.toggle('synthetic',run.source!=='qnx-native');
    txt('verdict',run.verdict);$('verdict').classList.toggle('fail',run.verdict!=='PASS');
    txt('run-id',run.run_id||'Offline analysis');txt('run-time',run.created_at?new Date(run.created_at).toLocaleString():'');
    txt('sample-count',run.samples.length+' samples');txt('deadline','Deadline '+ns(run.scenario.parameters.deadline_us*1000));
    for(const key of ['p50','p95','p99'])metric(key,run.successful_latency[key+'_ns']);
    txt('misses',run.deadline_misses);txt('miss-rate',(run.deadline_misses/run.samples.length*100).toFixed(1)+'% of all attempts · allowed '+run.scenario.gates.max_deadline_misses);
    document.querySelector('.deadline-card').classList.toggle('has-misses',run.deadline_misses>run.scenario.gates.max_deadline_misses);
    txt('timeline-caption',run.scenario.mode==='timer'?'Scheduled release → work completion, including backlog.':'Client send → reply or kernel timeout. Recovery attempts included.');
    charts(run);$('gates').replaceChildren();
    run.checks.forEach(check=>{
      const row=document.createElement('tr');const latency=check.name.startsWith('p99');
      const policy=check.name==='expected timeouts'?'= ':check.name==='successful recoveries'?'≥ ':'≤ ';
      for(const text of [check.name,latency?ns(check.actual):String(check.actual),policy+(latency?ns(check.limit):check.limit)]){const cell=document.createElement('td');cell.textContent=text;row.append(cell);}
      const cell=document.createElement('td'),badge=document.createElement('span');badge.className=check.pass?'gate-pass':'gate-fail';badge.textContent=check.pass?'PASS':'FAIL';cell.append(badge);row.append(cell);$('gates').append(row);
    });
    txt('gate-count',run.checks.filter(c=>c.pass).length+' / '+run.checks.length+' PASSED');
    txt('native-api',run.scenario.mode==='service'?'Independent application · name_open · MsgSend':run.scenario.mode==='ipc'?'ChannelCreate · MsgSend · TimerTimeout':'clock_nanosleep · CLOCK_MONOTONIC');
    $('runtime-details').replaceChildren();
    const m=run.metadata;
    const details={'Guest CPU busy estimate':run.system_busy_fraction==null?'Unavailable':(100*run.system_busy_fraction).toFixed(1)+'%','Kernel timeouts':run.timeouts,'Unobserved deadlines':run.unobserved_deadlines??'Legacy run','Successful recoveries':run.recoveries,'Load threads':m.load_threads,'Agent CPU equivalents':run.process_cpu_equivalents.toFixed(2),'Scheduling':m.scheduler+' / '+m.priority,'Target CPUs / clock tick':m.cpu_count+' / '+ns(m.tick_ns),'Minimum clock-read pair':m.clock_read_min_ns+' ns'};
    if(run.provenance?.application){details['Application build']=run.provenance.application.variant;details['Fixture payload']='Real QNX timing · deterministic values';}
    for(const [key,value] of Object.entries(details)){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=key;dd.textContent=value;$('runtime-details').append(dt,dd);}
    txt('agent-hash',run.provenance?.agent_sha256||'Not supplied in offline analysis');txt('raw-hash',run.provenance?.raw_sha256||'Not supplied in offline analysis');
    txt('evidence-caption',(m.os||'')+' '+(m.release||'')+' · '+(m.arch||'')+' · '+m.clock+' · buffered capture');
    txt('comparison-result','');$('baseline').replaceChildren();
    const compatible=state.runs.filter(item=>item.run_id!==run.run_id&&item.target_os===run.target_os&&JSON.stringify(item.scenario.gates)===JSON.stringify(run.scenario.gates)&&item.comparison_signature===run.comparison_signature&&item.provenance?.agent_sha256===run.provenance?.agent_sha256&&JSON.stringify(item.provenance?.target_environment)===JSON.stringify(run.provenance?.target_environment));
    if(!compatible.length){const option=document.createElement('option');option.textContent='No compatible earlier run';option.value='';$('baseline').append(option);}
    compatible.forEach(item=>{const option=document.createElement('option');option.value=item.run_id;option.textContent=item.scenario.id+' · '+new Date(item.created_at).toLocaleTimeString();$('baseline').append(option);});
    $('compare').disabled=!compatible.length||!!report;
    document.querySelector('.comparison-panel').hidden=!!report;
    exports(run);renderHistory();
  }
  function renderHistory() {
    $('history').replaceChildren();txt('run-count',state.runs.length);txt('history-count',state.runs.length);
    $('run-picker').replaceChildren();
    state.runs.forEach(item=>{
      const option=document.createElement('option');option.value=item.run_id;option.textContent=item.scenario.id+' · '+item.verdict+' · '+(item.created_at?new Date(item.created_at).toLocaleTimeString():'');$('run-picker').append(option);
      const button=document.createElement('button');button.type='button';button.className='history-item'+(item.run_id===selected?.run_id?' selected':'');
      const dot=document.createElement('span');dot.className='history-dot'+(item.verdict==='PASS'?'':' fail');dot.textContent='●';
      const small=document.createElement('small');small.textContent=(item.created_at?new Date(item.created_at).toLocaleTimeString():'')+' · '+item.verdict;
      button.append(dot,document.createTextNode(item.scenario.id),small);button.onclick=()=>report?render(report):selectRun(item.run_id);$('history').append(button);
    });
    if(selected)$('run-picker').value=selected.run_id;
  }
  $('run-picker').onchange=()=>selectRun($('run-picker').value);
  async function selectRun(id) {try{render(await api('/api/runs/'+id+'/summary.json'));}catch(error){notice(error.message);}}
  async function refresh(chooseNew=false) {
    state=await api('/api/state');token=state.token;
    if(!$('scenario').options.length){state.scenarios.forEach(s=>{const option=document.createElement('option');option.value=s.id;option.textContent=s.id;$('scenario').append(option);});$('scenario').value='timer-baseline';}
    $('run').disabled=state.job.running;txt('run',state.job.running?'Measuring on QNX…':'▶ Run experiment');
    renderHistory();
    if(state.runs.length&&(!selected||chooseNew))await selectRun(chooseNew&&state.job.run_id?state.job.run_id:state.runs[0].run_id);
    if(!state.runs.length)$('empty').hidden=false;
    if(state.job.error)notice(state.job.error);
    return state.job.running;
  }
  async function checkTarget(){
    if(report)return;
    $('target-check').disabled=true;txt('target-state','Checking QNX…');
    try{const result=await api('/api/target');txt('target-state',result.connected?'QNX connected · SSH verified':'Target offline · showing recorded data');txt('target-detail',result.connected?'Checked '+new Date(result.checked_at).toLocaleTimeString():'Connection check failed');}
    catch(error){txt('target-state','Target status unavailable');}
    finally{$('target-check').disabled=false;}
  }
  $('target-check').onclick=checkTarget;
  $('scale-toggle').onclick=()=>{zoom=!zoom;$('scale-toggle').setAttribute('aria-pressed',String(zoom));txt('scale-toggle',zoom?'Show deadline range':'Zoom measured range');if(selected)charts(selected);};
  $('refresh').onclick=()=>refresh().then(checkTarget).catch(e=>notice(e.message));
  $('run').onclick=async()=>{
    if(busy)return;busy=true;notice('Running on the QNX target. Evidence will appear after the complete stream is verified.');
    try{
      await api('/api/run',{method:'POST',headers:{'Content-Type':'application/json','X-PulseProof-Token':token},body:JSON.stringify({scenario:$('scenario').value})});
      $('run').disabled=true;
      while(await refresh(false))await new Promise(resolve=>setTimeout(resolve,700));
      await refresh(true);if(!state.job.error)notice('Experiment complete. Results below are from the real QNX target.');
    }catch(error){notice(error.message);}finally{busy=false;$('run').disabled=false;}
  };
  $('compare').onclick=async()=>{
    try{
      const result=await api('/api/compare?baseline='+encodeURIComponent($('baseline').value)+'&candidate='+encodeURIComponent(selected.run_id));
      const delta=result.change_percent;
      txt('comparison-result',result.verdict+' · P99 '+(delta>=0?'+':'')+delta.toFixed(1)+'% · '+ns(result.baseline_p99_ns)+' → '+ns(result.candidate_p99_ns)+' · maximum regression '+result.limit_percent+'% · evidence verified');
    }catch(error){txt('comparison-result',error.message);}
  };
  if(report){state.runs=[report];$('scenario-panel').hidden=true;$('refresh').hidden=true;$('target-check').hidden=true;txt('target-state','Recorded QNX experiment');$('run-picker').disabled=true;render(report);}
  else refresh().then(checkTarget).catch(error=>{notice('Workbench could not load: '+error.message);$('empty').hidden=false;});
})();
