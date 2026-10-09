// ESN Starter partner referral edge (Cloudflare Worker + D1).
// Configure D1 binding DB, STRIPE_WEBHOOK_SECRET and STRIPE_SECRET_KEY as secrets.
// Never store secrets in repository.
const STARTER = "https://buy.stripe.com/9B628scRZ2jZ9Nl5pZdnW04";
const enc = new TextEncoder();
function hex(bytes){return [...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,"0")).join("");}
async function signatureValid(raw, header, secret) {
  const parts = Object.fromEntries((header||"").split(",").map(s=>s.trim().split("=")).filter(a=>a.length===2));
  const timestamp = Number(parts.t);
  if(!Number.isFinite(timestamp) || Math.abs(Date.now()/1000-timestamp)>300) return false;
  const key = await crypto.subtle.importKey("raw",enc.encode(secret),"HMAC",false,["sign"]);
  const expected = hex(await crypto.subtle.sign("HMAC",key,enc.encode(parts.t+"."+raw)));
  const candidates = (header||"").split(",").filter(s=>s.trim().startsWith("v1=")).map(s=>s.trim().slice(3));
  return candidates.some(v=>v.length===expected.length && v===expected);
}
function json(x,status=200){return new Response(JSON.stringify(x),{status,headers:{"content-type":"application/json"}});}
export default {
 async fetch(request,env){
  const url = new URL(request.url);
  if(url.pathname==="/health")return json({ok:true});
  const m = url.pathname.match(/^\/ref\/([A-Z0-9]{8,32})\/starter$/);
  if(m && request.method==="GET"){
    const partner=await env.DB.prepare("SELECT status FROM partners WHERE code=?").bind(m[1]).first();
    if(!partner || partner.status!=="approved")return json({error:"Unknown referral"},404);
    const dest=new URL(STARTER);dest.searchParams.set("client_reference_id",m[1]);
    return Response.redirect(dest.toString(),302);
  }
  if(url.pathname!=="/stripe/webhook"||request.method!=="POST")return json({error:"Not found"},404);
  if(!env.STRIPE_WEBHOOK_SECRET||!env.STRIPE_SECRET_KEY)return json({error:"Not configured"},503);
  const raw=await request.text();
  if(!(await signatureValid(raw,request.headers.get("Stripe-Signature"),env.STRIPE_WEBHOOK_SECRET)))
    return json({error:"Invalid signature"},400);
  const event=JSON.parse(raw);
  if(!["checkout.session.completed","checkout.session.async_payment_succeeded"].includes(event.type))
    return json({received:true});
  const session=event.data.object;
  if(session.payment_status!=="paid"||session.mode!=="payment"||!session.client_reference_id)
    return json({received:true,skipped:true});
  const verifiedResponse=await fetch("https://api.stripe.com/v1/checkout/sessions/"+encodeURIComponent(session.id),
    {headers:{Authorization:"Bearer "+env.STRIPE_SECRET_KEY}});
  if(!verifiedResponse.ok)return json({error:"Stripe verification failed"},503);
  const verified=await verifiedResponse.json();
  if(verified.payment_status!=="paid"||verified.mode!=="payment"||
     verified.client_reference_id!==session.client_reference_id||
     verified.payment_link!==env.STARTER_PAYMENT_LINK_ID)
    return json({received:true,skipped:"mismatched checkout"});
  if(!verified.customer||!verified.payment_intent||!Number.isInteger(verified.amount_subtotal)||verified.amount_subtotal<=0)
    return json({received:true,skipped:"missing customer or amount"});
  const p=await env.DB.prepare("SELECT id,discord_id FROM partners WHERE code=? AND status='approved'")
    .bind(verified.client_reference_id).first();
  if(!p)return json({received:true,skipped:"unapproved partner"});
  const count=await env.DB.prepare("SELECT count(*) AS n FROM referrals WHERE partner_id=? AND state!='reversed'")
    .bind(p.id).first();
  const rate=count.n>=15?15:count.n>=5?10:5;
  const commission=Math.round(verified.amount_subtotal*rate/100);
  const now=new Date(),hold=new Date(now.getTime()+30*86400000);
  try{
    await env.DB.prepare(`INSERT INTO referrals
      (partner_id,customer_id,stripe_payment_id,amount_cents,commission_cents,rate,state,created_at,eligible_after)
      VALUES (?,?,?,?,?,?,'held',?,?)`)
      .bind(p.id,verified.customer,verified.payment_intent,verified.amount_subtotal,commission,rate,now.toISOString(),hold.toISOString()).run();
  }catch(e){
    // UNIQUE constraints make webhook delivery idempotent, including repeat customers.
    if(String(e).includes("UNIQUE constraint failed"))return json({received:true,duplicate:true});
    return json({error:"Database error"},503);
  }
  return json({received:true});
 }
};
