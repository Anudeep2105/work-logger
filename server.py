#!/usr/bin/env python3
"""Worklog v3: stdlib HTTP API, SQLite persistence, role-enforced workflows."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from datetime import datetime, timezone, timedelta
import sqlite3, json, secrets, hashlib, hmac, os, re, sys, getpass, mimetypes
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
DB_PATH=Path(os.environ.get('WORKLOG_DB_PATH', DATA/'worklog.sqlite3'))
SESSION_DAYS=1
ROLES={'admin','hr','manager','employee'}
STATUSES={'Not started','In progress','Blocked','Done'}


def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def connect():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB_PATH,timeout=15)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=15000')
    return c

@contextmanager
def db():
    c=connect()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def init_db():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(
          id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, full_name TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('admin','hr','manager','employee')),
          team TEXT NOT NULL, manager_id TEXT REFERENCES users(id),
          salt TEXT NOT NULL, password_hash TEXT NOT NULL, must_change INTEGER NOT NULL DEFAULT 1,
          active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(
          token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          expires_at TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(
          id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          owner_id TEXT NOT NULL REFERENCES users(id), team TEXT NOT NULL, due TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('Not started','In progress','Blocked','Done')),
          quality TEXT NOT NULL DEFAULT '', contributors TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, completed_at TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS evaluations(
          id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES users(id),
          manager_id TEXT NOT NULL REFERENCES users(id), task_id TEXT REFERENCES tasks(id),
          period TEXT NOT NULL, title TEXT NOT NULL, rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
          feedback TEXT NOT NULL, shared INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS hr_reviews(
          id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL UNIQUE REFERENCES evaluations(id) ON DELETE CASCADE,
          reviewer_id TEXT NOT NULL REFERENCES users(id), grade INTEGER NOT NULL CHECK(grade BETWEEN 1 AND 5),
          review TEXT NOT NULL, disposition TEXT NOT NULL CHECK(disposition IN ('Reviewed','Follow-up required')),
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS corrections(
          id TEXT PRIMARY KEY, entity_type TEXT NOT NULL CHECK(entity_type IN ('task','feedback')),
          entity_id TEXT NOT NULL, requester_id TEXT NOT NULL REFERENCES users(id), reason TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Accepted','Declined')),
          resolution TEXT NOT NULL DEFAULT '', resolver_id TEXT REFERENCES users(id),
          created_at TEXT NOT NULL, resolved_at TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS audit_events(
          id TEXT PRIMARY KEY, actor_id TEXT REFERENCES users(id), action TEXT NOT NULL,
          entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_id,due);
        CREATE INDEX IF NOT EXISTS idx_eval_employee ON evaluations(employee_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_eval_shared ON evaluations(shared,created_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
        ''')
        c.execute("DELETE FROM sessions WHERE expires_at < ?",(now(),))

def pw_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),310000).hex()
    return salt,digest

def audit(c,actor,action,etype,eid,detail=''):
    c.execute('INSERT INTO audit_events VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(16),actor,action,etype,eid,detail[:400],now()))

def public_user(row):
    return {k:row[k] for k in ('id','username','full_name','role','team','manager_id','must_change','active','created_at')}

def add_user(username,full_name,role,team,password,manager_id=None,must_change=True):
    if role not in ROLES: raise ValueError('Invalid role')
    if len(password)<12: raise ValueError('Temporary password must be at least 12 characters')
    if not re.fullmatch(r'[A-Za-z0-9._-]{3,50}',username): raise ValueError('Username must be 3–50 letters, numbers, dots, underscores, or hyphens')
    if not full_name.strip() or not team.strip(): raise ValueError('Name and team are required')
    salt,digest=pw_hash(password); uid=secrets.token_hex(16)
    with db() as c:
        if manager_id:
            m=c.execute('SELECT id,role FROM users WHERE id=? AND active=1',(manager_id,)).fetchone()
            if not m or m['role']!='manager': raise ValueError('Select an active manager profile')
        c.execute('INSERT INTO users(id,username,full_name,role,team,manager_id,salt,password_hash,must_change,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,1,?)',(uid,username.strip(),full_name.strip(),role,team.strip(),manager_id,salt,digest,int(must_change),now()))
        audit(c,None,'user_created','user',uid,f'role={role}; team={team.strip()}')
        row=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        return public_user(row)

def clean_user(row):
    d=public_user(row); d['must_change']=bool(d['must_change']);d['active']=bool(d['active']);return d

class WorklogHTTPServer(ThreadingHTTPServer):
    allow_reuse_address=False
    daemon_threads=True

class Handler(BaseHTTPRequestHandler):
    server_version='Worklog/3'
    def log_message(self,fmt,*args): print('%s - %s'%(self.address_string(),fmt%args))
    def send_json(self,code,data,headers=None):
        raw=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(raw)
    def fail(self,code,msg): self.send_json(code,{'error':msg})
    def read_json(self):
        try:
            n=int(self.headers.get('Content-Length','0'))
            if n>100000: raise ValueError('Request too large')
            return json.loads(self.rfile.read(n) or b'{}')
        except Exception: raise ValueError('Invalid JSON request')
    def origin_ok(self):
        origin=self.headers.get('Origin')
        if not origin:return True
        return urlparse(origin).netloc==self.headers.get('Host','')
    def current_user(self):
        cookie=self.headers.get('Cookie','')
        raw=''
        for part in cookie.split(';'):
            k,_,v=part.strip().partition('=')
            if k=='worklog_session':raw=v
        if not raw:return None
        token_hash=hashlib.sha256(raw.encode()).hexdigest()
        with db() as c:
            row=c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1',(token_hash,now())).fetchone()
            return dict(row) if row else None
    def require(self,*roles):
        u=self.current_user()
        if not u:raise PermissionError('Sign in required')
        if u['must_change'] and self.path not in ('/api/password','/api/logout','/api/me'):raise PermissionError('Change your temporary password before continuing')
        if roles and u['role'] not in roles:raise PermissionError('You do not have permission for this action')
        return u
    def do_GET(self):
        try:
            path=urlparse(self.path).path
            if path.startswith('/api/'):return self.api_get(path)
            if path=='/' or path=='/index.html':return self.static('index.html','text/html; charset=utf-8')
            if path=='/app.js':return self.static('app.js','text/javascript; charset=utf-8')
            if path=='/styles.css':return self.static('styles.css','text/css; charset=utf-8')
            if path=='/manifest.webmanifest':return self.static('manifest.webmanifest','application/manifest+json; charset=utf-8')
            if path=='/service-worker.js':return self.static('service-worker.js','text/javascript; charset=utf-8')
            if path=='/icon.svg':return self.static('icon.svg','image/svg+xml')
            return self.fail(404,'Not found')
        except PermissionError as e:return self.fail(401 if str(e)=='Sign in required' else 403,str(e))
        except Exception as e:print('GET error:',repr(e));return self.fail(500,'Unexpected server error')
    def static(self,name,ctype):
        asset=(ROOT/'client'/name)
        if not asset.is_file():asset=ROOT/name
        data=asset.read_bytes();self.send_response(200);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-cache');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','same-origin');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'");self.end_headers();self.wfile.write(data)
    def do_POST(self):self.handle_mutation('POST')
    def do_PUT(self):self.handle_mutation('PUT')
    def do_PATCH(self):self.handle_mutation('PATCH')
    def handle_mutation(self,method):
        try:
            if not self.origin_ok():return self.fail(403,'Request origin is not allowed')
            body=self.read_json();path=urlparse(self.path).path
            if path=='/api/login' and method=='POST':return self.login(body)
            if path=='/api/setup' and method=='POST':return self.setup_admin(body)
            if path=='/api/logout' and method=='POST':return self.logout()
            if path=='/api/password' and method=='POST':return self.change_password(body)
            u=self.require()
            if path=='/api/tasks' and method=='POST':return self.create_task(u,body)
            m=re.fullmatch(r'/api/tasks/([\w-]+)',path)
            if m and method in ('PUT','PATCH'):return self.update_task(u,m.group(1),body)
            if path=='/api/feedback' and method=='POST':return self.create_feedback(u,body)
            m=re.fullmatch(r'/api/feedback/([\w-]+)/share',path)
            if m and method=='POST':return self.share_feedback(u,m.group(1))
            m=re.fullmatch(r'/api/feedback/([\w-]+)',path)
            if m and method=='PUT':return self.update_feedback(u,m.group(1),body)
            m=re.fullmatch(r'/api/feedback/([\w-]+)/review',path)
            if m and method=='POST':return self.hr_review(u,m.group(1),body)
            if path=='/api/corrections' and method=='POST':return self.create_correction(u,body)
            m=re.fullmatch(r'/api/corrections/([\w-]+)',path)
            if m and method=='PATCH':return self.resolve_correction(u,m.group(1),body)
            if path=='/api/users' and method=='POST':return self.create_user(u,body)
            if path=='/api/import-tasks' and method=='POST':return self.import_tasks(u,body)
            m=re.fullmatch(r'/api/users/([\w-]+)/active',path)
            if m and method=='PATCH':return self.activate_user(u,m.group(1),body)
            m=re.fullmatch(r'/api/users/([\w-]+)/reset-password',path)
            if m and method=='POST':return self.reset_password(u,m.group(1),body)
            return self.fail(404,'Unknown endpoint')
        except PermissionError as e:return self.fail(401 if str(e)=='Sign in required' else 403,str(e))
        except ValueError as e:return self.fail(400,str(e))
        except sqlite3.IntegrityError as e:return self.fail(409,'A record conflicts with existing data')
        except Exception as e:print('Mutation error:',repr(e));return self.fail(500,'Unexpected server error')
    def setup_admin(self,b):
        username=str(b.get('username','')).strip();full_name=str(b.get('full_name','')).strip();team=str(b.get('team','Administration')).strip() or 'Administration';password=str(b.get('password',''));confirm=str(b.get('confirm_password',''))
        if password!=confirm:raise ValueError('Passwords do not match')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM users LIMIT 1').fetchone():raise PermissionError('Initial setup is already complete')
            salt,digest=pw_hash(password);uid=secrets.token_hex(16);ts=now()
            if len(password)<12:raise ValueError('Password must be at least 12 characters')
            if not re.fullmatch(r'[A-Za-z0-9._-]{3,50}',username):raise ValueError('Username must be 3–50 letters, numbers, dots, underscores, or hyphens')
            if not full_name:raise ValueError('Full name is required')
            c.execute('INSERT INTO users(id,username,full_name,role,team,manager_id,salt,password_hash,must_change,active,created_at) VALUES(?,?,?,?,?,?,?,?,0,1,?)',(uid,username,full_name,'admin',team,None,salt,digest,ts))
            audit(c,uid,'initial_admin_created','user',uid)
        return self.send_json(201,{'ok':True})
    def login(self,b):
        username=str(b.get('username','')).strip();password=str(b.get('password',''))
        with db() as c:row=c.execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone()
        if not row:return self.fail(401,'Invalid username or password')
        _,test=pw_hash(password,row['salt'])
        if not hmac.compare_digest(test,row['password_hash']):return self.fail(401,'Invalid username or password')
        token=secrets.token_urlsafe(32);exp=(datetime.now(timezone.utc)+timedelta(days=SESSION_DAYS)).isoformat(timespec='seconds')
        with db() as c:
            c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],exp,now()));audit(c,row['id'],'login','session',row['id'])
        secure='; Secure' if self.headers.get('X-Forwarded-Proto')=='https' else ''
        return self.send_json(200,{'user':clean_user(row)},{'Set-Cookie':f'worklog_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_DAYS*86400}{secure}'})
    def logout(self):
        u=self.current_user();raw=''
        for part in self.headers.get('Cookie','').split(';'):
            k,_,v=part.strip().partition('=')
            if k=='worklog_session':raw=v
        if raw:
            with db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(raw.encode()).hexdigest(),))
        return self.send_json(200,{'ok':True},{'Set-Cookie':'worklog_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
    def change_password(self,b):
        u=self.current_user()
        if not u:return self.fail(401,'Sign in required')
        old=str(b.get('current_password',''));new=str(b.get('new_password',''))
        if not u['must_change']:
            _,test=pw_hash(old,u['salt'])
            if not hmac.compare_digest(test,u['password_hash']):return self.fail(400,'Current password is incorrect')
        if len(new)<12:return self.fail(400,'Password must be at least 12 characters')
        salt,digest=pw_hash(new)
        with db() as c:c.execute('UPDATE users SET salt=?,password_hash=?,must_change=0 WHERE id=?',(salt,digest,u['id']));audit(c,u['id'],'password_changed','user',u['id'])
        return self.send_json(200,{'ok':True})
    def api_get(self,path):
        try:
            u=self.require() if path not in ('/api/health','/api/setup-status') else None
            if path=='/api/health':return self.send_json(200,{'ok':True,'database':'sqlite'})
            if path=='/api/setup-status':
                with db() as c: configured=bool(c.execute('SELECT 1 FROM users LIMIT 1').fetchone())
                return self.send_json(200,{'configured':configured})
            with db() as c:
                if path=='/api/me':return self.send_json(200,{'user':clean_user(c.execute('SELECT * FROM users WHERE id=?',(u['id'],)).fetchone())})
                if path=='/api/users':
                    if u['role']=='admin':rows=c.execute('SELECT * FROM users ORDER BY role,full_name').fetchall()
                    elif u['role']=='manager':rows=c.execute("SELECT * FROM users WHERE manager_id=? AND role='employee' AND active=1 ORDER BY full_name",(u['id'],)).fetchall()
                    else:raise PermissionError('You do not have permission for this action')
                    return self.send_json(200,{'users':[clean_user(x) for x in rows]})
                if path=='/api/tasks':
                    if u['role']=='admin':rows=c.execute('SELECT t.*,u.full_name AS owner_name,u.team AS owner_team FROM tasks t JOIN users u ON u.id=t.owner_id ORDER BY t.due,t.created_at DESC').fetchall()
                    elif u['role']=='manager':rows=c.execute('SELECT t.*,u.full_name AS owner_name,u.team AS owner_team FROM tasks t JOIN users u ON u.id=t.owner_id WHERE u.manager_id=? ORDER BY t.due,t.created_at DESC',(u['id'],)).fetchall()
                    elif u['role']=='employee':rows=c.execute('SELECT t.*,u.full_name AS owner_name,u.team AS owner_team FROM tasks t JOIN users u ON u.id=t.owner_id WHERE t.owner_id=? ORDER BY t.due,t.created_at DESC',(u['id'],)).fetchall()
                    else:rows=c.execute('SELECT t.*,u.full_name AS owner_name,u.team AS owner_team FROM tasks t JOIN users u ON u.id=t.owner_id WHERE t.id IN (SELECT task_id FROM evaluations WHERE shared=1 AND task_id IS NOT NULL)',()).fetchall()
                    return self.send_json(200,{'tasks':[dict(x) for x in rows]})
                if path=='/api/feedback':
                    if u['role']=='manager':rows=c.execute('SELECT e.*,emp.full_name AS employee_name,emp.team,tk.title AS task_title,rv.grade AS hr_grade,rv.review AS hr_review,rv.disposition AS hr_disposition FROM evaluations e JOIN users emp ON emp.id=e.employee_id LEFT JOIN hr_reviews rv ON rv.evaluation_id=e.id LEFT JOIN tasks tk ON tk.id=e.task_id WHERE e.manager_id=? ORDER BY e.created_at DESC',(u['id'],)).fetchall()
                    elif u['role']=='employee':rows=c.execute('SELECT e.*,emp.full_name AS employee_name,emp.team,tk.title AS task_title,rv.grade AS hr_grade,rv.review AS hr_review,rv.disposition AS hr_disposition FROM evaluations e JOIN users emp ON emp.id=e.employee_id LEFT JOIN hr_reviews rv ON rv.evaluation_id=e.id LEFT JOIN tasks tk ON tk.id=e.task_id WHERE e.employee_id=? AND e.shared=1 ORDER BY e.created_at DESC',(u['id'],)).fetchall()
                    elif u['role']=='hr':rows=c.execute('SELECT e.*,emp.full_name AS employee_name,emp.team,tk.title AS task_title,rv.grade AS hr_grade,rv.review AS hr_review,rv.disposition AS hr_disposition FROM evaluations e JOIN users emp ON emp.id=e.employee_id LEFT JOIN hr_reviews rv ON rv.evaluation_id=e.id LEFT JOIN tasks tk ON tk.id=e.task_id WHERE e.shared=1 ORDER BY e.created_at DESC').fetchall()
                    else:rows=c.execute('SELECT e.*,emp.full_name AS employee_name,emp.team,tk.title AS task_title,rv.grade AS hr_grade,rv.review AS hr_review,rv.disposition AS hr_disposition FROM evaluations e JOIN users emp ON emp.id=e.employee_id LEFT JOIN hr_reviews rv ON rv.evaluation_id=e.id LEFT JOIN tasks tk ON tk.id=e.task_id ORDER BY e.created_at DESC').fetchall()
                    return self.send_json(200,{'feedback':[dict(x) for x in rows]})
                if path=='/api/corrections':
                    if u['role']=='admin':rows=c.execute('SELECT x.*,r.full_name AS requester_name FROM corrections x JOIN users r ON r.id=x.requester_id ORDER BY x.created_at DESC').fetchall()
                    elif u['role']=='employee':rows=c.execute('SELECT x.*,r.full_name AS requester_name FROM corrections x JOIN users r ON r.id=x.requester_id WHERE x.requester_id=? ORDER BY x.created_at DESC',(u['id'],)).fetchall()
                    elif u['role']=='manager':rows=c.execute("SELECT x.*,r.full_name AS requester_name FROM corrections x JOIN users r ON r.id=x.requester_id WHERE r.manager_id=? AND x.status='Pending' ORDER BY x.created_at DESC",(u['id'],)).fetchall()
                    else:rows=[]
                    return self.send_json(200,{'corrections':[dict(x) for x in rows]})
                if path=='/api/audit' and u['role']=='admin':
                    rows=c.execute('SELECT a.*,u.full_name AS actor_name FROM audit_events a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.created_at DESC LIMIT 200').fetchall();return self.send_json(200,{'events':[dict(x) for x in rows]})
            return self.fail(404,'Unknown endpoint')
        except PermissionError as e:return self.fail(401 if str(e)=='Sign in required' else 403,str(e))
        except Exception as e:print('API GET error:',repr(e));return self.fail(500,'Unexpected server error')
    def import_tasks(self,u,b):
        if u['role']!='admin':raise PermissionError('Only administrators can import task backups')
        records=b.get('tasks')
        if not isinstance(records,list) or len(records)>5000:raise ValueError('Backup must contain a task list with no more than 5,000 records')
        inserted=0;skipped=0;ts=now()
        with db() as c:
            for item in records:
                if not isinstance(item,dict):skipped+=1;continue
                title=str(item.get('title','')).strip();due=str(item.get('due',''));status=str(item.get('status','Not started'));owner_name=str(item.get('owner','')).strip();team=str(item.get('team','')).strip()
                try:datetime.strptime(due,'%Y-%m-%d')
                except ValueError:skipped+=1;continue
                if not title or len(title)>180 or status not in STATUSES or not owner_name:skipped+=1;continue
                matches=c.execute("SELECT * FROM users WHERE role='employee' AND active=1 AND lower(full_name)=lower(?) AND (?='' OR lower(team)=lower(?))",(owner_name,team,team)).fetchall()
                if len(matches)!=1:skipped+=1;continue
                emp=matches[0];tid=secrets.token_hex(16);completed=str(item.get('completedAt',''))[:10] if status=='Done' else ''
                c.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,title,str(item.get('description',''))[:2000],emp['id'],emp['team'],due,status,str(item.get('quality',''))[:80],str(item.get('contributors',''))[:300],u['id'],str(item.get('createdAt',''))[:40] or ts,str(item.get('updatedAt',''))[:40] or ts,completed))
                inserted+=1
            audit(c,u['id'],'tasks_imported','task_batch',secrets.token_hex(8),f'imported={inserted}; skipped={skipped}')
        return self.send_json(200,{'imported':inserted,'skipped':skipped})
    def create_user(self,u,b):
        if u['role']!='admin':raise PermissionError('Only administrators can create profiles')
        role=str(b.get('role','')); manager_id=b.get('manager_id') or None
        result=add_user(str(b.get('username','')),str(b.get('full_name','')),role,str(b.get('team','')),str(b.get('temporary_password','')),manager_id,True)
        with db() as c:audit(c,u['id'],'user_created','user',result['id'],f"role={role}; team={b.get('team','')}")
        return self.send_json(201,{'user':result})
    def reset_password(self,u,uid,b):
        if u['role']!='admin':raise PermissionError('Only administrators can reset passwords')
        password=str(b.get('temporary_password',''))
        if len(password)<12:raise ValueError('Temporary password must be at least 12 characters')
        salt,digest=pw_hash(password)
        with db() as c:
            c.execute('UPDATE users SET salt=?,password_hash=?,must_change=1 WHERE id=?',(salt,digest,uid))
            if c.total_changes<1:raise ValueError('Profile not found')
            c.execute('DELETE FROM sessions WHERE user_id=?',(uid,));audit(c,u['id'],'password_reset','user',uid)
        return self.send_json(200,{'ok':True})
    def activate_user(self,u,uid,b):
        if u['role']!='admin':raise PermissionError('Only administrators can manage profiles')
        active=1 if b.get('active') else 0
        if uid==u['id'] and not active:raise ValueError('You cannot deactivate your own account')
        with db() as c:
            c.execute('UPDATE users SET active=? WHERE id=?',(active,uid));c.execute('DELETE FROM sessions WHERE user_id=?',(uid,));audit(c,u['id'],'user_activation_changed','user',uid,f'active={active}')
        return self.send_json(200,{'ok':True})
    def create_task(self,u,b):
        if u['role'] not in ('manager','admin'):raise PermissionError('Managers and administrators create tasks')
        owner=str(b.get('owner_id',''));title=str(b.get('title','')).strip();due=str(b.get('due',''));status=str(b.get('status','Not started'))
        if not title or len(title)>180 or not due or status not in STATUSES:raise ValueError('Title (1–180 characters), due date, and valid status are required')
        try:datetime.strptime(due,'%Y-%m-%d')
        except ValueError:raise ValueError('Due date must use YYYY-MM-DD')
        with db() as c:
            emp=c.execute("SELECT * FROM users WHERE id=? AND role='employee' AND active=1",(owner,)).fetchone()
            if not emp:raise ValueError('Choose an active employee')
            if u['role']=='manager' and emp['manager_id']!=u['id']:raise PermissionError('You can only assign tasks to your direct reports')
            tid=secrets.token_hex(16);ts=now();completed=ts[:10] if status=='Done' else ''
            c.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,title,str(b.get('description',''))[:2000],owner,emp['team'],due,status,str(b.get('quality',''))[:80],str(b.get('contributors',''))[:300],u['id'],ts,ts,completed))
            audit(c,u['id'],'task_created','task',tid,f'owner={owner}; status={status}')
            row=c.execute('SELECT t.*,e.full_name AS owner_name FROM tasks t JOIN users e ON e.id=t.owner_id WHERE t.id=?',(tid,)).fetchone()
        return self.send_json(201,{'task':dict(row)})
    def update_task(self,u,tid,b):
        with db() as c:
            row=c.execute('SELECT t.*,e.manager_id FROM tasks t JOIN users e ON e.id=t.owner_id WHERE t.id=?',(tid,)).fetchone()
            if not row:raise ValueError('Task not found')
            full=u['role']=='admin' or (u['role']=='manager' and row['manager_id']==u['id'])
            own=u['role']=='employee' and row['owner_id']==u['id']
            if not(full or own):raise PermissionError('You cannot edit this task')
            status=b.get('status',row['status'])
            if status not in STATUSES:raise ValueError('Invalid status')
            if own and any(k in b for k in ('title','owner_id','team','due','quality','contributors')):raise PermissionError('Employees can update status or request a correction')
            title=str(b.get('title',row['title'])).strip();due=str(b.get('due',row['due']))
            completed=(now()[:10] if status=='Done' and row['status']!='Done' else row['completed_at'] if status=='Done' else '')
            c.execute('UPDATE tasks SET title=?,description=?,due=?,status=?,quality=?,contributors=?,updated_at=?,completed_at=? WHERE id=?',(title,str(b.get('description',row['description']))[:2000],due,status,str(b.get('quality',row['quality']))[:80],str(b.get('contributors',row['contributors']))[:300],now(),completed,tid))
            audit(c,u['id'],'task_updated','task',tid,'status='+status)
        return self.send_json(200,{'ok':True})
    def create_feedback(self,u,b):
        if u['role']!='manager':raise PermissionError('Only managers create employee feedback')
        employee_id=str(b.get('employee_id',''));rating=int(b.get('rating',0));title=str(b.get('title','')).strip();text=str(b.get('feedback','')).strip();period=str(b.get('period','')).strip();task_id=b.get('task_id') or None
        if not 1<=rating<=5 or not title or len(title)>160 or not text or len(text)>3000 or not period or len(period)>60:raise ValueError('Title (1–160), period (1–60), feedback (1–3000), and a 1–5 rating are required')
        with db() as c:
            emp=c.execute("SELECT * FROM users WHERE id=? AND role='employee' AND manager_id=? AND active=1",(employee_id,u['id'])).fetchone()
            if not emp:raise PermissionError('Choose an active direct report')
            if task_id and not c.execute('SELECT 1 FROM tasks WHERE id=? AND owner_id=?',(task_id,employee_id)).fetchone():raise ValueError('Related task must belong to the selected employee')
            eid=secrets.token_hex(16);ts=now();shared=int(bool(b.get('shared')))
            c.execute('INSERT INTO evaluations VALUES(?,?,?,?,?,?,?,?,?,?,?)',(eid,employee_id,u['id'],task_id,period,title,rating,text,shared,ts,ts))
            audit(c,u['id'],'feedback_created','feedback',eid,f'shared={shared}; employee={employee_id}')
        return self.send_json(201,{'id':eid})
    def update_feedback(self,u,eid,b):
        if u['role']!='manager':raise PermissionError('Only the authoring manager can correct feedback')
        try:rating=int(b.get('rating',0))
        except:rating=0
        title=str(b.get('title','')).strip();text=str(b.get('feedback','')).strip();period=str(b.get('period','')).strip();task_id=b.get('task_id') or None
        if not 1<=rating<=5 or not title or len(title)>160 or not text or len(text)>3000 or not period or len(period)>60:raise ValueError('Title (1–160), period (1–60), feedback (1–3000), and a 1–5 rating are required')
        with db() as c:
            e=c.execute('SELECT * FROM evaluations WHERE id=? AND manager_id=?',(eid,u['id'])).fetchone()
            if not e:raise ValueError('Feedback not found')
            if task_id and not c.execute('SELECT 1 FROM tasks WHERE id=? AND owner_id=?',(task_id,e['employee_id'])).fetchone():raise ValueError('Related task must belong to the selected employee')
            c.execute('UPDATE evaluations SET task_id=?,period=?,title=?,rating=?,feedback=?,updated_at=? WHERE id=?',(task_id,period,title,rating,text,now(),eid))
            if e['shared']:
                c.execute('DELETE FROM hr_reviews WHERE evaluation_id=?',(eid,))
                audit(c,u['id'],'hr_review_invalidated','feedback',eid,'Manager corrected shared feedback; HR review cleared for reevaluation')
            audit(c,u['id'],'feedback_corrected','feedback',eid,f'rating={rating}; shared={e["shared"]}')
        return self.send_json(200,{'ok':True})
    def share_feedback(self,u,eid):
        if u['role']!='manager':raise PermissionError('Only the authoring manager can share feedback')
        with db() as c:
            row=c.execute('SELECT * FROM evaluations WHERE id=? AND manager_id=?',(eid,u['id'])).fetchone()
            if not row:raise ValueError('Feedback not found')
            c.execute('UPDATE evaluations SET shared=1,updated_at=? WHERE id=?',(now(),eid));audit(c,u['id'],'feedback_shared','feedback',eid)
        return self.send_json(200,{'ok':True})
    def hr_review(self,u,eid,b):
        if u['role']!='hr':raise PermissionError('Only HR can grade shared feedback')
        try:grade=int(b.get('grade',0))
        except:grade=0
        disposition=str(b.get('disposition','Reviewed'));review=str(b.get('review','')).strip()
        if not 1<=grade<=5 or not review or disposition not in ('Reviewed','Follow-up required'):raise ValueError('A 1–5 grade, review note, and valid disposition are required')
        with db() as c:
            e=c.execute('SELECT * FROM evaluations WHERE id=? AND shared=1',(eid,)).fetchone()
            if not e:raise PermissionError('Only shared feedback can be reviewed')
            old=c.execute('SELECT id FROM hr_reviews WHERE evaluation_id=?',(eid,)).fetchone();rid=old['id'] if old else secrets.token_hex(16);ts=now()
            c.execute('INSERT INTO hr_reviews VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(evaluation_id) DO UPDATE SET reviewer_id=excluded.reviewer_id,grade=excluded.grade,review=excluded.review,disposition=excluded.disposition,updated_at=excluded.updated_at',(rid,eid,u['id'],grade,review,disposition,ts,ts) if not old else (rid,eid,u['id'],grade,review,disposition,ts,ts))
            audit(c,u['id'],'hr_review_saved','feedback',eid,f'grade={grade}; disposition={disposition}')
        return self.send_json(200,{'ok':True})
    def create_correction(self,u,b):
        etype=str(b.get('entity_type',''));eid=str(b.get('entity_id',''));reason=str(b.get('reason','')).strip()
        if etype not in ('task','feedback') or not eid or len(reason)<5:raise ValueError('Choose a record and provide a correction reason')
        with db() as c:
            if etype=='task':
                row=c.execute('SELECT t.*,e.manager_id FROM tasks t JOIN users e ON e.id=t.owner_id WHERE t.id=?',(eid,)).fetchone()
                allowed=row and u['role']=='employee' and row['owner_id']==u['id']
            else:
                row=c.execute('SELECT * FROM evaluations WHERE id=? AND shared=1',(eid,)).fetchone();allowed=row and u['role']=='employee' and row['employee_id']==u['id']
            if not allowed:raise PermissionError('You can only request corrections to your own records')
            cid=secrets.token_hex(16);c.execute('INSERT INTO corrections VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,etype,eid,u['id'],reason,'Pending','',None,now(),''));audit(c,u['id'],'correction_requested',etype,eid)
        return self.send_json(201,{'id':cid})
    def resolve_correction(self,u,cid,b):
        if u['role'] not in ('manager','admin'):raise PermissionError('Only the employee’s manager or administrator can resolve requests')
        status=str(b.get('status',''));resolution=str(b.get('resolution','')).strip()
        if status not in ('Accepted','Declined') or len(resolution)<3:raise ValueError('Choose a decision and add a resolution note')
        with db() as c:
            row=c.execute('SELECT x.*,r.manager_id FROM corrections x JOIN users r ON r.id=x.requester_id WHERE x.id=?',(cid,)).fetchone()
            if not row:raise ValueError('Correction request not found')
            if u['role']=='manager' and row['manager_id']!=u['id']:raise PermissionError('You can only resolve requests from your direct reports')
            if row['status']!='Pending':raise ValueError('This request has already been resolved')
            c.execute('UPDATE corrections SET status=?,resolution=?,resolver_id=?,resolved_at=? WHERE id=?',(status,resolution,u['id'],now(),cid));audit(c,u['id'],'correction_resolved',row['entity_type'],row['entity_id'],status)
            if status=='Accepted' and row['entity_type']=='task':c.execute('UPDATE tasks SET description=description||?,updated_at=? WHERE id=?',('\nCorrection note: '+resolution,now(),row['entity_id']))
            if status=='Accepted' and row['entity_type']=='feedback':
                c.execute('UPDATE evaluations SET feedback=feedback||?,updated_at=? WHERE id=?',('\nCorrection note: '+resolution,now(),row['entity_id']))
                c.execute('DELETE FROM hr_reviews WHERE evaluation_id=?',(row['entity_id'],))
                audit(c,u['id'],'hr_review_invalidated','feedback',row['entity_id'],'Accepted employee correction requires HR reevaluation')
        return self.send_json(200,{'ok':True})
    def do_OPTIONS(self):self.send_response(204);self.send_header('Allow','GET, POST, PUT, PATCH, OPTIONS');self.end_headers()

def create_initial_admin():
    with db() as c:
        if c.execute('SELECT 1 FROM users LIMIT 1').fetchone():print('Profiles already exist; initial administrator was not changed.');return
    print('Create the first Worklog administrator profile.')
    username=input('Admin username: ').strip();name=input('Admin full name: ').strip();team=input('Department (default Administration): ').strip() or 'Administration';pw=getpass.getpass('Password (at least 12 characters): ');confirm=getpass.getpass('Confirm password: ')
    if pw!=confirm:raise SystemExit('Passwords did not match.')
    add_user(username,name,'admin',team,pw,None,False);print('Administrator created. Start the server with: python server.py')

if __name__=='__main__':
    init_db()
    if len(sys.argv)>1 and sys.argv[1]=='create-admin':create_initial_admin();raise SystemExit(0)
    host=os.environ.get('WORKLOG_HOST','127.0.0.1');port=int(os.environ.get('WORKLOG_PORT','8765'))
    print(f'Worklog v3 running at http://{host}:{port}  |  SQLite: {DB_PATH}')
    print('For access from other devices, configure HTTPS and a reverse proxy; do not expose this development server directly.')
    try:
        with WorklogHTTPServer((host,port),Handler) as httpd:
            httpd.serve_forever()
    except OSError as exc:
        print(f'Could not start Worklog at http://{host}:{port}: {exc}. Check whether another process is already using the port.',file=sys.stderr)
        raise SystemExit(1)
