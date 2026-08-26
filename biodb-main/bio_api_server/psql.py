from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import Optional

from nanoid import generate
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session as typeing_Session, DeclarativeBase
from sqlalchemy.schema import Column
from sqlalchemy.types import SmallInteger, String, Date, TIMESTAMP, DateTime, BOOLEAN

import env

engine = create_engine(f"postgresql+psycopg2://{env.POSTGRES_USER}:{env.POSTGRES_PASSWORD}@{env.POSTGRES_HOST}:{env.POSTGRES_PORT}/biodb")
Session = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    __abstract__ = True
    __table_args__ = {"schema": "biodbapi"}

def session_scope(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        session = Session()
        try:
            kwargs['session'] = session
            result = func(*args, **kwargs)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    return wrapper

class Users(Base):
    __tablename__ = "users"
    id = Column(String(21), primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(40))
    sex = Column(SmallInteger, default=0, nullable=False)
    birth_date = Column(Date)
    role = Column(String(10))

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "sex": self.sex,
            "birth_date": self.birth_date,
            "role": self.role,
        }

class Participants(Base):
    __tablename__ = "participants"
    id = Column(String(21), primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(40))
    sex = Column(SmallInteger, default=0, nullable=False)
    birth_date = Column(Date)
    is_enable = Column(BOOLEAN)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "sex": self.sex,
            "birth_date": self.birth_date,
            "is_enable": self.is_enable,
        }

Base.metadata.create_all(bind=engine)

# user

# ユーザが見つからない場合は例外
@session_scope
def get_user_from_email(email: str, session: typeing_Session) -> dict:
    return session.query(Users).filter(Users.email == email).one().to_dict()

@session_scope
def get_user_from_id(id: str, session: typeing_Session) -> dict:
    return session.query(Users).filter(Users.id == id).one().to_dict()

@session_scope
def add_user(email: str, session: typeing_Session) -> dict:
    is_created = session.query(Users).filter(Users.email == email).first()
    if is_created != None:
        raise KeyError("Already Created")
    for _ in range(10):
        user_id = generate()
        is_existed_id = session.query(Users).filter(Users.id == user_id).first()
        if is_existed_id != None:
            continue
        else:
            new_user = Users(id=user_id, email=email, role="normal")
            session.add(new_user)
            return new_user.to_dict()
    raise RuntimeError("Fail Create UserID")

@session_scope
def update_user_data(user_id: str, name: Optional[str], sex: Optional[int], birth_date, session: typeing_Session):
    user = session.query(Users).filter(Users.id == user_id).one_or_none()
    if user is None:
        raise IndexError("User Not Found Error")
    # Update
    user.name = name
    user.sex = sex
    user.birth_date = birth_date
    return

@session_scope
def update_user_role(user_id: str, role: str, session: typeing_Session):
    user = session.query(Users).filter(Users.id == user_id).one_or_none()
    if user is None:
        raise IndexError("User Not Fround Error")
    user.role = role
    return

@session_scope
def ensure_admin_user(email: str, session: typeing_Session) -> dict:
    """
    指定されたメールアドレスのユーザーを管理者として登録または更新する．
    - ユーザーが存在しない場合：管理者として新規作成する．
    - ユーザーが存在する場合：ロールを'admin'に更新する．
    """
    # 既存ユーザーを検索
    user = session.query(Users).filter(Users.email == email).one_or_none()

    if user:
        # ユーザーが既に存在する場合
        if user.role == "admin":
            print(f"Info: User '{email}' is already an admin.")
        else:
            user.role = "admin"
            print(f"Info: User '{email}' role has been updated to 'admin'.")
        return user.to_dict()
    else:
        # ユーザーが存在しない場合、新規作成する
        for _ in range(10):
            user_id = generate()
            is_existed_id = session.query(Users).filter(Users.id == user_id).first()
            if is_existed_id is None:
                new_user = Users(
                    id=user_id,
                    email=email,
                    role="admin"  # ロールを 'admin' に設定
                )
                session.add(new_user)
                print(f"Info: New admin user '{email}' has been created.")
                return new_user.to_dict()
        
        raise RuntimeError("Failed to generate a unique User ID.")
# participant

@session_scope
def get_participant_from_email(email: str, session: typeing_Session) -> dict:
    return session.query(Participants).filter(Participants.email == email).one().to_dict()

@session_scope
def get_participant_from_id(id: str, session: typeing_Session) -> dict:
    return session.query(Participants).filter(Participants.id == id).one().to_dict()

@session_scope
def get_all_participant(session: typeing_Session) -> list[dict]:
    return [participant.to_dict() for participant in session.query(Participants).all()]

@session_scope
def add_participant(email: str, session: typeing_Session) -> dict:
    is_created = session.query(Participants).filter(Participants.email == email).first()
    if is_created != None:
        raise Exception("Already created")
    for _ in range(10):
        participant_id = generate()
        is_existed_id = session.query(Participants).filter(Participants.id == participant_id).first()
        if is_existed_id != None:
            continue
        else:
            new_participant = Participants(id=participant_id, email=email, is_enable=True)
            session.add(new_participant)
            return new_participant.to_dict()
    raise RuntimeError("Fail Create UserID")

@session_scope
def update_participant_data(participant_id: str, name: Optional[str], sex: Optional[int], birth_date, is_enable: Optional[bool], session: typeing_Session):
    participant = session.query(Participants).filter(Participants.id == participant_id).one_or_none()
    if participant is None:
        raise IndexError("Not fount participant")
    if name is not None:
        participant.name = name
    if sex is not None:
        participant.sex = sex
    if birth_date is not None:
        participant.birth_date = birth_date
    if is_enable is not None:
        participant.is_enable = is_enable
    return