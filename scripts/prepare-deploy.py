import os
import shutil

def prepare_deploy():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"Preparing Catalyst layout under {root}")
    
    # 1. Sync backend -> appsail/ksp-ai-backend
    src_be = os.path.join(root, "backend")
    dest_be = os.path.join(root, "appsail", "ksp-ai-backend")
    print("  backend/  -> appsail/ksp-ai-backend/")
    
    os.makedirs(dest_be, exist_ok=True)
    be_files = ["main.py", "db.py", "seed.py", "llm.py", "analytics.py", "catalyst.py", "jobs.py", "requirements.txt"]
    for f in be_files:
        src = os.path.join(src_be, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dest_be, f))
            
    # Copy env.example
    env_ex = os.path.join(src_be, ".env.example")
    if os.path.exists(env_ex):
        shutil.copy2(env_ex, os.path.join(dest_be, ".env.example"))
        
    # Write .dockerignore
    dockerignore_path = os.path.join(dest_be, ".dockerignore")
    with open(dockerignore_path, "w", encoding="utf-8") as f:
        f.write(".venv/\n__pycache__/\n*.pyc\n*.db\n.env\nstratus_local/\n")
        
    # 2. Sync frontend -> client
    src_fe = os.path.join(root, "frontend")
    dest_fe = os.path.join(root, "client")
    print("  frontend/ -> client/")
    
    os.makedirs(dest_fe, exist_ok=True)
    fe_files = ["index.html", "app.js", "styles.css", "config.js"]
    for f in fe_files:
        src = os.path.join(src_fe, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dest_fe, f))
            
    # Rewrite /static/ prefixes in client/index.html
    client_idx = os.path.join(dest_fe, "index.html")
    if os.path.exists(client_idx):
        with open(client_idx, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace('href="/static/', 'href="./')
        content = content.replace('src="/static/', 'src="./')
        with open(client_idx, "w", encoding="utf-8") as f:
            f.write(content)
            
    # 3. Sync frontend -> appsail/ksp-ai-backend/webroot
    dest_web = os.path.join(dest_be, "webroot")
    os.makedirs(dest_web, exist_ok=True)
    print("  frontend/ -> appsail/ksp-ai-backend/webroot/")
    for f in fe_files:
        src = os.path.join(src_fe, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dest_web, f))
            
    print("Deployment files prepared successfully.")

if __name__ == "__main__":
    prepare_deploy()
