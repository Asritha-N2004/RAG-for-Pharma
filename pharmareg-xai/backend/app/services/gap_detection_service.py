"""Documentary screening candidates, never proof of an operational violation."""
import re
RULES={
 'RESPONSIBILITIES':(r'\b(responsibilit\w*|accountable|owner|assigned to)\b','Confirm named responsibilities and accountable roles.'),
 'APPROVAL_RECORD':(r'\b(approv\w*|signatur\w*|signed)\b','Obtain the applicable approval record or controlled-document authorization.'),
 'TRAINING_EVIDENCE':(r'\b(train\w*|competenc\w*)\b','Review whether role-specific training evidence is required within scope.'),
 'VALIDATION_EVIDENCE':(r'\b(validat\w*|qualif\w*)\b','Review whether validation or qualification records are required within scope.'),
 'REVIEW_DATE':(r'\b(review date|next review|reviewed on|effective date)\b','Confirm current review/effective dates in controlled metadata.'),
 'REVISION_HISTORY':(r'\b(revision history|change history|version history|revision log)\b','Check the controlled revision history or linked document management record.')}
def screen(chunks):
    text='\n'.join(c.text for c in chunks)
    return [{'category':name,'kind':'MISSING_DOCUMENTED_ELEMENT_CANDIDATE','recommendation':action,'explanation':'No matching documentary terminology was found in the selected source text. The element may be in supporting records or outside scope.','requires_human_review':True} for name,(pattern,action) in RULES.items() if not re.search(pattern,text,re.I)]
