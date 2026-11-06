import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api} from '../services/api';
export function useRecords(collection,initial={}){
 const [filters,setFilters]=useState(initial);const [offset,setOffset]=useState(0);const [limit,setLimit]=useState(25);
 const params=new URLSearchParams(Object.entries({...filters,limit,offset}).filter(([,v])=>v!==''&&v!=null));const url='/records/'+collection+'?'+params;
 const query=useQuery({queryKey:[url],queryFn:async()=>(await api.get(url)).data});
 return {...query,items:query.data?.items||[],total:query.data?.total||0,filters,offset,limit,setOffset,setLimit:n=>{setLimit(n);setOffset(0);},setFilter:(key,value)=>{setFilters(f=>({...f,[key]:value}));setOffset(0);}};
}
