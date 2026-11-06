import axios from 'axios';
export const api=axios.create({baseURL:'/api'});
let refreshRequest=null;
export function saveTokens(tokens){sessionStorage.setItem('token',tokens.access_token);sessionStorage.setItem('refresh_token',tokens.refresh_token);}
export function clearTokens(){sessionStorage.removeItem('token');sessionStorage.removeItem('refresh_token');}
api.interceptors.request.use(c=>{const token=sessionStorage.getItem('token');if(token)c.headers.Authorization='Bearer '+token;return c;});
api.interceptors.response.use(r=>r,async error=>{
 const config=error.config;
 if(error.response?.status!==401||!config||config._retried||config.url.startsWith('/auth/'))throw error;
 const refresh=sessionStorage.getItem('refresh_token');if(!refresh)throw error;
 config._retried=true;
 try{
  if(!refreshRequest)refreshRequest=axios.post('/api/auth/refresh',{refresh_token:refresh}).then(r=>{saveTokens(r.data);return r.data.access_token;}).finally(()=>{refreshRequest=null;});
  const token=await refreshRequest;config.headers.Authorization='Bearer '+token;return api(config);
 }catch(e){clearTokens();window.dispatchEvent(new Event('session-expired'));throw e;}
});
export async function download(url,name){const {data}=await api.get(url,{responseType:'blob'});const u=URL.createObjectURL(data);const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
export function errorMessage(e){const d=e.response?.data?.detail;return typeof d==='string'?d:Array.isArray(d)?d.map(x=>x.msg).join('; '):e.message;}
