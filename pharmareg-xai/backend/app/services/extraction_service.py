"""Format-aware extraction; never invent rendered page numbers for Office files."""
import io, re, zipfile
from pathlib import Path
from fastapi import HTTPException
from app.core.config import MAX_UPLOAD

ALLOWED = {'.pdf','.docx','.txt','.csv','.xlsx'}
def validate_file(name, data):
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED: raise HTTPException(415, 'Supported types: PDF, DOCX, TXT, CSV, XLSX')
    if not data or len(data)>MAX_UPLOAD: raise HTTPException(413, 'File is empty or exceeds upload limit')
    if ext == '.pdf' and not data.startswith(b'%PDF-'): raise HTTPException(415, 'Invalid PDF signature')
    if ext in {'.docx','.xlsx'}:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(x.file_size for x in archive.infolist()) > MAX_UPLOAD * 4: raise ValueError('Archive expands beyond limit')
                marker = 'word/document.xml' if ext == '.docx' else 'xl/workbook.xml'
                if marker not in archive.namelist(): raise ValueError('Invalid Office document')
        except (zipfile.BadZipFile, ValueError) as exc: raise HTTPException(415, str(exc))
    if ext in {'.txt','.csv'}:
        try: data.decode('utf-8-sig')
        except UnicodeDecodeError: raise HTTPException(415, 'Text files must be UTF-8')
    return ext

def extract(path):
    if str(path).startswith('blob:') or Path(path).suffix.lower()=='.enc':
        from app.services.storage_service import materialize
        with materialize(path) as temporary:return extract(temporary)
    ext = Path(path).suffix.lower()
    if ext == '.pdf':
        import pymupdf
        pages = []
        with pymupdf.open(path) as document:
            import os
            if len(document)>int(os.getenv('MAX_DOCUMENT_PAGES','1000')):raise ValueError('PDF exceeds configured page-processing limit')
            for i, page in enumerate(document):
                text = page.get_text('text')
                if len(text.strip()) < 20:
                    import os
                    if os.getenv('OCR_ENABLED','true').lower() != 'true':
                        raise ValueError('Scanned page requires OCR, but OCR is disabled')
                    try: text = page.get_text(textpage=page.get_textpage_ocr(language='eng', dpi=200, full=True))
                    except Exception as exc: raise ValueError('OCR requires Tesseract and English tessdata; install them and retry') from exc
                if not text.strip(): raise ValueError(f'No extractable text on PDF page {i+1}')
                pages.append((i+1, text))
        return pages
    if ext == '.docx':
        from docx import Document
        doc = Document(path)
        text = '\n'.join(p.text for p in doc.paragraphs)
        text += '\n' + '\n'.join(' | '.join(c.text for c in row.cells) for table in doc.tables for row in table.rows)
        return [(None,text)]
    if ext == '.xlsx':
        from openpyxl import load_workbook
        book = load_workbook(path, read_only=True, data_only=False)
        try: return [(None, f'Sheet: {s.title}\n'+'\n'.join(' | '.join(str(v or '') for v in row) for row in s.values)) for s in book]
        finally: book.close()
    return [(None,Path(path).read_text(encoding='utf-8-sig'))]

def chunks(pages, size=None, overlap=None):
    import os
    size=int(os.getenv('CHUNK_SIZE','1200')) if size is None else size
    overlap=int(os.getenv('CHUNK_OVERLAP','160')) if overlap is None else overlap
    maximum=int(os.getenv('MAX_CHUNK_SIZE','4000'))
    if not 32<=size<=maximum or not 0<=overlap<size:raise ValueError('Chunk configuration requires 32 ≤ size ≤ maximum and 0 ≤ overlap < size')
    section = ''
    for page, text in pages:
        buffer = ''
        for line in text.splitlines():
            line = line.strip()
            if not line: continue
            if re.match(r'^(?:\d+(?:\.\d+)*[.)]?\s+[A-Z]|[IVXLCDM]+\.\s+[A-Z]|[A-Z]\.\s+[A-Z])',line) and len(line)<180:
                if buffer: yield page, section, buffer.strip(); buffer=''
                section = line
            sentences=[]
            for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])',line):
                while len(sentence)>maximum:
                    cut=sentence.rfind(' ',0,maximum+1)
                    if cut<1:cut=maximum
                    sentences.append(sentence[:cut]);sentence=sentence[cut:].lstrip()
                if sentence:sentences.append(sentence)
            for sentence in sentences:
                if buffer and len(buffer)+len(sentence)>size:
                    yield page,section,buffer.strip()
                    buffer = buffer[-overlap:]+' ' if overlap else ''
                buffer += sentence+'\n'
        if buffer.strip(): yield page,section,buffer.strip()
