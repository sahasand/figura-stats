import { WebR } from "https://webr.r-wasm.org/latest/webr.mjs";
let ready;
let queue = Promise.resolve();
async function boot() {
  const r = new WebR();
  self.postMessage({status:"Loading R in this browser…"});
  await r.init();
  self.postMessage({status:"Loading the power-analysis library…"});
  await r.installPackages(["jsonlite","pwr"],{quiet:true});
  const response=await fetch(new URL("../R/sample-size.R",import.meta.url),{cache:"reload"});
  if(!response.ok) throw new Error("The planning engine could not be loaded. Try again.");
  await r.evalRVoid(await response.text());
  self.postMessage({status:"R ready · calculations stay in this tab"});
  return r;
}
self.onmessage=({data})=>{
  queue=queue.then(async()=>{
    try {
      if(!ready) ready=boot().catch(e=>{ready=null;throw e;});
      const r=await ready;
      const shelter=await new r.Shelter();
      try {
        const value=await shelter.evalR("as.character(sample_size_json(planning_input))",
          {env:{planning_input:JSON.stringify(data.spec)},captureStreams:false});
        const [json]=await value.toArray();
        self.postMessage({id:data.id,...JSON.parse(json)});
      } finally { await shelter.purge(); }
    } catch(error) {self.postMessage({id:data.id,ok:false,error:String(error.message||error)});}
  });
};
