# setup_autonomous_12h.ps1 - Full setup for 12-hour autonomous run
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   Digital Being - Autonomous 12h Setup" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

$projectDir = "E:\project\project-2\digital-being"
cd $projectDir

# 1. Backup current config
Write-Host "[+] Backing up current config..." -ForegroundColor Yellow
Copy-Item "$projectDir\config.yaml" "$projectDir\config.yaml.backup" -Force

# 2. Apply config patches
Write-Host "[+] Applying autonomous evolution config..." -ForegroundColor Yellow

# Read current config
$config = Get-Content "$projectDir\config.yaml" -Raw

# Patches - ONLY override specific values, don't replace entire sections
$evolutionPatch = @"

# ============= AUTONOMOUS 12H EVOLUTION MODE =============
# Auto-applied by setup_autonomous_12h.ps1
# This overrides specific values without replacing entire config sections

ticks:
  heavy_tick_sec: 90

self_evolution:
  check_interval_ticks: 5
  max_modifications_per_hour: 8
  max_modifications_per_day: 50

dream_mode:
  interval_hours: 3

curiosity:
  base_rate: 0.4
  max_open_questions: 15

values:
  anchor_rules:
    locked: false
"@

# Apply patch if not already applied
if ($config -notlike "*AUTONOMOUS 12H EVOLUTION MODE*") {
    $config + $evolutionPatch | Set-Content "$projectDir\config.yaml" -Encoding UTF8
    Write-Host "   [OK] Config patched" -ForegroundColor Green
} else {
    Write-Host "   [INFO] Already patched" -ForegroundColor Gray
}

# 3. Cleanup
Write-Host "[+] Cleaning up..." -ForegroundColor Yellow
Remove-Item "$projectDir\logs\*.log" -ErrorAction SilentlyContinue
Write-Host "   [OK] Logs cleared" -ForegroundColor Green

# 4. Check dependencies
Write-Host "[+] Checking dependencies..." -ForegroundColor Yellow
$ollama = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "   [+] Starting Ollama..." -ForegroundColor Yellow
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
}
Write-Host "   [OK] Ollama running" -ForegroundColor Green

# 5. Create clean inbox
Write-Host "[+] Creating clean inbox..." -ForegroundColor Yellow
"" | Out-File "$projectDir\inbox.txt" -Encoding UTF8 -Force
Write-Host "   [OK] Inbox ready" -ForegroundColor Green

# 6. Final check
Write-Host ""
Write-Host "[OK] Setup complete! Ready to run for 12 hours." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "   1. Start autonomous mode: .\run_autonomous.ps1 -maxHours 12" -ForegroundColor White
Write-Host "   2. (In separate window) Start monitor: .\monitor.ps1" -ForegroundColor White
Write-Host "   3. (Optional) Open web UI: http://127.0.0.1:8766" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to start autonomous mode, or Ctrl+C to cancel..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Launch
Write-Host ""
Write-Host "[*] Starting in 3 seconds..." -ForegroundColor Cyan
Start-Sleep -Seconds 3
.\run_autonomous.ps1 -maxHours 12