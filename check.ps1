# Scan Bluetooth devices nearby
Add-Type -AssemblyName System.Management

$bluetoothDevices = Get-CimInstance -Namespace root\CIMv2 -ClassName Win32_PnPEntity | Where-Object {
    $_.Name -like "*Bluetooth*"
}

Write-Host "=== Daftar Perangkat Bluetooth Terdeteksi ===" -ForegroundColor Cyan

foreach ($device in $bluetoothDevices) {
    # Ambil DeviceID dan ekstrak MAC
    if ($device.DeviceID -match "DEV_([0-9A-F]{12})") {
        $mac = $matches[1]
        $macFormatted = ($mac -replace "(.{2})(?=.)","$1:")
        Write-Host "Nama: $($device.Name) | MAC: $macFormatted"
    } else {
        Write-Host "Nama: $($device.Name) | MAC: Tidak ditemukan"
    }
}
