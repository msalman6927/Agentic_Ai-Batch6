from fastapi import FastAPI
from routers import books,members,borrows


app=FastAPI(title="Library Management System",description="A simple library management system built with FastAPI.",version="1.0.0")

app.include_router(books.router)
app.include_router(members.router)
app.include_router(borrows.router)

@app.get("/")
def root():
    return {"message":"Welcome to the Library Management System API."}