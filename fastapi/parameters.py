
from fastapi import FastAPI, Query, Path
from typing import Annotated
from pydantic import BaseModel

app=FastAPI()
class Item(BaseModel):
    name:str
    price:float
    secret_number:Annotated[int, Path(title="Secret Number", description="This is a secret number", ge=1, le=100)]
    password:str|None=None



@app.get("/items/{item_id}")
def read_items(item_id:int,page:int=Query(default="1",le=100), size:int=Query(default=1)):
    return {
        "item_id": item_id,
        "result": f"Page: {page}, Size: {size}"
        }
    
@app.post("/items")
def create_item(item:Item):
    return {
       "items": item
    }
    
    
    
    
    