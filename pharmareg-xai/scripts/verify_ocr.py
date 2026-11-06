from pathlib import Path
import os,sys,json
root=Path(__file__).resolve().parents[1];os.environ['TESSDATA_PREFIX']=str(root/'storage'/'tessdata');os.environ['OCR_ENABLED']='true';sys.path.insert(0,str(root/'backend'))
import pymupdf
from PIL import Image,ImageDraw,ImageFont
from app.services.extraction_service import extract
image=Image.new('RGB',(1800,800),'white');draw=ImageDraw.Draw(image);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',48)
draw.text((70,70),'DEMONSTRATION DATA - SCANNED TRAINING RECORD',font=font,fill='black')
draw.text((70,180),'Training records are retained by Quality Assurance.',font=font,fill='black')
draw.text((70,290),'Operator training was completed on 2026-10-01.',font=font,fill='black')
folder=root/'storage'/'ocr-verification';folder.mkdir(parents=True,exist_ok=True);png=folder/'scan.png';image.save(png)
doc=pymupdf.open();page=doc.new_page(width=900,height=400);page.insert_image(page.rect,filename=str(png));pdf=folder/'DEMONSTRATION-scanned-record.pdf';doc.save(pdf);doc.close()
pages=extract(pdf);assert pages[0][0]==1 and 'Training records' in pages[0][1],pages
result={'actual_ocr':True,'engine':'PyMuPDF integrated Tesseract with tessdata_fast English','page':pages[0][0],'text':pages[0][1]}
(root/'docs'/'OCR_RESULTS.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
