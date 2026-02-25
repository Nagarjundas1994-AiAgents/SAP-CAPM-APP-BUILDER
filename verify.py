import sqlite3, json

conn = sqlite3.connect('app.db')
c = conn.cursor()
c.execute("SELECT id, project_name, status, configuration FROM sessions ORDER BY created_at DESC LIMIT 1")
data = c.fetchone()

if data:
    session_id, project_name, status, config_str = data
    config = json.loads(config_str) if config_str else {}
    errors = config.get("validation_errors", [])
    
    print("\n--- Latest Session ---")
    print(f"ID: {session_id}")
    print(f"Project Name: {project_name}")
    print(f"Status: {status}")
    
    if errors:
        print(f"Validation Errors: {len(errors)}")
        for e in errors:
            print(f" - [{e.get('agent')}] {e.get('message')}")
    
    srv = config.get("artifacts_srv", [])
    dpl = config.get("artifacts_deployment", [])
    
    print(f"\nSRV Files: {len(srv)}")
    for f in srv: print(f"  - {f['path']}")
    print(f"DPL Files: {len(dpl)}")
    for f in dpl: print(f"  - {f['path']}")
    
    # Phase 3 Checks
    print("\n--- Phase 3 Checks ---")
    service_cds = next((f.get("content", "") for f in srv if f["path"] == "srv/service.cds"), "")
    mta = next((f.get("content", "") for f in dpl if f["path"] == "mta.yaml"), "")
    service_js = next((f.get("content", "") for f in srv if f["path"] == "srv/service.js"), "")
    
    print("service.cds draft:", "@odata.draft.enabled" in service_cds)
    print("mta.yaml HANA/XSUAA:", "xsuaa" in mta.lower() and "hdi" in mta.lower())
    print("service.js cds.tx:", "cds.tx" in service_js)
    
else:
    print("No sessions found in DB")
