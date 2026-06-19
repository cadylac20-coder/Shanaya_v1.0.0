from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from database import get_db
api_key_header = APIKeyHeader(name="X-API-Key")
def verify_api_key(key: str = Security(api_key_header)):
    conn=get_db(); row=conn.execute("SELECT name FROM api_keys WHERE key=? AND active=1",(key,)).fetchone(); conn.close()
    if not row: raise HTTPException(status_code=403,detail="Invalid API key.")
    return {"key":key,"name":row["name"]}
