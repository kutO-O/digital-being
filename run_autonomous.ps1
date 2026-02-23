# run_autonomous.ps1 - Autonomous 12+ hour run with auto-restart
param(
    [int]$maxHours = 12
)

$maxRestarts = 20
$restartCount = 0
$logFile = "E:\project\project-2\digital-being\autonomous_run.log"
$startTime = Get-Date

Write-Host "[*] Starting Digital Being in autonomous mode for $maxHours hours..." -ForegroundColor Cyan

# Disable sleep mode
Write-Host "[+] Disabling sleep mode..." -ForegroundColor Yellow
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 30

# Clean old logs
Write-Host "[+] Cleaning old logs..." -ForegroundColor Yellow
Get-ChildItem E:\project\project-2\digital-being\logs\*.log | Where-Object { $_.Length -gt 50MB } | Remove-Item -Force

# Restart Ollama
Write-Host "[+] Restarting Ollama..." -ForegroundColor Yellow
Stop-Process -Name ollama -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden

Start-Sleep -Seconds 5

# Main loop
while ($restartCount -lt $maxRestarts) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $elapsed = (Get-Date) - $startTime
    
    # Check timeout
    if ($elapsed.TotalHours -ge $maxHours) {
        Write-Host "[!] Time limit reached ($maxHours hours). Stopping..." -ForegroundColor Green
        "$timestamp - Time limit reached, stopping gracefully" | Out-File $logFile -Append
        break
    }
    
    Write-Host "[>] Starting Digital Being (attempt $($restartCount + 1) / run time: $([math]::Round($elapsed.TotalHours, 1))h)" -ForegroundColor Cyan
    "$timestamp - Starting Digital Being (attempt $($restartCount + 1))" | Out-File $logFile -Append
    
    try {
        cd E:\project\project-2\digital-being
        python main.py 2>&1 | Tee-Object -Append -FilePath $logFile
        
        # Clean exit
        Write-Host "[OK] Clean exit" -ForegroundColor Green
        "$timestamp - Clean exit" | Out-File $logFile -Append
        break
    }
    catch {
        $restartCount++
        Write-Host "[ERROR] Crashed: $($_.Exception.Message)" -ForegroundColor Red
        "$timestamp - Crashed: $($_.Exception.Message)" | Out-File $logFile -Append
        
        if ($restartCount -lt $maxRestarts) {
            Write-Host "[+] Restarting in 10 seconds..." -ForegroundColor Yellow
            "$timestamp - Restarting in 10 seconds..." | Out-File $logFile -Append
            
            # Restart Ollama if needed
            $ollama = Get-Process ollama -ErrorAction SilentlyContinue
            if (-not $ollama) {
                Write-Host "[+] Ollama crashed, restarting..." -ForegroundColor Yellow
                Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
            }
            
            Start-Sleep -Seconds 10
        }
    }
}

Write-Host "[STOP] Stopped after $restartCount restarts" -ForegroundColor Magenta
"$timestamp - Stopped after $restartCount restarts" | Out-File $logFile -Append

# Restore power settings
Write-Host "[+] Restoring power settings..." -ForegroundColor Yellow
powercfg /change standby-timeout-ac 15
powercfg /change monitor-timeout-ac 10

Write-Host "[OK] Autonomous run completed!" -ForegroundColor Green