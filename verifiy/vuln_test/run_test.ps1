cd 'C:\Users\santa\Desktop\TheAuditor\verifiy\vuln_test'

Write-Output "=== Running indexer ==="
& 'C:\Users\santa\Desktop\TheAuditor\.venv\Scripts\python.exe' -m theauditor.cli index

Write-Output "`n=== Running taint analysis ==="
& 'C:\Users\santa\Desktop\TheAuditor\.venv\Scripts\python.exe' -m theauditor.cli taint-analyze

if (Test-Path '.pf\raw\taint_analysis.json') {
    $json = Get-Content '.pf\raw\taint_analysis.json' | ConvertFrom-Json
    Write-Output "`n=== RESULTS ==="
    Write-Output "Success: $($json.success)"
    Write-Output "Sources found: $($json.sources_found)"
    Write-Output "Sinks found: $($json.sinks_found)"
    Write-Output "Taint paths found: $($json.taint_paths.Count)"
    Write-Output "`nVulnerabilities detected:"
    $json.taint_paths | ForEach-Object {
        Write-Output "  - $($_.vulnerability_type) at $($_.sink.file):$($_.sink.line)"
    }
} else {
    Write-Output "ERROR: taint_analysis.json not found!"
}
