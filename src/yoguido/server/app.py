"""
Fixed FastAPI server for YoGuido framework with router support
Replace your yoguido/server/app.py with this version
"""

import json
import uuid
import secrets
import hashlib
import uvicorn
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from fastapi import FastAPI, Request, HTTPException, Depends, Cookie, Header
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

# Add these imports
from ..core.audit import GXPAuditLogger
from ..data.db import DatabaseManager

# User authentication models
class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    
class UserInDB(User):
    hashed_password: str
    
class Token(BaseModel):
    access_token: str
    token_type: str
    
class TokenData(BaseModel):
    username: Optional[str] = None

class EventRegistry:
    """Registry for event handlers"""
    
    handlers: Dict[str, Callable] = {}
    
    @classmethod
    def register_handler(cls, handler_id: str, callback: Callable):
        """Register an event handler"""
        cls.handlers[handler_id] = callback
        print(f"🎯 Registered handler: {handler_id}")
    
    @classmethod
    def execute_handler(cls, handler_id: str, *args, **kwargs) -> Any:
        """Execute an event handler"""
        if handler_id in cls.handlers:
            try:
                return cls.handlers[handler_id](*args, **kwargs)
            except Exception as e:
                print(f"❌ Handler {handler_id} failed: {e}")
                raise
        else:
            print(f"⚠️ Handler not found: {handler_id}")

class YoGuidoServer:
    """FastAPI server for YoGuido runtime with multi-user support"""
    
    # Global instance for app-wide access to the server and database
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get the global server instance"""
        if cls._instance is None:
            raise RuntimeError("YoGuidoServer not initialized. Call YoGuidoServer() first.")
        return cls._instance
    
    @classmethod
    def get_db_manager(cls):
        """Get the database manager instance"""
        instance = cls.get_instance()
        return instance.db_manager
    
    def __init__(self, build_dir: str = "./yoguido_build", db_config: Dict = None):
        self.app = FastAPI(title="YoGuido Runtime")
        self.build_dir = Path(build_dir)
        self.db_config = db_config or {}
        
        # Set as global instance
        YoGuidoServer._instance = self
        
        # Initialize session and user management
        self.audit_logger = GXPAuditLogger()
        self.db_manager = None  # Will be initialized in setup_database
        self.sessions = {}  # Maps session_tokens to session data
        self.session_token_to_id = {}  # Maps tokens to audit session IDs
        
        # Set up middleware for CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Restrict in production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # IMPORTANT: Setup routes immediately on initialization
        print("🔧 Setting up routes during server initialization...")
        self.setup_app()
        print(f"🔧 Routes setup complete. Total routes: {len(self.app.routes)}")
    
    def setup_database(self, db_config: Dict = None):
        """Initialize the database manager with configuration"""
        # Use provided config or fall back to the one from __init__
        config = db_config or self.db_config or {}
        
        # Create database manager with configuration
        self.db_manager = DatabaseManager(config)
        
        # Log database initialization
        db_type = config.get('type', 'mysql')
        db_host = config.get('host', 'localhost')
        db_name = config.get('database', 'yoguido')
        print(f"🗃️ Initialized {db_type} database connection to {db_host}/{db_name}")
        
        # Return for chaining
        return self
        
    def setup_app(self):
        """Set up all routes and middleware"""
        self.setup_routes()
        self.setup_auth_routes()
        self.setup_static_files()
        return self
    
    def setup_routes(self):
        """Setup API routes"""
        print("🔧 Setting up routes...")
        
        @self.app.get("/", response_class=HTMLResponse)
        async def serve_app():
            """Serve the main HTML file"""
            try:
                print("📄 Serving root route /")
                
                # DON'T execute components here - they're already executed in runtime
                # Just serve the compiled HTML file
                html_file = self.build_dir / "index.html"
                if html_file.exists():
                    print(f"✅ Found index.html at {html_file}")
                    content = html_file.read_text(encoding='utf-8')
                    print(f"📄 Serving index.html ({len(content)} characters)")
                    return content
                else:
                    print(f"❌ index.html not found at {html_file}")
                    print(f"🔍 Build directory: {self.build_dir}")
                    print(f"🔍 Build directory exists: {self.build_dir.exists()}")
                    if self.build_dir.exists():
                        files = list(self.build_dir.iterdir())
                        print(f"🔍 Build directory contents: {files}")
                    
                    # Return a helpful error page
                    return """
                    <!DOCTYPE html>
                    <html>
                        <head>
                            <title>YoGuido App - Not Compiled</title>
                        </head>
                        <body>
                            <h1>YoGuido App</h1>
                            <p><strong>Error:</strong> App not compiled yet.</p>
                            <p>The index.html file was not found in the build directory.</p>
                            <p>Make sure your app.compile() method is working correctly.</p>
                            <p>Build directory: """ + str(self.build_dir) + """</p>
                        </body>
                    </html>
                    """
            except Exception as e:
                print(f"❌ Error serving root route: {e}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=str(e))
        
        print("🔧 Root route (/) registered")
        
        @self.app.get("/styles.css")
        async def serve_css():
            """Serve the CSS file"""
            css_file = self.build_dir / "styles.css"
            if css_file.exists():
                return Response(
                    content=css_file.read_text(encoding='utf-8'),
                    media_type="text/css"
                )
            return Response(
                content="/* CSS file not found */",
                media_type="text/css"
            )
        
        @self.app.get("/main.js")
        async def serve_js():
            """Serve the JavaScript file"""
            js_file = self.build_dir / "main.js"
            if js_file.exists():
                return Response(
                    content=js_file.read_text(encoding='utf-8'),
                    media_type="application/javascript"
                )
            return Response(
                content="// JavaScript file not found",
                media_type="application/javascript"
            )
            
        @self.app.get("/login", response_class=HTMLResponse)
        async def serve_login():
            """Serve the login page"""
            login_file = self.build_dir / "login.html"
            if login_file.exists():
                return login_file.read_text(encoding='utf-8')
            else:
                return """
                <html>
                    <body>
                        <h1>YoGuido Login</h1>
                        <form action="/api/login" method="post">
                            <div>
                                <label>Username: <input type="text" name="username" required></label>
                            </div>
                            <div>
                                <label>Password: <input type="password" name="password" required></label>
                            </div>
                            <div>
                                <button type="submit">Login</button>
                            </div>
                        </form>
                    </body>
                </html>
                """
                
        @self.app.post("/hcc")
        async def handle_component_communication(request: Request):
            """Handle component state changes from frontend"""
            try:
                data = await request.json()
                print(f"📡 HCC Request: {data}")
                
                event_type = data.get('event_type')
                handler_id = data.get('handler_id')
                
                response_data = {
                    "status": "success",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
                # Handle button clicks
                if event_type == "click" and handler_id:
                    print(f"🔥 Executing handler: {handler_id}")
                    try:
                        result = EventRegistry.execute_handler(handler_id)
                        print(f"✅ Handler executed successfully: {result}")
                        response_data["handler_result"] = result
                    except Exception as e:
                        print(f"❌ Handler execution failed: {e}")
                        response_data["status"] = "error"
                        response_data["error"] = str(e)
                
                # Handle input changes
                elif event_type == "input":
                    field_name = data.get('field_name')
                    new_value = data.get('value')
                    print(f"📝 Input change: {field_name} = {new_value}")
                    response_data["field_updated"] = field_name
                    response_data["new_value"] = new_value
                
                # CRITICAL: Re-execute components after state changes
                print("🔄 Re-executing components after state change...")
                
                # Get updated component tree
                updated_tree = self._execute_app_components()
                
                response_data["component_tree"] = updated_tree
                
                return JSONResponse(content=response_data)
                
            except Exception as e:
                print(f"❌ HCC endpoint error: {e}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/state")
        async def get_current_state():
            """Get current application state"""
            from ..core.state import state_manager
            
            return JSONResponse(content={
                "current_state": state_manager.get_current_state_snapshot(),
                "change_history": state_manager.get_change_history()
            })
        
        @self.app.post("/api/render")
        async def trigger_render():
            """Trigger a component re-render - FIXED for router support"""
            try:
                print("🎨 /api/render called - starting component execution")
                
                # Get the current app and execute its components
                from ..core.runtime import get_current_app
                current_app = get_current_app()
                
                if current_app:
                    print("🔄 Executing app components through runtime...")
                    current_app._execute_components()
                    
                    # Get updated component tree
                    from ..ui.basic_components import _get_component_tree
                    component_tree = _get_component_tree()
                    
                    print(f"🌳 Component tree after execution: {len(component_tree)} components")
                    
                    return JSONResponse(content={
                        "status": "success",
                        "component_tree": component_tree
                    })
                else:
                    print("❌ No current app found")
                    return JSONResponse(content={
                        "status": "error",
                        "message": "No current app found"
                    }, status_code=500)
                
            except Exception as e:
                print(f"❌ /api/render failed: {e}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=str(e))
    
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy", "framework": "yoguido-vanilla"}
            
        print("🔧 All routes registered successfully")
        print(f"🔧 Total routes: {len(self.app.routes)}")
        for route in self.app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                print(f"   📍 {list(route.methods)} {route.path}")
            elif hasattr(route, 'path'):
                print(f"   📍 {route.path}")
    
    def setup_auth_routes(self):
        """Set up authentication routes"""
        
        @self.app.post("/api/login", response_model=Token)
        async def login_for_access_token(
            form_data: OAuth2PasswordRequestForm = Depends(),
            user_agent: str = Header(None),
            request: Request = None
        ):
            # Authenticate user against database
            user = self.authenticate_user(form_data.username, form_data.password)
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Create session in audit logger
            session_id = self.audit_logger.create_session(
                user_id=user.username,
                user_name=user.full_name or user.username,
                ip_address=request.client.host,
                user_agent=user_agent or ""
            )
            
            # Generate session token
            session_token = secrets.token_urlsafe(32)
            expires = datetime.utcnow() + timedelta(hours=8)
            
            # Store session data
            self.sessions[session_token] = {
                "user": user.dict(),
                "expires": expires,
                "session_id": session_id
            }
            self.session_token_to_id[session_token] = session_id
            
            return {
                "access_token": session_token,
                "token_type": "bearer"
            }
        
        @self.app.post("/api/logout")
        async def logout(session_token: str = Cookie(None)):
            if session_token and session_token in self.sessions:
                session_id = self.session_token_to_id.get(session_token)
                if session_id:
                    # Close session in audit logger
                    self.audit_logger.close_session(session_id)
                
                # Remove session data
                del self.sessions[session_token]
                if session_token in self.session_token_to_id:
                    del self.session_token_to_id[session_token]
                
                return {"status": "success", "message": "Logged out successfully"}
            return {"status": "error", "message": "No active session"}
        
    def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        """Authenticate user against database"""
        if not self.db_manager:
            raise RuntimeError("Database not initialized. Call setup_database() first.")
            
        try:
            # Use MySQL/PostgreSQL compatible placeholders
            placeholder = "%s" if self.db_manager.db_type in ('mysql', 'postgres') else "?"
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT username, full_name, email, hashed_password, disabled FROM users WHERE username = {placeholder}",
                    (username,)
                )
                user_data = cursor.fetchone()
                
                if not user_data:
                    return None
                    
                # Handle different result formats
                if isinstance(user_data, tuple):
                    username, full_name, email, hashed_password, disabled = user_data
                else:  # Dictionary-like object
                    username = user_data['username']
                    full_name = user_data['full_name']
                    email = user_data['email']
                    hashed_password = user_data['hashed_password']
                    disabled = user_data['disabled']
                
                # Check password
                if self.verify_password(password, hashed_password):
                    return UserInDB(
                        username=username,
                        email=email,
                        full_name=full_name,
                        disabled=bool(disabled),
                        hashed_password=hashed_password
                    )
                return None
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return None
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash (use proper hashing in production)"""
        # In real app, use bcrypt or similar
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
    
    def get_current_user(self, session_token: str = Cookie(None)) -> Optional[User]:
        """Get current user from session token"""
        if not session_token or session_token not in self.sessions:
            return None
            
        session = self.sessions[session_token]
        if datetime.utcnow() > session["expires"]:
            # Session expired
            del self.sessions[session_token]
            return None
            
        return User(**session["user"])
    
    def setup_static_files(self):
        """Setup static file serving"""
        if self.build_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(self.build_dir)), name="static")

    def _execute_app_components(self, session_id: str = None, user: User = None) -> List[Dict]:
        """
        FIXED: Execute app components with router support
        This method handles both traditional components and router-based apps
        """
        try:
            # Set session context only if provided
            if session_id and user:
                from ..core.state import set_current_session
                set_current_session(session_id, user.dict())
            
            # Now execute components as before but in session context
            from ..ui.basic_components import _clear_component_tree, _get_component_tree
            
            # Clear previous component tree
            _clear_component_tree()
            
            # Execute router component or regular components
            from ..core.runtime import get_current_app
            current_app = get_current_app()
            
            if current_app and current_app._router_enabled:
                print("🛣️ Router enabled - executing router component")
                try:
                    from ..pages.routing import router_component
                    router_component()
                    print("✅ Router component executed")
                except Exception as e:
                    print(f"❌ Router component failed: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("🎨 Executing traditional components")
                from ..core.decorators import _registry
                components = _registry.get_all_components()
                
                for comp_id, metadata in components.items():
                    try:
                        metadata.function()
                    except Exception as e:
                        print(f"❌ Component {comp_id} execution failed: {e}")
            
            # Get the component tree
            tree = _get_component_tree()
            print(f"🌳 Generated component tree with {len(tree)} components")
            return tree
        
        except Exception as e:
            print(f"❌ Component execution failed: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            # Clear session context
            from ..core.state import clear_current_session
            clear_current_session()
            
    @staticmethod
    def get_db_manager() -> DatabaseManager:
        """Get the global database manager instance"""
        return YoGuidoServer.get_db_manager()
    
    def run(self, host: str = "127.0.0.1", port: int = 8000):
        """Run the server with optional database configuration override"""
        
        # Routes are now set up during initialization
        
        # Print server info
        print(f"🚀 Starting YoGuido server at http://{host}:{port}")
        uvicorn.run(self.app, host=host, port=port)