import {describe,it,expect,vi,afterEach} from 'vitest';
import axios from 'axios';
import {api,saveTokens,clearTokens} from './api';
afterEach(()=>{vi.restoreAllMocks();clearTokens();});
describe('Session renewal',()=>{
 it('rotates refresh tokens and retries an expired request',async()=>{
  saveTokens({access_token:'expired',refresh_token:'old-refresh'});
  const post=vi.spyOn(axios,'post').mockResolvedValue({data:{access_token:'new-access',refresh_token:'new-refresh'}});
  const adapter=api.defaults.adapter;
  api.defaults.adapter=async config=>{if(!config._retried)throw {response:{status:401},config};return {data:{ok:true},status:200,statusText:'OK',headers:{},config};};
  try{const response=await api.get('/settings');expect(response.data.ok).toBe(true);expect(sessionStorage.getItem('token')).toBe('new-access');expect(sessionStorage.getItem('refresh_token')).toBe('new-refresh');expect(post).toHaveBeenCalledOnce();}finally{api.defaults.adapter=adapter;}
 });
 it('clears both credentials together',()=>{saveTokens({access_token:'a',refresh_token:'b'});clearTokens();expect(sessionStorage.getItem('token')).toBeNull();expect(sessionStorage.getItem('refresh_token')).toBeNull();});
});
