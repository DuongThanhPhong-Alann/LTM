from supabase import create_client

SUPABASE_URL = "https://qrzycoatheltpfiztkeh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFyenljb2F0aGVsdHBmaXp0a2VoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODY3NjA1NiwiZXhwIjoyMDc0MjUyMDU2fQ.3JmRXRDs-QcEQDHNghjTJEPvoEHA3Zx5MpioHTh9rWM"
BUCKET = 'files'

sup = create_client(SUPABASE_URL, SUPABASE_KEY)

print('Checking Supabase URL/key...')
try:
    resp = sup.rpc('now').execute()
    print(' - RPC now OK (unexpected if not present):', resp)
except Exception as e:
    print(' - RPC check failed (expected on some projects):', e)

print('Checking storage list...')
try:
    files = sup.storage.from_(BUCKET).list()
    print(' - Storage list OK, count =', len(files))
    if files:
        print(' - Sample entry:', files[0])
except Exception as e:
    print(' - Storage list failed:', e)

print('Checking get_public_url on sample...')
try:
    url = sup.storage.from_(BUCKET).get_public_url('input.txt')
    print(' - get_public_url returned:', url)
except Exception as e:
    print(' - get_public_url failed:', e)

print('Checking files_metadata table...')
try:
    rows = sup.table('files_metadata').select('*').limit(3).execute()
    print(' - files_metadata query returned:', getattr(rows, 'data', rows))
except Exception as e:
    print(' - files_metadata query failed:', e)
