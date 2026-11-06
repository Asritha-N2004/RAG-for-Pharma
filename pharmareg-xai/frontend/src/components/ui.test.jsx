import React from 'react';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,describe,it,expect,vi} from 'vitest';
import {Badge,Source,Empty} from './ui';
afterEach(cleanup);
describe('Evidence presentation',()=>{
 it('explicitly labels missing rendered pages',()=>{render(<Source source={{document_title:'SOP',version:'1',page:null,text:'Source evidence',chunk_id:'abc'}} onOpen={()=>{}}/>);expect(screen.getByText(/Page unavailable/)).toBeTruthy();});
 it('opens original source through protected action',()=>{const open=vi.fn();render(<Source source={{document_title:'SOP',version:'1',page:3,text:'Exact source',chunk_id:'abc'}} onOpen={open}/>);fireEvent.click(screen.getByText('Open original document'));expect(open).toHaveBeenCalledTimes(1);});
 it('renders untrusted source text as text',()=>{render(<Source source={{document_title:'SOP',version:'1',text:'<script>alert(1)</script>',chunk_id:'abc'}} onOpen={()=>{}}/>);expect(document.querySelector('script')).toBeNull();expect(screen.getByText('<script>alert(1)</script>')).toBeTruthy();});
 it('labels insufficient evidence without a violation claim',()=>{render(<Badge>INSUFFICIENT_EVIDENCE</Badge>);expect(screen.getByText('INSUFFICIENT EVIDENCE')).toBeTruthy();});
});
