from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models import Borrow,BorrowUpdate
from db import borrows_db,books_db,members_db
from utils import generate_id,record_exists,get_all_records,delete_record,update_record,format_success_message

router=APIRouter(prefix="/borrows",tags=["Borrows"])
@router.post("/borrow_book")
def borrow_book(borrow:Borrow):
    if not record_exists(books_db,borrow.book_id):
        raise HTTPException(status_code=404,detail=f"Book with id {borrow.book_id} not found.")
    if not record_exists(members_db,borrow.member_id):
        raise HTTPException(status_code=404,detail=f"Member with id {borrow.member_id} not found.")
    id=generate_id(borrows_db)
    borrows_db[id]=borrow.model_dump()
    return {
        "id":id,
        "borrow":borrow,
        "message":"Book borrowed successfully."
        }
@router.get("/get_borrow/{id}")
def get_borrow(id:int):
    if not record_exists(borrows_db,id):
        raise HTTPException(status_code=404,detail=f"Borrow record with id {id} not found.")
    return borrows_db[id]

@router.get("/get_all_borrows")
def get_all_borrows():
    return get_all_records(borrows_db)

@router.put("/update_borrow/{id}")
def update_borrow(id:int, borrow:BorrowUpdate):
    if not record_exists(borrows_db,id):
        raise HTTPException(status_code=404,detail=f"Borrow record with id {id} not found.")
    if borrow.member_id is not None:
        borrows_db[id]["member_id"]=borrow.member_id
    if borrow.book_id is not None:
        borrows_db[id]["book_id"]=borrow.book_id
    if borrow.borrow_date is not None:
        borrows_db[id]["borrow_date"]=borrow.borrow_date
    if borrow.due_date is not None:
        borrows_db[id]["due_date"]=borrow.due_date
    
    return format_success_message("updated","Borrow record",id)

@router.delete("/delete_borrow/{id}")
def delete_borrow(id:int):
    if not record_exists(borrows_db,id):
        raise HTTPException(status_code=404,detail=f"Borrow record with id {id} not found.")
    delete_record(borrows_db,id)
    return format_success_message("deleted","Borrow record",id)