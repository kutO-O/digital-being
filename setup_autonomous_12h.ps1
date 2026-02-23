# setup_autonomous_12h.ps1 - Полная настройка для 12-часового автономного запуска
Write-Host "╔═══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   🧠 Digital Being - Autonomous 12h Setup       ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$projectDir = "E:\project\project-2\digital-being"
cd $projectDir

# 1. Бэкап текущего конфига
Write-Host "📦 Backing up current config..." -ForegroundColor Yellow
Copy-Item "$projectDir\config.yaml" "$projectDir\config.yaml.backup" -Force

# 2. Применить патчи к конфигу
Write-Host "⚙️  Applying autonomous evolution config..." -ForegroundColor Yellow

# Читаем текущий конфиг
$config = Get-Content "$projectDir\config.yaml" -Raw

# Патчи (добавляем в конец файла)
$evolutionPatch = @"

# ============= AUTONOMOUS 12H EVOLUTION MODE =============
# Auto-applied by setup_autonomous_12h.ps1

self_evolution:
  check_interval_ticks: 5
  max_modifications_per_hour: 8
  max_modifications_per_day: 50
  
memory:
  consolidation:
    interval_hours: 2
    min_episodes_to_consolidate: 30
    
dream_mode:
  interval_hours: 3
  insight_generation: true
  
learning:
  pattern_extraction:
    min_occurrences: 2
    
curiosity:
  base_rate: 0.4
  max_open_questions: 15
  
values:
  evolution:
    allow_value_drift: true
    max_drift_per_day: 0.15
  anchor_rules:
    locked: false
    allow_self_modification: true
"@

# Добавляем патч если его ещё нет
if ($config -notlike "*AUTONOMOUS 12H EVOLUTION MODE*") {
    $config + $evolutionPatch | Set-Content "$projectDir\config.yaml" -Encoding UTF8
    Write-Host "   ✅ Config patched" -ForegroundColor Green
} else {
    Write-Host "   ℹ️  Already patched" -ForegroundColor Gray
}

# 3. Очистка перед запуском
Write-Host "🧹 Cleaning up..." -ForegroundColor Yellow
Remove-Item "$projectDir\logs\*.log" -ErrorAction SilentlyContinue
Write-Host "   ✅ Logs cleared" -ForegroundColor Green

# 4. Проверка зависимостей
Write-Host "🔍 Checking dependencies..." -ForegroundColor Yellow
$ollama = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "   🦙 Starting Ollama..." -ForegroundColor Yellow
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
}
Write-Host "   ✅ Ollama running" -ForegroundColor Green

# 5. Создание inbox.txt с правильной кодировкой
Write-Host "📬 Creating clean inbox..." -ForegroundColor Yellow
"" | Out-File "$projectDir\inbox.txt" -Encoding UTF8 -Force
Write-Host "   ✅ Inbox ready" -ForegroundColor Green

# 6. Финальная проверка
Write-Host ""
Write-Host "✅ Setup complete! Ready to run for 12 hours." -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Start autonomous mode: .\run_autonomous.ps1 -maxHours 12" -ForegroundColor White
Write-Host "   2. (In separate window) Start monitor: .\monitor.ps1" -ForegroundColor White
Write-Host "   3. (Optional) Open web UI: http://127.0.0.1:8766" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to start autonomous mode, or Ctrl+C to cancel..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Запуск
Write-Host ""
Write-Host "🚀 Starting in 3 seconds..." -ForegroundColor Cyan
Start-Sleep -Seconds 3
.\run_autonomous.ps1 -maxHours 12