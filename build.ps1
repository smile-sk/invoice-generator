# build.ps1
# Збирає застосунок у єдиний виконуваний файл Windows.
#
# Запуск (з кореня проєкту, у активованому venv):
#   .\build.ps1

Write-Host "Збираю InvoiceGenerator.exe..." -ForegroundColor Cyan

pyinstaller build.spec --noconfirm

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Готово! Виконуваний файл:" -ForegroundColor Green
    Write-Host "  dist\InvoiceGenerator.exe" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Збірка завершилась з помилкою. Перевірте повідомлення вище." -ForegroundColor Red
}
