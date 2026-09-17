from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models import Book,BookUpdate
from db import books_db
from utils import generate_id,record_exists,get_all_records,delete_record,update_record,format_success_message

router=APIRouter(prefix="/books",tags=["Books"])
@router.post("/add_book")
def add_book(book:Book):
    id=generate_id(books_db)
    books_db[id]=book.model_dump()
    return {
        "id":id,
        "book":book,
        "message":"Book added successfully."
        }
@router.get("/get_book/{id}")
def get_book(id:int):
    if not record_exists(books_db,id):
        raise HTTPException(status_code=404,detail=f"Book with id {id} not found.")
    return books_db[id]

@router.get("/get_all_books")
def get_all_books():
    return get_all_records(books_db)

@router.put("/update_book/{id}")
def update_book(id:int, book:BookUpdate):
    if not record_exists(books_db,id):
        raise HTTPException(status_code=404,detail=f"Book with id {id} not found.")
    if book.title is not None:
        books_db[id]["title"]=book.title
    if book.author is not None:
        books_db[id]["author"]=book.author
    if book.total_copies is not None:
        books_db[id]["total_copies"]=book.total_copies
    return format_success_message("updated","Book",id)

@router.delete("/delete_book/{id}")
def delete_book(id:int):
    if not record_exists(books_db,id):
        raise HTTPException(status_code=404,detail=f"Book with id {id} not found.")
    delete_record(books_db,id)
    return format_success_message("deleted","Book",id)
