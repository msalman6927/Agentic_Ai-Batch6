from fastapi import APIRouter, HTTPException
from models import Member,MemberUpdate
from db import members_db
from utils import generate_id,record_exists,get_all_records,delete_record,update_record,format_success_message

router=APIRouter(prefix="/members",tags=["Members"])
@router.post("/add_member")
def add_member(member:Member):
    id=generate_id(members_db)
    members_db[id]=member.model_dump()
    return {
        "id":id,
        "member":member,
        "message":"Member added successfully."
        }

@router.get("/get_member/{id}")
def get_member(id:int):
    if not record_exists(members_db,id):
        raise HTTPException(status_code=404,detail=f"Member with id {id} not found.")
    return members_db[id]
    
@router.get("/get_all_members")
def get_all_members():
    return get_all_records(members_db)

@router.put("/update_member/{id}")
def update_member(id:int, member:MemberUpdate):
    if not record_exists(members_db,id):
        raise HTTPException(status_code=404,detail=f"Member with id {id} not found.")
    if member.name is not None:
        members_db[id]["name"]=member.name
    if member.email is not None:
        members_db[id]["email"]=member.email
    return format_success_message("Member updated successfully.")

@router.delete("/delete_member/{id}")
def delete_member(id:int):
    if not record_exists(members_db,id):
        raise HTTPException(status_code=404,detail=f"Member with id {id} not found.")
    delete_record(members_db,id)
    return format_success_message("deleted","Member",id)
