"""Generate explicitly synthetic source files; never seed compliance conclusions."""
from pathlib import Path
from docx import Document
from openpyxl import Workbook
import pymupdf

root=Path(__file__).resolve().parents[1]/'sample_data'
root.mkdir(exist_ok=True)
examples={
 'DEMONSTRATION-regulatory-requirements.txt':'1 Training\nPersonnel must receive role-specific training before operating equipment.\nTraining effectiveness should be evaluated.\n2 Validation\nEquipment qualification records must identify the equipment, acceptance criteria, execution results, and approval.',
 'DEMONSTRATION-SOP.txt':'1 Responsibilities\nQuality Assurance maintains approved procedures.\n2 Training\nOperators complete initial equipment training. Attendance records are retained by QA. Effectiveness assessment is outside this document.\n3 Equipment\nQualified equipment is used for processing. Qualification records are maintained separately.',
 'DEMONSTRATION-qualification.txt':'1 Qualification\nThe engineering team documents installation, operation, and performance qualification. QA reviews acceptance criteria and approves qualification records.',
 'DEMONSTRATION-validation.txt':'1 Validation\nValidation protocols define acceptance criteria and sampling plans. Deviations are investigated before QA approval.',
 'DEMONSTRATION-audit-observations.txt':'Training attendance records were available for two operators in this synthetic example. No effectiveness assessment record was supplied. This observation is not a confirmed operational violation.'}
for name,text in examples.items():
    (root/name).write_text('DEMONSTRATION DATA — SYNTHETIC, NOT OFFICIAL REGULATORY TEXT\n'+text,encoding='utf-8')
doc=Document();doc.add_heading('DEMONSTRATION DATA — Synthetic SOP',0);doc.add_paragraph(examples['DEMONSTRATION-SOP.txt']);doc.save(root/'DEMONSTRATION-SOP.docx')
book=Workbook();sheet=book.active;sheet.title='DEMONSTRATION DATA';sheet.append(['DEMONSTRATION DATA - synthetic training records']);sheet.append(['Employee','Role','Course','Date','Effectiveness record']);sheet.append(['SYN-001','Operator','Equipment operation','2026-10-01','Not supplied']);book.save(root/'DEMONSTRATION-training.xlsx')
pdf=pymupdf.open();page=pdf.new_page();page.insert_textbox((45,45,550,780),'DEMONSTRATION DATA - SYNTHETIC, NOT OFFICIAL\n'+examples['DEMONSTRATION-regulatory-requirements.txt'],fontsize=11);pdf.save(root/'DEMONSTRATION-regulation.pdf')
print('Synthetic source files generated:',root)
