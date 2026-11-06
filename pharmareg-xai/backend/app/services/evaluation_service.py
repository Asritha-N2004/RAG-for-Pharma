import math
def classification_metrics(expected,predicted):
    from app.services.rag_service import STATUSES
    labels=sorted(STATUSES);matrix={a:{b:0 for b in labels} for a in labels}
    for actual,prediction in zip(expected,predicted,strict=True):matrix[actual][prediction]+=1
    per_class={}
    for label in labels:
        tp=matrix[label][label];fp=sum(matrix[x][label] for x in labels if x!=label);fn=sum(matrix[label][x] for x in labels if x!=label)
        precision=tp/(tp+fp) if tp+fp else 0;recall=tp/(tp+fn) if tp+fn else 0
        per_class[label]={'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0,'support':sum(matrix[label].values())}
    return {'accuracy':sum(a==b for a,b in zip(expected,predicted))/(len(expected) or 1),'macro_precision':sum(x['precision'] for x in per_class.values())/len(labels),'macro_recall':sum(x['recall'] for x in per_class.values())/len(labels),'macro_f1':sum(x['f1'] for x in per_class.values())/len(labels),'per_class':per_class,'confusion_matrix':matrix,'samples':len(expected)}

def evidence_metrics(findings,labels):
    citations=0;valid=0;complete=0;completeness_labels=0;claims=0;supported=0;covered=0;elements=0
    for finding,annotation in zip(findings,labels,strict=True):
        data=finding.original;known={x['chunk_id'] for x in data['regulatory_evidence']+data['organizational_evidence']}
        refs=data.get('citations',[]);citations+=len(refs);valid+=sum(x in known for x in refs)
        if 'citation_complete' in annotation:
            completeness_labels+=1
            if annotation['citation_complete'] is True:complete+=1
        judgments=annotation.get('claim_supported',[]);claims+=len(judgments);supported+=sum(x is True for x in judgments)
        reviewed_elements=annotation.get('element_supported',[]);elements+=len(reviewed_elements);covered+=sum(x is True for x in reviewed_elements)
    return {'citation_reference_validity':valid/citations if citations else None,'citation_completeness_human_labeled':complete/completeness_labels if completeness_labels else None,'faithfulness_human_labeled':supported/claims if claims else None,'unsupported_claim_rate_human_labeled':(claims-supported)/claims if claims else None,'evidence_coverage_human_labeled':covered/elements if elements else None,'claims_annotated':claims,'elements_annotated':elements,'note':'Reference validity is not semantic correctness. Human-labeled rates require independently approved annotations.'}
def retrieval_metrics(ranked,relevant,k=5):
    relevant=set(relevant); ranked=ranked[:k]
    hits=[int(x in relevant) for x in ranked]
    precision=sum(hits)/k
    recall=sum(hits)/len(relevant) if relevant else 0
    rr=next((1/(i+1) for i,h in enumerate(hits) if h),0)
    ap=sum(sum(hits[:i+1])/(i+1) for i,h in enumerate(hits) if h)/(min(len(relevant),k) or 1)
    dcg=sum(h/math.log2(i+2) for i,h in enumerate(hits))
    ideal=sum(1/math.log2(i+2) for i in range(min(len(relevant),k)))
    return {'precision_at_k':precision,'recall_at_k':recall,'mrr':rr,'map_at_k':ap,'ndcg_at_k':dcg/(ideal or 1)}
