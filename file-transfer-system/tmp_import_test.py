import sys
sys.path.append(r'C:\Users\duong\LTM-main\file-transfer-system\web')
try:
    from services.storage_service import StorageService
    print('Imported StorageService OK')
except Exception as e:
    print('Import failed:', e)
