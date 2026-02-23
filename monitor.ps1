# monitor.ps1 - Real-time monitoring dashboard
while ($true) {
    Clear-Host
    $timestamp = Get-Date -Format "HH:mm:ss"
    
    Write-Host "===================================================" -ForegroundColor Cyan
    Write-Host "     Digital Being - Live Monitor" -ForegroundColor Cyan
    Write-Host "     Time: $timestamp" -ForegroundColor Cyan
    Write-Host "===================================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Process status
    Write-Host "[Process Status]" -ForegroundColor Yellow
    $process = Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*main.py*"}
    if ($process) {
        Write-Host "   [OK] Status    : Running (PID: $($process.Id))" -ForegroundColor Green
        Write-Host "   [*] Memory     : $([math]::Round($process.WorkingSet64/1MB,0)) MB" -ForegroundColor White
        Write-Host "   [*] CPU Time   : $([math]::Round($process.CPU,1))s" -ForegroundColor White
        Write-Host "   [*] Started    : $($process.StartTime.ToString('HH:mm:ss'))" -ForegroundColor White
    } else {
        Write-Host "   [ERROR] Status : Not running!" -ForegroundColor Red
    }
    Write-Host ""
    
    # Ollama status
    Write-Host "[Ollama Status]" -ForegroundColor Yellow
    $ollama = Get-Process ollama -ErrorAction SilentlyContinue
    if ($ollama) {
        Write-Host "   [OK] Status    : Running" -ForegroundColor Green
        Write-Host "   [*] Memory     : $([math]::Round($ollama.WorkingSet64/1MB,0)) MB" -ForegroundColor White
    } else {
        Write-Host "   [ERROR] Status : Not running!" -ForegroundColor Red
    }
    Write-Host ""
    
    # API status
    Write-Host "[API Status]" -ForegroundColor Yellow
    try {
        $status = Invoke-WebRequest http://127.0.0.1:8766/status -TimeoutSec 3 -ErrorAction Stop
        $json = $status.Content | ConvertFrom-Json
        
        $uptimeMin = [math]::Round($json.uptime_sec / 60, 1)
        Write-Host "   [OK] Status      : Online" -ForegroundColor Green
        Write-Host "   [*] Uptime       : ${uptimeMin} minutes" -ForegroundColor White
        Write-Host "   [*] Ticks        : $($json.tick_count)" -ForegroundColor White
        Write-Host "   [*] Episodes     : $($json.episode_count)" -ForegroundColor White
        Write-Host "   [*] Mode         : $($json.mode)" -ForegroundColor White
        Write-Host "   [*] Goal         : $($json.current_goal.Substring(0, [Math]::Min(40, $json.current_goal.Length)))..." -ForegroundColor White
    } catch {
        Write-Host "   [ERROR] Status   : Offline" -ForegroundColor Red
    }
    Write-Host ""
    
    # Recent errors
    Write-Host "[Recent Errors (last 5)]" -ForegroundColor Yellow
    $errors = Select-String -Path "E:\project\project-2\digital-being\logs\digital_being.log" -Pattern "ERROR" -SimpleMatch -ErrorAction SilentlyContinue | Select-Object -Last 5
    if ($errors) {
        foreach ($error in $errors) {
            $line = $error.Line.Substring(0, [Math]::Min(70, $error.Line.Length))
            Write-Host "   - $line..." -ForegroundColor Red
        }
    } else {
        Write-Host "   [OK] No errors" -ForegroundColor Green
    }
    Write-Host ""
    
    # Disk space
    Write-Host "[Disk Space (E:)]" -ForegroundColor Yellow
    $drive = Get-PSDrive E
    $freeGB = [math]::Round($drive.Free / 1GB, 1)
    Write-Host "   Free: ${freeGB} GB" -ForegroundColor White
    Write-Host ""
    
    Write-Host "Press Ctrl+C to stop monitoring" -ForegroundColor Gray
    Write-Host "Refreshing in 30 seconds..." -ForegroundColor Gray
    
    Start-Sleep -Seconds 30
}