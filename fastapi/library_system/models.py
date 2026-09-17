from pydantic import BaseModel
from typing import Optional


class Book(BaseModel):
    title:str
    author:str
    total_copies:int
    

class BookUpdate(BaseModel):
    title:Optional[str]=None
    author:Optional[str]=None
    total_copies:Optional[int]=None

class Member(BaseModel):
    name:str
    email:str
    
class MemberUpdate(BaseModel):
    name:Optional[str]=None
    email:Optional[str]=None
    
class Borrow(BaseModel):
    book_id:int
    member_id:int
    borrow_date:str
    
class BorrowUpdate(BaseModel):
    return_date:Optional[str]=None