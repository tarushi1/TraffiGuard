from fastapi import FastAPI, HTTPException, Depends, Form
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqlalchemy.ext.declarative import declarative_base
import bcrypt

app = FastAPI()

oauth = OAuth()
oauth.register(
    name="google",
    client_id="your_google_client_id",
    client_secret="your_google_client_secret",
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    access_token_url="https://oauth2.googleapis.com/token",
    client_kwargs={"scope": "openid email profile"},
)
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

DATABASE_URL = "sqlite:///./traffiguard.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

class EmergencyRequest(Base):
    __tablename__ = "requests"
    id = Column(Integer, primary_key=True, index=True)
    vehicle_type = Column(String, index=True)
    route = Column(String)  
    eta = Column(Float)
    status = Column(String, default="Pending")


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class LoginRequest(BaseModel):
    username: str
    password: str

class PriorityRequest(BaseModel):
    vehicle_type: str
    route: str
    eta: float

class UpdateRequestStatus(BaseModel):
    request_id: int
    status: str


@app.post("/signup")
def signup(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(username=username, password_hash=hashed_password)
    db.add(user)
    db.commit()
    return {"message": "User registered successfully"}

@app.get("/google-login")
async def google_login(request: Request):
    redirect_uri = "http://localhost:8000/auth"
    return await oauth.google.authorize_redirect(request, redirect_uri)
@app.get("/auth")
async def auth(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    user_info = await oauth.google.parse_id_token(request, token)

    
    user = db.query(User).filter(User.username == user_info["email"]).first()
    if not user:
        user = User(username=user_info["email"], password_hash="google_auth")
        db.add(user)
        db.commit()

    jwt_token = jwt.encode({"sub": user.username}, SECRET_KEY, algorithm="HS256")
    return {"access_token": jwt_token, "token_type": "bearer", "user": user_info}



@app.post("/request-priority")
def request_priority(request: PriorityRequest, db: Session = Depends(get_db)):
    new_request = EmergencyRequest(**request.dict())
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return {"message": "Priority request submitted successfully", "id": new_request.id}


@app.get("/get-requests")
def get_requests(db: Session = Depends(get_db)):
    requests = db.query(EmergencyRequest).all()
    return {"requests": requests}


@app.put("/update-request-status")
def update_request_status(update: UpdateRequestStatus, db: Session = Depends(get_db)):
    request_entry = db.query(EmergencyRequest).filter(EmergencyRequest.id == update.request_id).first()
    if not request_entry:
        raise HTTPException(status_code=404, detail="Request not found")
    
    request_entry.status = update.status
    db.commit()
    return {"message": "Request status updated successfully"}


@app.get("/")
def read_root():
    return {"message": "Welcome to TraffiGuard!"}


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)

