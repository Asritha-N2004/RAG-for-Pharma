def calculate(severity,likelihood,detectability,thresholds=None):
    if not all(isinstance(x,int) and 1<=x<=5 for x in (severity,likelihood,detectability)): raise ValueError('Risk factors must be integers 1–5')
    score=severity*likelihood*detectability
    thresholds=thresholds or {'critical':80,'high':40,'medium':15}
    level='CRITICAL' if score>=thresholds['critical'] else 'HIGH' if score>=thresholds['high'] else 'MEDIUM' if score>=thresholds['medium'] else 'LOW'
    return {'severity':severity,'likelihood':likelihood,'detectability':detectability,'score':score,'level':level,'thresholds':thresholds,'methodology':'Internal S×L×D matrix, 1–5 factors; not a regulator-defined scoring system'}
