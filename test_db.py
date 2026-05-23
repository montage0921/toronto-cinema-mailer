from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
db = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])
result = db.table('cinemas').select('*').execute()
print(f'Cinemas in DB: {len(result.data)}')
for c in result.data:
    print(f'  {c["slug"]} — {c["name"]}')
