from fastapi import FastAPI

app=FastAPI()
@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.post("/items")
def create_item():
    return {"message": "Item created successfully!"}
@app.get("/items/{item_id}")
def read_item(item_id:int):
    return {"item_id": item_id, "message": "Item retrieved successfully!"}

@app.put("/items/{item_id}")
def update_item(item_id:int):
    return {"item_id": item_id, "message": "Item updated successfully!"}

@app.delete("/items/{item_id}")
def delete_item(item_id:int):
    return {"item_id": item_id, "message": "Item deleted successfully!"}
