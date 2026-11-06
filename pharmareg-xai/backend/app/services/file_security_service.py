import json,os,subprocess
def scan(path):
    command=os.getenv('MALWARE_SCANNER_COMMAND')
    if not command:
        if os.getenv('REQUIRE_MALWARE_SCAN','false')=='true':raise ValueError('Malware scanning is required but no scanner is configured')
        return 'NOT_CONFIGURED'
    arguments=json.loads(command)
    if not isinstance(arguments,list) or not arguments or not all(isinstance(x,str) for x in arguments):raise ValueError('MALWARE_SCANNER_COMMAND must be a JSON argument array')
    result=subprocess.run([*arguments,str(path)],shell=False,capture_output=True,timeout=60)
    if result.returncode!=0:raise ValueError('Malware scanner rejected the upload or was unavailable')
    return 'SCANNED_CLEAN'
