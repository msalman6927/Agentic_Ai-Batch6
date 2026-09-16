
from fastapi import FastAPI, Query, Path, status,HTTPException
from typing import Annotated
from pydantic import BaseModel, Field



db:dict[int,dict]={}

app=FastAPI()
class Item(BaseModel):
    item_id:int
    name:str
    price:float
    secret_number:Annotated[int, Field(title="Secret Number", description="This is a secret number", ge=1, le=100)]
    password:str|None=None

class responses(BaseModel):
    item_id:int
    name:str
    price:float
    password:str|None=None

@app.get("/items/{item_id}")
def read_items(item_id:int,page:int=Query(default=1,le=100), size:int=Query(default=1)):
    return {
        "item_id": item_id,
        "result": f"Page: {page}, Size: {size}"
        }
    
@app.post("/items",response_model_exclude_none=True,status_code=status.HTTP_201_CREATED)

def create_item(item:Item):
    if item.item_id in db:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Item already exists")
    db[item.item_id] = item.model_dump()
 
    return {
        "data":item,
        "result": "Item created successfully!"
    }

@app.get("/all_items")
def get_all_items():
    return {
        "data": db,
        "result": "All items retrieved successfully!"
    }

@app.get("/get_items/{item_id}",response_model=responses)
def get_item(item_id:int):
    if item_id not in db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return db[item_id]
        
@app.put("/update_items")
def update_item(item:Item):
    if item.item_id not in db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    db[item.item_id] = item.model_dump()
    return {
        "data": item,
        "result": "Item updated successfully!"
    }
    
@app.delete("/delete_items/{item_id}")
def delete_item(item_id:int):
    if item_id not in db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    del db[item_id]
    return {
        "result": "Item deleted successfully!"
    }
    
